"""Jams: synchronous listening sessions shared by several accounts."""

import asyncio
import hashlib
import json
import random
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.deps import current_user, db_session
from apps.api.models import Jam, JamParticipant, JamQueueItem, Session as UserSession, Track, User, normalize_utc
from apps.api.runtime import SessionLocal
from apps.api.serializers import track_to_dict, user_profile

router = APIRouter()

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class JamConnectionManager:
    def __init__(self):
        self.rooms: dict[str, set[WebSocket]] = {}
        self.users: dict[WebSocket, int] = {}

    async def connect(self, code: str, ws: WebSocket, user_id: int):
        # The endpoint accepts the socket first so it can read the auth message.
        self.rooms.setdefault(code, set()).add(ws)
        self.users[ws] = user_id

    def disconnect(self, code: str, ws: WebSocket):
        self.rooms.get(code, set()).discard(ws)
        self.users.pop(ws, None)

    async def broadcast(self, code: str, message: dict, exclude: WebSocket | None = None):
        for ws in list(self.rooms.get(code, ())):
            if ws is exclude:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                self.rooms.get(code, set()).discard(ws)


manager = JamConnectionManager()

# The WebSocket handlers own the event loop; HTTP handlers are sync functions that run
# in a worker thread, so they cannot schedule broadcasts themselves. Capturing the loop
# once lets them hand a message to it safely.
_loop: asyncio.AbstractEventLoop | None = None


def bind_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


def notify(coro) -> None:
    loop = _loop
    if loop is None or not loop.is_running():
        coro.close()
        return
    asyncio.run_coroutine_threadsafe(coro, loop)



def _new_code(db: Session) -> str:
    for _ in range(20):
        code = "".join(random.choice(CODE_ALPHABET) for _ in range(6))
        if not db.scalar(select(Jam).where(Jam.code == code)):
            return code
    raise HTTPException(status_code=500, detail="Could not generate a jam code")


def _get_jam(db: Session, code: str) -> Jam:
    jam = db.scalar(select(Jam).where(Jam.code == code.upper()))
    if not jam or jam.status != "active":
        raise HTTPException(status_code=404, detail="Jam not found or ended")
    return jam


def _participant(db: Session, jam: Jam, user: User) -> JamParticipant:
    row = db.scalar(
        select(JamParticipant).where(
            JamParticipant.jam_id == jam.id, JamParticipant.user_id == user.id
        )
    )
    if not row:
        raise HTTPException(status_code=403, detail="You are not in this jam")
    return row


def _state_payload(db: Session, jam: Jam) -> dict:
    participants = db.execute(
        select(JamParticipant, User)
        .join(User, User.id == JamParticipant.user_id)
        .where(JamParticipant.jam_id == jam.id)
        .order_by(JamParticipant.joined_at)
    ).all()
    queue = db.execute(
        select(JamQueueItem, Track)
        .join(Track, Track.id == JamQueueItem.track_id)
        .where(JamQueueItem.jam_id == jam.id)
        .order_by(JamQueueItem.position, JamQueueItem.id)
    ).all()
    track = db.get(Track, jam.current_track_id) if jam.current_track_id else None
    # Compute a live position so late joiners land on the right second.
    position = jam.position
    if jam.is_playing and jam.position_updated_at:
        elapsed = (datetime.now(timezone.utc) - normalize_utc(jam.position_updated_at)).total_seconds()
        position = max(0.0, position + elapsed)
    return {
        "code": jam.code,
        "host_user_id": jam.host_user_id,
        "current_track": track_to_dict(track, db.get(User, jam.host_user_id)) if track else None,
        "is_playing": jam.is_playing,
        "position": position,
        "participants": [user_profile(u) for _, u in participants],
        "queue": [
            {
                "id": item.id,
                "track": track_to_dict(t, db.get(User, jam.host_user_id)),
                "added_by": item.added_by,
            }
            for item, t in queue
        ],
    }


