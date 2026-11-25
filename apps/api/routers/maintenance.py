"""Owner backup and restore endpoints (local storage and SQLite only)."""

import logging
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from apps.api.deps import current_user, db_session, require_owner
from apps.api.models import User
from apps.api.runtime import (
    BASE_DIR,
    STORAGE_DIR,
    database,
    engine,
    storage_provider_name,
)

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/api/backup")
def create_backup(user: Annotated[User, Depends(current_user)]):
    require_owner(user)
    sqlite_path = database.sqlite_path
    # A ZIP without the database is not a backup, so refuse instead of returning a
    # partial archive that would look like one.
    if storage_provider_name != "local" or sqlite_path is None:
        raise HTTPException(
            status_code=400,
            detail="Backup requires local storage and a SQLite database",
        )
    backup_path = BASE_DIR / f"auralith-backup-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.zip"
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as handle:
        snapshot_path = Path(handle.name)
    try:
        # Copy through SQLite's backup API instead of the raw file: a plain file copy
        # can catch a half-written page and produce an archive that will not open.
        source = sqlite3.connect(sqlite_path)
        snapshot = sqlite3.connect(snapshot_path)
        try:
            source.backup(snapshot)
        finally:
            snapshot.close()
            source.close()
        with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot_path, "auralith.db")
            for path in STORAGE_DIR.rglob("*"):
                if path.is_file():
                    # POSIX member names keep Windows-made archives restorable.
                    relative = path.relative_to(STORAGE_DIR).as_posix()
                    archive.write(path, f"music/{relative}")
    finally:
        snapshot_path.unlink(missing_ok=True)
    # Remove the archive once it has been sent: it is a full copy of the library.
    return FileResponse(
        backup_path,
        media_type="application/zip",
        filename=backup_path.name,
        background=BackgroundTask(backup_path.unlink, missing_ok=True),
    )

@router.post("/api/restore")
async def restore_backup(
    file: UploadFile,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(db_session)],
):
    require_owner(user)
    sqlite_path = database.sqlite_path
    if storage_provider_name != "local" or sqlite_path is None:
        raise HTTPException(
            status_code=400,
            detail="Restore requires local storage and a SQLite database",
        )
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Backup must be a ZIP file")
    content = await file.read(1024 * 1024 * 1024)
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as temp:
        temp.write(content)
        temp_path = Path(temp.name)
    try:
        with zipfile.ZipFile(temp_path) as archive:
            names = set(archive.namelist())
            if "auralith.db" not in names:
                raise HTTPException(status_code=400, detail="Invalid backup: database is missing")
            total_size = sum(info.file_size for info in archive.infolist())
            if total_size > 1024 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="Backup exceeds 1 GB")
            for member in archive.namelist():
                normalized = Path(member.replace("\\", "/"))
                if normalized.is_absolute() or ".." in normalized.parts:
                    raise HTTPException(status_code=400, detail="Invalid backup: unsafe path")
            sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            # Release every pooled connection before replacing the file: SQLite keeps
            # using the old inode otherwise, and Windows cannot replace an open file.
            db.close()
            engine.dispose()
            with archive.open("auralith.db") as source, sqlite_path.open("wb") as target:
                shutil.copyfileobj(source, target)
            shutil.rmtree(STORAGE_DIR)
            STORAGE_DIR.mkdir(parents=True, exist_ok=True)
            for member in archive.namelist():
                if not member.startswith("music/") or member.endswith("/"):
                    continue
                relative = Path(member).relative_to("music")
                destination = STORAGE_DIR / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, destination.open("wb") as target:
                    shutil.copyfileobj(source, target)
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid ZIP backup")
    finally:
        temp_path.unlink(missing_ok=True)
    engine.dispose()
    return {"ok": True, "message": "Backup restored. Restart the API if playback does not resume."}
