"""Liveness endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.deps import db_session

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/api/health")
def health(db: Annotated[Session, Depends(db_session)]):
    try:
        db.execute(text("SELECT 1"))
    except Exception as error:
        logger.error("Health check could not reach the database: %s", error)
        raise HTTPException(status_code=503, detail="Database unavailable") from error
    return {"status": "ok"}

@router.get("/health")
def health_alias():
    return {"status": "ok"}