@router.post("/api/jams")
def create_jam(
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    code = _new_code(db)
    jam = Jam(code=code, host_user_id=user.id, position_updated_at=datetime.now(timezone.utc))
    db.add(jam)
    db.flush()
    db.add(JamParticipant(jam_id=jam.id, user_id=user.id))
    db.commit()
    db.refresh(jam)
    return {"code": jam.code, "state": _state_payload(db, jam)}


@router.post("/api/jams/join")
def join_jam(
    payload: dict,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    code = str(payload.get("code", "")).strip().upper()
    jam = _get_jam(db, code)
    existing = db.scalar(
        select(JamParticipant).where(
            JamParticipant.jam_id == jam.id, JamParticipant.user_id == user.id
        )
    )
    if not existing:
        db.add(JamParticipant(jam_id=jam.id, user_id=user.id))
        db.commit()
    # Broadcast the new participant list to everyone already in the room.
    notify(
        manager.broadcast(jam.code, {"type": "participants", "participants": _state_payload(db, jam)["participants"]})
    )
    return {"code": jam.code, "state": _state_payload(db, jam)}


@router.get("/api/jams/{code}")
def get_jam(
    code: str,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    jam = _get_jam(db, code)
    _participant(db, jam, user)
    return _state_payload(db, jam)


@router.post("/api/jams/{code}/queue")
def add_to_queue(
    code: str,
    payload: dict,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    jam = _get_jam(db, code)
    _participant(db, jam, user)
    track_id = payload.get("track_id")
    track = db.get(Track, track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    position = db.query(JamQueueItem).filter(JamQueueItem.jam_id == jam.id).count()
    item = JamQueueItem(jam_id=jam.id, track_id=track.id, position=position, added_by=user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    notify(
        manager.broadcast(
            jam.code,
            {"type": "queue_add", "item": {"id": item.id, "track": track_to_dict(track, user), "added_by": user.id}},
        )
    )
    return {"ok": True, "item_id": item.id}


@router.delete("/api/jams/{code}/queue/{item_id}")
def remove_from_queue(
    code: str,
    item_id: int,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    jam = _get_jam(db, code)
    _participant(db, jam, user)
    item = db.get(JamQueueItem, item_id)
    if not item or item.jam_id != jam.id:
        raise HTTPException(status_code=404, detail="Queue item not found")
    if item.added_by != user.id and jam.host_user_id != user.id:
        raise HTTPException(status_code=403, detail="Cannot remove this item")
    db.delete(item)
    db.commit()
    notify(
        manager.broadcast(jam.code, {"type": "queue_remove", "item_id": item_id})
    )
    return {"ok": True}


@router.post("/api/jams/{code}/control")
def control_jam(
    code: str,
    payload: dict,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    jam = _get_jam(db, code)
    _participant(db, jam, user)
    action = str(payload.get("action", "")).strip().lower()
    now = datetime.now(timezone.utc)
    if action == "play":
        track_id = payload.get("track_id")
        if track_id is not None:
            jam.current_track_id = track_id
        jam.is_playing = True
        jam.position = float(payload.get("position") or 0.0)
        jam.position_updated_at = now
    elif action == "pause":
        # Freeze the position at the moment of pausing.
        if jam.is_playing and jam.position_updated_at:
            elapsed = (now - normalize_utc(jam.position_updated_at)).total_seconds()
            jam.position = max(0.0, jam.position + elapsed)
        jam.is_playing = False
        jam.position_updated_at = now
    elif action == "seek":
        jam.position = float(payload.get("position") or 0.0)
        jam.position_updated_at = now
    elif action == "next":
        # Pick the first queued track and remove it.
        first = db.scalar(
            select(JamQueueItem)
            .where(JamQueueItem.jam_id == jam.id)
            .order_by(JamQueueItem.position, JamQueueItem.id)
        )
        if first:
            jam.current_track_id = first.track_id
            db.delete(first)
        jam.is_playing = True
        jam.position = 0.0
        jam.position_updated_at = now
    elif action == "stop_track":
        jam.current_track_id = None
        jam.is_playing = False
        jam.position = 0.0
        jam.position_updated_at = now
    else:
        raise HTTPException(status_code=400, detail="Unknown action")
    db.commit()
    db.refresh(jam)
    track = db.get(Track, jam.current_track_id) if jam.current_track_id else None
    host = db.get(User, jam.host_user_id)
    message = {
        "type": "control",
        "action": action,
        "by": user.id,
        "current_track": track_to_dict(track, host) if track else None,
        "is_playing": jam.is_playing,
        "position": jam.position,
    }
    notify(manager.broadcast(jam.code, message))
    return {"ok": True}


@router.post("/api/jams/{code}/end")
def end_jam(
    code: str,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    jam = _get_jam(db, code)
    if jam.host_user_id != user.id:
        raise HTTPException(status_code=403, detail="Only the host can end the jam")
    jam.status = "ended"
    db.commit()
    notify(
        manager.broadcast(jam.code, {"type": "ended"})
    )
    return {"ok": True}


@router.websocket("/ws/jam/{code}")
async def jam_websocket(websocket: WebSocket, code: str):
    # Sockets are the only place where the loop is guaranteed, so capture it here for
    # the sync HTTP handlers that broadcast.
    bind_loop(asyncio.get_running_loop())
    code = code.upper()
    # First message must authenticate.
    await websocket.accept()
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        auth = json.loads(raw)
    except Exception:
        await websocket.close(code=4401)
        return
    token = auth.get("token") if isinstance(auth, dict) else None
    if not token:
        await websocket.close(code=4401)
        return
    digest = hashlib.sha256(token.encode()).hexdigest()
    with SessionLocal() as db:
        session = db.scalar(select(UserSession).where(UserSession.token_hash == digest))
        now = datetime.now(timezone.utc)
        expires_at = normalize_utc(session.expires_at) if session else now
        if not session or expires_at <= now:
            await websocket.close(code=4401)
            return
        user = db.get(User, session.user_id)
        if not user:
            await websocket.close(code=4401)
            return
        jam = db.scalar(select(Jam).where(Jam.code == code, Jam.status == "active"))
        if not jam:
            await websocket.close(code=4404)
            return
        participant = db.scalar(
            select(JamParticipant).where(
                JamParticipant.jam_id == jam.id, JamParticipant.user_id == user.id
            )
        )
        if not participant:
            await websocket.close(code=4403)
            return
        user_id = user.id
    await manager.connect(code, websocket, user_id)
    # Send the current snapshot.
    with SessionLocal() as db:
        jam = db.scalar(select(Jam).where(Jam.code == code))
        if jam:
            await websocket.send_json({"type": "state", "state": _state_payload(db, jam)})
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            # Clients may send pings; ignore unknown messages.
            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(code, websocket)
        with SessionLocal() as db:
            jam = db.scalar(select(Jam).where(Jam.code == code))
            if jam:
                await manager.broadcast(
                    code,
                    {
                        "type": "participants",
                        "participants": _state_payload(db, jam)["participants"],
                    },
                )
