import csv
import math
import re
import unicodedata
from difflib import SequenceMatcher
from io import StringIO


MAX_CSV_BYTES = 2 * 1024 * 1024
MAX_CSV_ROWS = 500
MAX_FIELD_LENGTH = 300
ISRC_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{3}[0-9]{7}$")

FIELD_ALIASES = {
    "title": {"title", "track", "tracktitle", "trackname", "song", "songname", "name"},
    "artist": {"artist", "artists", "artistnames", "performer"},
    "album": {"album", "albumname", "release"},
    "duration": {"duration", "durationseconds", "durationms", "length"},
    "isrc": {"isrc", "recordingcode"},
    "position": {"position", "tracknumber", "trackno", "index"},
}


def normalize_text(value: str | None) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    without_marks = "".join(
        character for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(
        "".join(character if character.isalnum() else " " for character in without_marks.casefold()).split()
    )


def normalize_isrc(value: str | None) -> str | None:
    normalized = re.sub(r"[\s-]", "", value or "").upper()
    return normalized if ISRC_PATTERN.fullmatch(normalized) else None


def _clean_cell(value: str | None) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[\x00-\x1f\x7f]", "", value).strip()[:MAX_FIELD_LENGTH]


def _duration_seconds(value: str | None, header: str) -> int | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        if ":" in value:
            parts = [int(part) for part in value.split(":")]
            if len(parts) not in {2, 3} or any(part < 0 for part in parts):
                raise ValueError
            seconds = parts[-1] + parts[-2] * 60
            if len(parts) == 3:
                seconds += parts[0] * 3600
        else:
            numeric = float(value)
            if not math.isfinite(numeric):
                raise ValueError
            seconds = round(numeric / 1000) if header == "durationms" or numeric > 10000 else round(numeric)
        if seconds < 0 or seconds > 24 * 60 * 60:
            raise ValueError
        return seconds
    except ValueError as error:
        raise ValueError("CSV contains an invalid duration") from error


def parse_playlist_csv(content: bytes) -> list[dict]:
    if len(content) > MAX_CSV_BYTES:
        raise ValueError("CSV file exceeds the 2 MB limit")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("CSV must use UTF-8 encoding") from error
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise ValueError("CSV must include a header row")
    headers = {
        re.sub(r"[^a-z0-9]", "", (header or "").casefold()): header
        for header in reader.fieldnames
    }
    columns = {
        field: next((headers[alias] for alias in aliases if alias in headers), None)
        for field, aliases in FIELD_ALIASES.items()
    }
    if not columns["title"]:
        raise ValueError("CSV must include a Title or Track column")

    rows = []
    for row_number, raw in enumerate(reader, start=2):
        if len(rows) >= MAX_CSV_ROWS:
            raise ValueError("CSV may contain at most 500 tracks")
        if not raw or not any(_clean_cell(value) for value in raw.values()):
            continue
        title = _clean_cell(raw.get(columns["title"]))
        artist = _clean_cell(raw.get(columns["artist"])) if columns["artist"] else ""
        album = _clean_cell(raw.get(columns["album"])) if columns["album"] else ""
        isrc_value = _clean_cell(raw.get(columns["isrc"])) if columns["isrc"] else ""
        isrc = normalize_isrc(isrc_value) if isrc_value else None
        duration_value = _clean_cell(raw.get(columns["duration"])) if columns["duration"] else ""
        duration = _duration_seconds(
            duration_value,
            re.sub(r"[^a-z0-9]", "", columns["duration"].casefold()) if columns["duration"] else "",
        )
        position_value = _clean_cell(raw.get(columns["position"])) if columns["position"] else ""
        try:
            position = int(position_value) if position_value else row_number
            if position < 0:
                raise ValueError
        except ValueError as error:
            raise ValueError(f"CSV has an invalid position on row {row_number}") from error
        rows.append({
            "row": row_number,
            "title": title,
            "artist": artist,
            "album": album,
            "duration": duration,
            "isrc": isrc,
            "invalid_isrc": bool(isrc_value and not isrc),
            "position": position,
        })
    return rows


def _version_markers(value: str) -> set[str]:
    markers = {
        "acoustic", "demo", "extended", "instrumental", "live", "mix",
        "radio", "remaster", "remastered", "remix",
    }
    return set(normalize_text(value).split()) & markers


def match_playlist_rows(rows: list[dict], tracks: list) -> list[dict]:
    by_isrc: dict[str, list] = {}
    by_title_artist: dict[tuple[str, str], list] = {}
    by_artist: dict[str, list] = {}
    by_title: dict[str, list] = {}
    for track in tracks:
        title = normalize_text(track.title)
        artist = normalize_text(track.artist)
        isrc = normalize_isrc(getattr(track, "isrc", None))
        if isrc:
            by_isrc.setdefault(isrc, []).append(track)
        by_title_artist.setdefault((title, artist), []).append(track)
        by_artist.setdefault(artist, []).append(track)
        by_title.setdefault(title, []).append(track)

    results = []
    seen_rows = set()
    for row in sorted(rows, key=lambda item: (item["position"], item["row"])):
        title = normalize_text(row["title"])
        artist = normalize_text(row["artist"])
        album = normalize_text(row["album"])
        duplicate_key = row["isrc"] or (title, artist, row["duration"])
        result = {
            "row": row["row"],
            "title": row["title"],
            "artist": row["artist"],
            "status": "UNMATCHED",
            "track_id": None,
            "candidate": None,
        }
        if not row["title"] or row["invalid_isrc"]:
            result["status"] = "INVALID"
        elif duplicate_key in seen_rows:
            result["status"] = "DUPLICATE"
        else:
            seen_rows.add(duplicate_key)
            isrc_matches = by_isrc.get(row["isrc"], []) if row["isrc"] else []
            exact_matches = isrc_matches or by_title_artist.get((title, artist), [])
            candidates = exact_matches
            if exact_matches:
                ranked = sorted(
                    exact_matches,
                    key=lambda track: (
                        0 if row["duration"] is not None and track.duration == row["duration"] else 1,
                        0 if album and normalize_text(track.album) == album else 1,
                    ),
                )
                chosen = ranked[0]
                ambiguous = (
                    len(ranked) > 1
                    and row["duration"] is None
                    and not album
                    and not row["isrc"]
                )
                duration_differs = (
                    row["duration"] is not None
                    and chosen.duration is not None
                    and abs(chosen.duration - row["duration"]) > 2
                )
                album_differs = bool(
                    album and chosen.album and normalize_text(chosen.album) != album
                )
                version_differs = _version_markers(row["title"]) != _version_markers(chosen.title)
                result["candidate"] = _candidate(chosen)
                if row["isrc"] and chosen in isrc_matches:
                    result["status"] = "EXACT"
                    result["track_id"] = chosen.id
                elif not ambiguous and not duration_differs and not album_differs and not version_differs:
                    result["status"] = "EXACT"
                    result["track_id"] = chosen.id
                else:
                    result["status"] = "REVIEW_REQUIRED"
            else:
                candidates = by_artist.get(artist, []) if artist else []
                if not candidates:
                    candidates = by_title.get(title, [])
                scored = []
                for track in candidates:
                    title_score = SequenceMatcher(None, title, normalize_text(track.title)).ratio()
                    artist_score = SequenceMatcher(None, artist, normalize_text(track.artist)).ratio() if artist else 0
                    if title_score >= 0.78 and (not artist or artist_score >= 0.88):
                        score = title_score * 0.75 + (artist_score * 0.25 if artist else 0)
                        scored.append((score, track))
                scored.sort(key=lambda item: item[0], reverse=True)
                if scored:
                    best_score, best_track = scored[0]
                    result["candidate"] = _candidate(best_track)
                    tied = len(scored) > 1 and abs(scored[0][0] - scored[1][0]) < 0.02
                    same_artist = bool(artist and artist == normalize_text(best_track.artist))
                    same_title = title == normalize_text(best_track.title)
                    duration_matches = (
                        row["duration"] is None
                        or best_track.duration is None
                        or abs(best_track.duration - row["duration"]) <= 2
                    )
                    version_matches = _version_markers(row["title"]) == _version_markers(best_track.title)
                    if best_score >= 0.96 and same_artist and same_title and duration_matches and version_matches and not tied:
                        result["status"] = "EXACT"
                        result["track_id"] = best_track.id
                    elif best_score >= 0.78:
                        result["status"] = (
                            "HIGH_CONFIDENCE"
                            if best_score >= 0.88 and not tied and duration_matches and version_matches
                            else "REVIEW_REQUIRED"
                        )
        results.append(result)
    return results


def _candidate(track) -> dict:
    return {
        "id": track.id,
        "title": track.title,
        "artist": track.artist,
        "album": track.album,
        "duration": track.duration,
    }
