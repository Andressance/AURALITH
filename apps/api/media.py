"""Signed media URLs, image processing and storage streaming helpers."""

import asyncio
import logging
import secrets
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Callable

from fastapi import HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from PIL import Image, ImageOps
from starlette.concurrency import run_in_threadpool

from apps.api.core.security import media_signature, media_signature_expiry
from apps.api.models import Track, User
from apps.api.runtime import MEDIA_SECRET, MEDIA_URL_TTL_SECONDS, storage

logger = logging.getLogger(__name__)

image_processing_semaphore = asyncio.Semaphore(1)

async def upload_profile_image(file: UploadFile, key_prefix: str) -> tuple[str, str]:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_IMAGE_SUFFIXES:
        raise HTTPException(status_code=400, detail="Only JPG, PNG and WebP images are supported")
    content = await file.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image exceeds 5 MB")
    content_type = ALLOWED_IMAGE_SUFFIXES[suffix]
    if content_type == "image/jpeg" and not (content.startswith(b"\xff\xd8\xff")):
        raise HTTPException(status_code=400, detail="Invalid JPEG image")
    if content_type == "image/png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=400, detail="Invalid PNG image")
    if content_type == "image/webp" and not (len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP"):
        raise HTTPException(status_code=400, detail="Invalid WebP image")
    try:
        optimized_content = await optimize_image_with_limit(content)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    path = f"{key_prefix}/{secrets.token_hex(16)}.webp"
    storage.upload(path, optimized_content, "image/webp")
    return path, "image/webp"

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000
OPTIMIZED_IMAGE_SIZE = (512, 512)

def optimize_image(content: bytes) -> bytes:
    if not content or len(content) > MAX_IMAGE_BYTES:
        raise ValueError("Image exceeds the 5 MB limit")

    try:
        with Image.open(BytesIO(content)) as source:
            if source.width * source.height > MAX_IMAGE_PIXELS:
                raise ValueError("Image dimensions exceed the supported limit")
            image = ImageOps.exif_transpose(source)
            image.thumbnail(OPTIMIZED_IMAGE_SIZE, Image.Resampling.LANCZOS)
            mode = "RGBA" if "A" in image.getbands() or "transparency" in image.info else "RGB"
            image = image.convert(mode)
            output = BytesIO()
            image.save(output, format="WEBP", quality=80, method=4)
            return output.getvalue()
    except (Image.DecompressionBombError, OSError) as error:
        raise ValueError("Image is invalid or cannot be safely processed") from error


async def optimize_image_with_limit(content: bytes) -> bytes:
    async with image_processing_semaphore:
        return await run_in_threadpool(optimize_image, content)

def signed_media_query(user: User) -> str:
    expires_at = media_signature_expiry(MEDIA_URL_TTL_SECONDS)
    signature = media_signature(MEDIA_SECRET, user.id, expires_at)
    return f"uid={user.id}&exp={expires_at}&sig={signature}"


def versioned_image_url(url: str, revision: str | int | None, user: User) -> str | None:
    if revision is None:
        return None
    return f"{url}?v={revision}&{signed_media_query(user)}"


def stream_url_for(track: Track, user: User) -> str:
    return f"/api/tracks/{track.id}/stream?{signed_media_query(user)}"

def delete_replaced_image(previous_path: str | None, current_path: str) -> None:
    if not previous_path or previous_path == current_path:
        return
    try:
        storage.delete(previous_path)
    except Exception:
        logger.warning("Unable to remove replaced image: %s", previous_path, exc_info=True)


def is_missing_storage_object(error: Exception) -> bool:
    code = getattr(error, "response", {}).get("Error", {}).get("Code")
    return isinstance(error, (FileNotFoundError, KeyError)) or code in {
        "NoSuchKey",
        "404",
        "NotFound",
    }

async def image_response(
    path: str | None,
    not_found: str,
    save_path: Callable[[str], None],
):
    if not path:
        raise HTTPException(status_code=404, detail=not_found)

    if Path(path).suffix.lower() != ".webp":
        try:
            with storage.open(path) as source:
                content = source.read(MAX_IMAGE_BYTES + 1)
            optimized_content = await optimize_image_with_limit(content)
        except ValueError as error:
            logger.warning("Keeping legacy image %s without optimization: %s", path, error)
        except Exception as error:
            if is_missing_storage_object(error):
                raise HTTPException(status_code=404, detail=not_found) from error
            raise HTTPException(status_code=503, detail="Image temporarily unavailable") from error
        else:
            optimized_path = str(PurePosixPath(path).with_suffix(".webp"))
            try:
                storage.upload(optimized_path, optimized_content, "image/webp")
                save_path(optimized_path)
            except Exception as error:
                raise HTTPException(status_code=503, detail="Image temporarily unavailable") from error
            delete_replaced_image(path, optimized_path)
            return Response(
                content=optimized_content,
                media_type="image/webp",
                headers={"Cache-Control": "private, max-age=86400"},
            )

    try:
        suffix = Path(path).suffix.lower()
        media_type = ALLOWED_IMAGE_SUFFIXES.get(suffix, "application/octet-stream")
        source = storage.open(path)
        return StreamingResponse(
            source,
            media_type=media_type,
            headers={"Cache-Control": "private, max-age=86400"},
        )
    except Exception as error:
        if is_missing_storage_object(error):
            raise HTTPException(status_code=404, detail=not_found) from error
        raise HTTPException(status_code=503, detail="Image temporarily unavailable") from error

ALLOWED_SUFFIXES = {".mp3": "audio/mpeg", ".flac": "audio/flac"}
ALLOWED_IMAGE_SUFFIXES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}

def extract_cover(tags) -> tuple[bytes, str] | None:
    if not tags:
        return None
    try:
        for picture in getattr(tags, "pictures", []) or []:
            data = getattr(picture, "data", None)
            mime = getattr(picture, "mime", "")
            if data:
                suffix = ".jpg" if "jpeg" in mime else ".png" if "png" in mime else ".webp" if "webp" in mime else ".jpg"
                return data, suffix
    except Exception:
        pass
    try:
        apic_frames = tags.tags.getall("APIC") if hasattr(tags, "tags") and tags.tags else []
        for frame in apic_frames:
            if getattr(frame, "data", None):
                mime = getattr(frame, "mime", "")
                suffix = ".jpg" if "jpeg" in mime else ".png" if "png" in mime else ".webp" if "webp" in mime else ".jpg"
                return frame.data, suffix
    except Exception:
        pass
    return None

def iter_storage(provider, key: str, start: int, end: int, chunk_size: int = 256 * 1024):
    try:
        source = provider.open(key, start=start, end=end)
    except TypeError:
        source = provider.open(key)
    with source:
        remaining = end - start + 1
        while remaining:
            chunk = source.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk
