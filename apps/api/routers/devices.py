"""Devices: which signed-in browsers of one account are playing, and relaying commands between them.

The server only tracks presence and forwards messages between sockets of the same account.
Playback itself happens in the browser that owns the audio element.
"""

import asyncio
import hashlib
import json
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from apps.api.models import Session as UserSession, User, normalize_utc
from apps.api.runtime import SessionLocal

router = APIRouter()

# shortcut: presence lives in process memory, so it resets on restart and needs one API worker.
# Upgrade to a shared store (Redis or the database) when the API runs on several instances.
sockets: dict[int, dict[str, WebSocket]] = {}
presence: dict[str, dict] = {}


def _user_for_token(token: str | None) -> int | None:
    if not token:
        return None
    digest = hashlib.sha256(token.encode()).hexdigest()
    with SessionLocal() as db:
        session = db.scalar(select(UserSession).where(UserSession.token_hash == digest))
        if not session or normalize_utc(session.expires_at) <= datetime.now(timezone.utc):
            return None
        user = db.get(User, session.user_id)
        return user.id if user else None


def _device_list(user_id: int) -> list[dict]:
    return [
        {"device_id": device_id, **presence.get(device_id, {})}
        for device_id in sockets.get(user_id, {})
    ]


async def _publish(user_id: int) -> None:
    message = {"type": "devices", "devices": _device_list(user_id)}
    for ws in list(sockets.get(user_id, {}).values()):
        try:
            await ws.send_json(message)
        except Exception:
            pass


def _clean_track(track) -> dict | None:
    # Only the summary goes to other devices; the full track is sent on handoff.
    if not isinstance(track, dict) or track.get("id") is None:
        return None
    return {
        "id": track.get("id"),
        "title": str(track.get("title") or "")[:200],
        "artist": str(track.get("artist") or "")[:200],
        "cover_url": track.get("cover_url") if isinstance(track.get("cover_url"), str) else None,
    }


@router.websocket("/ws/devices")
async def devices_websocket(websocket: WebSocket):
    await websocket.accept()
    try:
        auth = json.loads(await asyncio.wait_for(websocket.receive_text(), timeout=10.0))
    except Exception:
        await websocket.close(code=4401)
        return
    if not isinstance(auth, dict):
        await websocket.close(code=4401)
        return
    user_id = _user_for_token(auth.get("token"))
    device_id = str(auth.get("device_id") or "")[:64]
    if user_id is None or not device_id:
        await websocket.close(code=4401)
        return

    sockets.setdefault(user_id, {})[device_id] = websocket
    presence[device_id] = {
        "name": str(auth.get("name") or "Dispositivo")[:60],
        "track": None,
        "is_playing": False,
        "position": 0.0,
    }
    await _publish(user_id)
    try:
        while True:
            try:
                message = json.loads(await websocket.receive_text())
            except json.JSONDecodeError:
                continue
            if not isinstance(message, dict):
                continue
            kind = message.get("type")
            if kind == "presence":
                is_playing = bool(message.get("is_playing"))
                presence[device_id].update(
                    track=_clean_track(message.get("track")),
                    is_playing=is_playing,
                    position=float(message.get("position") or 0.0),
                )
                if is_playing:
                    # One sound per profile, like a streaming app: the device that just
                    # started playing takes over and the others pause.
                    for other_id, other_ws in list(sockets.get(user_id, {}).items()):
                        if other_id == device_id or not presence.get(other_id, {}).get("is_playing"):
                            continue
                        presence[other_id]["is_playing"] = False
                        try:
                            await other_ws.send_json(
                                {"type": "relay", "from": device_id, "message": {"cmd": "pause"}}
                            )
                        except Exception:
                            pass
                await _publish(user_id)
            elif kind == "relay":
                # Only forward to another device on the same account.
                target = sockets.get(user_id, {}).get(str(message.get("target", "")))
                if target and isinstance(message.get("message"), dict):
                    try:
                        await target.send_json(
                            {"type": "relay", "from": device_id, "message": message["message"]}
                        )
                    except Exception:
                        pass
            elif kind == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        if sockets.get(user_id, {}).get(device_id) is websocket:
            del sockets[user_id][device_id]
            presence.pop(device_id, None)
            if not sockets[user_id]:
                del sockets[user_id]
            await _publish(user_id)
