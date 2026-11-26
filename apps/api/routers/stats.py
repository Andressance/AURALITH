"""Listening statistics: play reports and the yearly wrapped summary.

Every finished or abandoned playback session is stored as one row, so totals are
derived instead of keeping counters that could drift. Statistics are per account.
"""

import csv
import io
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from apps.api.deps import current_user, db_session, is_track_hidden
from apps.api.media import versioned_image_url
from apps.api.models import (
    ListeningPlay,
    StatsDashboard,
    Track,
    User,
    normalize_utc,
)

router = APIRouter()

MAX_PLAY_SECONDS = 6 * 60 * 60
TOP_LIMIT = 10
UNKNOWN_ARTIST = "Artista desconocido"
UNKNOWN_ALBUM = "Sin álbum"


def _artist_of(track: Track) -> str:
    return (track.artist or "").strip() or UNKNOWN_ARTIST


def _album_of(track: Track) -> str:
    return (track.album or "").strip() or UNKNOWN_ALBUM


def _track_cover(track: Track | None, user: User) -> str | None:
    if track is None:
        return None
    return versioned_image_url(
        f"/api/tracks/{track.id}/cover",
        track.id if getattr(track, "cover_path", None) else None,
        user,
    )


def _format_minutes(seconds: int) -> int:
    return int(round(seconds / 60))


def _aggregate(played_tracks: list[dict]) -> tuple[dict, dict, dict]:
    """Group per-track totals into artists, albums and genres."""
    artists: dict[str, dict] = {}
    albums: dict[str, dict] = {}
    genres: dict[str, dict] = {}
    for item in played_tracks:
        track = item["track"]
        artist_name = _artist_of(track)
        artist = artists.setdefault(
            artist_name.casefold(),
            {"name": artist_name, "seconds": 0, "plays": 0, "cover": None, "top": -1},
        )
        artist["seconds"] += item["seconds"]
        artist["plays"] += item["plays"]
        if item["seconds"] > artist["top"]:
            artist["top"] = item["seconds"]
            artist["cover"] = track

        album_name = _album_of(track)
        album_key = f"{album_name.casefold()}::{artist_name.casefold()}"
        album = albums.setdefault(
            album_key,
            {
                "name": album_name,
                "artist": artist_name,
                "seconds": 0,
                "plays": 0,
                "cover": None,
                "top": -1,
            },
        )
        album["seconds"] += item["seconds"]
        album["plays"] += item["plays"]
        if item["seconds"] > album["top"]:
            album["top"] = item["seconds"]
            album["cover"] = track

        genre_name = (track.genre or "").strip() or "Sin género"
        genre = genres.setdefault(
            genre_name.casefold(), {"name": genre_name, "seconds": 0, "plays": 0}
        )
        genre["seconds"] += item["seconds"]
        genre["plays"] += item["plays"]
    return artists, albums, genres


def _period_range(period: str, year: int, month: int) -> tuple[datetime | None, datetime | None, str]:
    if period == "all":
        return None, None, "Todo el historial"
    if period == "month":
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        end = (
            datetime(year + 1, 1, 1, tzinfo=timezone.utc)
            if month == 12
            else datetime(year, month + 1, 1, tzinfo=timezone.utc)
        )
        return start, end, f"{month:02d}/{year}"
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    return start, datetime(year + 1, 1, 1, tzinfo=timezone.utc), str(year)


def _play_totals(db: Session, user: User, filters: list) -> list[dict]:
    rows = db.execute(
        select(
            ListeningPlay.track_id,
            func.count(ListeningPlay.id).label("plays"),
            func.coalesce(func.sum(ListeningPlay.seconds), 0).label("seconds"),
        )
        .where(*filters)
        .group_by(ListeningPlay.track_id)
    ).all()
    track_ids = [row.track_id for row in rows]
    tracks = (
        {track.id: track for track in db.scalars(select(Track).where(Track.id.in_(track_ids)))}
        if track_ids
        else {}
    )
    played_tracks = []
    for row in rows:
        track = tracks.get(row.track_id)
        if track is None:
            continue
        played_tracks.append(
            {
                "track": track,
                "plays": int(row.plays),
                "seconds": int(row.seconds or 0),
            }
        )
    return played_tracks


def _artist_payload(entry: dict, user: User) -> dict:
    return {
        "name": entry["name"],
        "seconds": entry["seconds"],
        "minutes": _format_minutes(entry["seconds"]),
        "plays": entry["plays"],
        "cover_url": _track_cover(entry.get("cover"), user),
    }


def _album_payload(entry: dict, user: User) -> dict:
    return {
        "name": entry["name"],
        "artist": entry["artist"],
        "seconds": entry["seconds"],
        "minutes": _format_minutes(entry["seconds"]),
        "plays": entry["plays"],
        "cover_url": _track_cover(entry.get("cover"), user),
    }


def _track_payload(item: dict, user: User) -> dict:
    track = item["track"]
    return {
        "id": track.id,
        "title": str(track.title) if track.title is not None else "Canción sin título",
        "artist": _artist_of(track),
        "album": _album_of(track),
        "seconds": item["seconds"],
        "minutes": _format_minutes(item["seconds"]),
        "plays": item["plays"],
        "cover_url": _track_cover(track, user),
    }


DEFAULT_WIDGETS = [
    {
        "id": "total",
        "title": "Minutos escuchados",
        "type": "stat",
        "dimension": "total",
        "metric": "minutes",
    },
    {
        "id": "hours",
        "title": "Horas en las que más escuchas",
        "type": "columns",
        "dimension": "hours",
        "metric": "minutes",
    },
    {
        "id": "artists",
        "title": "Artistas con más minutos",
        "type": "bars",
        "dimension": "artists",
        "metric": "minutes",
    },
    {
        "id": "genres",
        "title": "Reparto por género",
        "type": "donut",
        "dimension": "genres",
        "metric": "minutes",
    },
    {
        "id": "tracks",
        "title": "Canciones más escuchadas",
        "type": "list",
        "dimension": "tracks",
        "metric": "plays",
    },
    {
        "id": "weekdays",
        "title": "Tus días de la semana",
        "type": "columns",
        "dimension": "weekdays",
        "metric": "minutes",
    },
]

WIDGET_TYPES = {"stat", "bars", "columns", "donut", "list"}
WIDGET_DIMENSIONS = {
    "total",
    "hours",
    "weekdays",
    "months",
    "artists",
    "tracks",
    "albums",
    "genres",
}
WIDGET_METRICS = {"minutes", "plays"}
DEFAULT_TITLES = {
    "total": "Tu tiempo de escucha",
    "hours": "Horas en las que más escuchas",
    "weekdays": "Tus días de la semana",
    "months": "Escuchas por mes",
    "artists": "Artistas más escuchados",
    "tracks": "Canciones más escuchadas",
    "albums": "Álbumes más escuchados",
    "genres": "Géneros más escuchados",
}
MAX_WIDGETS = 12


def _default_widgets() -> list[dict]:
    return [dict(widget) for widget in DEFAULT_WIDGETS]


def _sanitize_widgets(raw) -> list[dict]:
    if not isinstance(raw, list):
        raise HTTPException(status_code=400, detail="widgets must be a list")
    if len(raw) > MAX_WIDGETS:
        raise HTTPException(status_code=400, detail=f"At most {MAX_WIDGETS} widgets are allowed")
    cleaned = []
    seen = set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise HTTPException(status_code=400, detail="every widget must be an object")
        dimension = str(item.get("dimension", "artists")).strip().lower()
        widget_type = str(item.get("type", "bars")).strip().lower()
        metric = str(item.get("metric", "minutes")).strip().lower()
        if dimension not in WIDGET_DIMENSIONS:
            raise HTTPException(status_code=400, detail=f"Unsupported dimension: {dimension}")
        if widget_type not in WIDGET_TYPES:
            raise HTTPException(status_code=400, detail=f"Unsupported chart type: {widget_type}")
        if metric not in WIDGET_METRICS:
            raise HTTPException(status_code=400, detail=f"Unsupported metric: {metric}")
        widget_id = re.sub(r"[^A-Za-z0-9_-]", "", str(item.get("id") or ""))[:40]
        if not widget_id:
            widget_id = f"w{index + 1}"
        if widget_id in seen:
            widget_id = f"{widget_id}-{index}"
        seen.add(widget_id)
        title = str(item.get("title") or "").strip()[:80]
        cleaned.append(
            {
                "id": widget_id,
                "title": title or DEFAULT_TITLES[dimension],
                "type": widget_type,
                "dimension": dimension,
                "metric": metric,
            }
        )
    return cleaned


@router.post("/api/stats/plays")
def record_play(
    payload: dict,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    track_id = payload.get("track_id")
    if not isinstance(track_id, int) or isinstance(track_id, bool):
        raise HTTPException(status_code=400, detail="track_id must be an integer")
    try:
        seconds = int(payload.get("seconds") or 0)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="seconds must be an integer") from None
    # Short previews are not worth a row, and a client cannot claim to have
    # listened longer than a session could possibly last.
    if seconds <= 0:
        return {"ok": True, "recorded": False}
    seconds = min(seconds, MAX_PLAY_SECONDS)
    track = db.get(Track, track_id)
    # Stat rows follow the same visibility rule as the rest of the library.
    if not track or is_track_hidden(db, user, track.id):
        raise HTTPException(status_code=404, detail="Track not found")
    db.add(
        ListeningPlay(
            user_id=user.id,
            track_id=track.id,
            seconds=seconds,
            played_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    return {"ok": True, "recorded": True}


@router.get("/api/stats/plays/export")
def export_plays(
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    """Download every listening session of the account as CSV."""
    rows = db.execute(
        select(
            ListeningPlay.played_at,
            ListeningPlay.seconds,
            Track.title,
            Track.artist,
            Track.album,
            Track.genre,
        )
        .join(Track, Track.id == ListeningPlay.track_id)
        .where(ListeningPlay.user_id == user.id)
        .order_by(ListeningPlay.played_at.asc(), ListeningPlay.id.asc())
    ).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["fecha", "titulo", "artista", "album", "genero", "segundos"])
    for row in rows:
        writer.writerow(
            [
                # UTC with an explicit offset, so the file carries its own timezone.
                normalize_utc(row.played_at).isoformat(),
                str(row.title or ""),
                str(row.artist or ""),
                str(row.album or ""),
                str(row.genre or ""),
                int(row.seconds or 0),
            ]
        )
    return Response(
        # The byte order mark keeps Excel from mangling accents.
        content="\ufeff" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="auralith-historico.csv"',
            "Cache-Control": "no-store",
        },
    )


@router.delete("/api/stats/plays")
def delete_plays(
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
    days: Annotated[int | None, Query(ge=1, le=3650)] = None,
    everything: Annotated[bool, Query()] = False,
):
    """Delete listening sessions older than ``days``, or the whole history."""
    if everything and days is not None:
        raise HTTPException(status_code=400, detail="Use days or everything, not both")
    if not everything and days is None:
        raise HTTPException(
            status_code=400, detail="days is required unless everything=true"
        )
    filters = [ListeningPlay.user_id == user.id]
    if not everything:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        filters.append(ListeningPlay.played_at < cutoff)
    deleted = db.query(ListeningPlay).filter(*filters).delete(synchronize_session=False)
    db.commit()
    return {"ok": True, "deleted": int(deleted or 0)}


@router.get("/api/stats/years")
def list_years(
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    played_year = extract("year", ListeningPlay.played_at)
    years = db.scalars(
        select(played_year)
        .where(ListeningPlay.user_id == user.id)
        .group_by(played_year)
        .order_by(played_year.desc())
    ).all()
    return [int(year) for year in years if year is not None] or [datetime.now(timezone.utc).year]


@router.get("/api/stats/wrapped")
def wrapped(
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
    year: Annotated[int | None, Query(ge=1970, le=9998)] = None,
):
    target_year = year or datetime.now(timezone.utc).year
    month_of_play = extract("month", ListeningPlay.played_at)
    start = datetime(target_year, 1, 1, tzinfo=timezone.utc)
    end = datetime(target_year + 1, 1, 1, tzinfo=timezone.utc)
    # A date range uses the (user_id, played_at) index; filtering by EXTRACT does not.
    filters = (
        ListeningPlay.user_id == user.id,
        ListeningPlay.played_at >= start,
        ListeningPlay.played_at < end,
    )

    played_tracks = _play_totals(db, user, filters)
    artists, albums, _ = _aggregate(played_tracks)

    top_artists = sorted(
        artists.values(), key=lambda item: (-item["seconds"], -item["plays"], item["name"].casefold())
    )[:TOP_LIMIT]
    top_albums = sorted(
        albums.values(),
        key=lambda item: (-item["seconds"], -item["plays"], item["name"].casefold()),
    )[:TOP_LIMIT]
    top_tracks = sorted(
        played_tracks, key=lambda item: (-item["seconds"], -item["plays"])
    )[:TOP_LIMIT]

    total_seconds = sum(item["seconds"] for item in played_tracks)
    total_plays = sum(item["plays"] for item in played_tracks)

    monthly = [{"month": month, "seconds": 0} for month in range(1, 13)]
    month_rows = db.execute(
        select(
            month_of_play.label("month"),
            func.coalesce(func.sum(ListeningPlay.seconds), 0).label("seconds"),
        )
        .where(*filters)
        .group_by(month_of_play)
    ).all()
    for row in month_rows:
        if row.month is not None:
            monthly[int(row.month) - 1]["seconds"] = int(row.seconds or 0)

    day_rows = db.execute(
        select(
            func.date(ListeningPlay.played_at).label("day"),
            func.coalesce(func.sum(ListeningPlay.seconds), 0).label("seconds"),
        )
        .where(*filters)
        .group_by(func.date(ListeningPlay.played_at))
    ).all()
    busiest_day = None
    if day_rows:
        best = max(day_rows, key=lambda row: int(row.seconds or 0))
        busiest_day = {"date": str(best.day), "seconds": int(best.seconds or 0)}

    first_play = db.scalar(select(func.min(ListeningPlay.played_at)).where(*filters))

    return {
        "year": target_year,
        "total_seconds": total_seconds,
        "total_minutes": _format_minutes(total_seconds),
        "total_plays": total_plays,
        "unique_artists": len(artists),
        "unique_tracks": len(played_tracks),
        "top_artists": [_artist_payload(artist, user) for artist in top_artists],
        "top_albums": [_album_payload(album, user) for album in top_albums],
        "top_tracks": [_track_payload(item, user) for item in top_tracks],
        "monthly": monthly,
        "busiest_day": busiest_day,
        "first_play": first_play.isoformat() if first_play else None,
    }


@router.get("/api/stats/overview")
def overview(
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
    period: Annotated[str, Query(pattern="^(year|month|all)$")] = "year",
    year: Annotated[int | None, Query(ge=1970, le=9998)] = None,
    month: Annotated[int | None, Query(ge=1, le=12)] = None,
):
    now = datetime.now(timezone.utc)
    target_year = year or now.year
    target_month = month or now.month
    start, end, label = _period_range(period, target_year, target_month)

    filters: list = [ListeningPlay.user_id == user.id]
    if start is not None and end is not None:
        filters.extend(
            [ListeningPlay.played_at >= start, ListeningPlay.played_at < end]
        )

    played_tracks = _play_totals(db, user, filters)
    artists, albums, genres = _aggregate(played_tracks)

    top_artists = sorted(
        artists.values(),
        key=lambda entry: (-entry["seconds"], -entry["plays"], entry["name"].casefold()),
    )[:TOP_LIMIT]
    top_albums = sorted(
        albums.values(),
        key=lambda entry: (-entry["seconds"], -entry["plays"], entry["name"].casefold()),
    )[:TOP_LIMIT]
    top_genres = sorted(
        genres.values(),
        key=lambda entry: (-entry["seconds"], -entry["plays"], entry["name"].casefold()),
    )[:TOP_LIMIT]
    top_tracks = sorted(
        played_tracks, key=lambda item: (-item["seconds"], -item["plays"])
    )[:TOP_LIMIT]

    def grouped(expression, slots: int) -> list[dict]:
        rows = db.execute(
            select(
                expression.label("slot"),
                func.count(ListeningPlay.id).label("plays"),
                func.coalesce(func.sum(ListeningPlay.seconds), 0).label("seconds"),
            )
            .where(*filters)
            .group_by(expression)
        ).all()
        buckets = [{"seconds": 0, "plays": 0} for _ in range(slots)]
        for row in rows:
            if row.slot is None:
                continue
            index = int(row.slot)
            if 0 <= index < slots:
                buckets[index] = {
                    "seconds": int(row.seconds or 0),
                    "plays": int(row.plays or 0),
                }
        return buckets

    hourly = [
        {"hour": hour, **values}
        for hour, values in enumerate(grouped(extract("hour", ListeningPlay.played_at), 24))
    ]
    weekday = [
        {"weekday": day, **values}
        for day, values in enumerate(grouped(extract("dow", ListeningPlay.played_at), 7))
    ]
    monthly = [
        {"month": month_number, **values}
        for month_number, values in enumerate(
            grouped(extract("month", ListeningPlay.played_at), 12), start=1
        )
    ]

    total_seconds = sum(item["seconds"] for item in played_tracks)
    total_plays = sum(item["plays"] for item in played_tracks)

    return {
        "period": period,
        "label": label,
        "range": {
            "from": start.isoformat() if start else None,
            "to": end.isoformat() if end else None,
        },
        "totals": {
            "seconds": total_seconds,
            "minutes": _format_minutes(total_seconds),
            "plays": total_plays,
            "unique_artists": len(artists),
            "unique_albums": len(albums),
            "unique_tracks": len(played_tracks),
            "unique_genres": len(genres),
        },
        "hourly": hourly,
        "weekday": weekday,
        "monthly": monthly,
        "top_artists": [_artist_payload(entry, user) for entry in top_artists],
        "top_albums": [_album_payload(entry, user) for entry in top_albums],
        "top_tracks": [_track_payload(item, user) for item in top_tracks],
        "top_genres": [
            {
                "name": entry["name"],
                "seconds": entry["seconds"],
                "minutes": _format_minutes(entry["seconds"]),
                "plays": entry["plays"],
            }
            for entry in top_genres
        ],
    }


@router.get("/api/stats/dashboard")
def get_dashboard(
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    row = db.scalar(select(StatsDashboard).where(StatsDashboard.user_id == user.id))
    if row is None:
        return {"widgets": _default_widgets(), "updated_at": None}
    try:
        widgets = _sanitize_widgets(json.loads(row.layout))
    except (ValueError, HTTPException):
        widgets = _default_widgets()
    return {
        "widgets": widgets,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.put("/api/stats/dashboard")
def save_dashboard(
    payload: dict,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    widgets = _sanitize_widgets(payload.get("widgets"))
    row = db.scalar(select(StatsDashboard).where(StatsDashboard.user_id == user.id))
    if row is None:
        row = StatsDashboard(user_id=user.id)
        db.add(row)
    row.layout = json.dumps(widgets)
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"widgets": widgets, "updated_at": row.updated_at.isoformat()}


@router.post("/api/stats/dashboard/reset")
def reset_dashboard(
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    row = db.scalar(select(StatsDashboard).where(StatsDashboard.user_id == user.id))
    if row is not None:
        db.delete(row)
        db.commit()
    return {"widgets": _default_widgets(), "updated_at": None}
