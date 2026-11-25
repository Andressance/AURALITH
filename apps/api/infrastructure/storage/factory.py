"""Build storage providers from the environment.

``AURALITH_STORAGE_PROVIDERS`` accepts a JSON list to run several backends at
once (replicated writes, fallback reads)::

    AURALITH_STORAGE_PROVIDERS='[
      {"type": "gdrive", "refresh_token": "...", "folder_id": "..."},
      {"type": "gdrive", "refresh_token": "...", "folder_id": "..."},
      {"type": "neon"}
    ]'

Each entry only needs ``type``; any field left out falls back to the provider's
own environment variables. ``AURALITH_STORAGE_PROVIDER`` keeps working for a
single backend.
"""

import json
import os
from pathlib import Path

from apps.api.infrastructure.storage.composite import MultiStorageProvider
from apps.api.infrastructure.storage.gdrive import GoogleDriveStorageProvider
from apps.api.infrastructure.storage.local import LocalStorageProvider
from apps.api.infrastructure.storage.s3 import S3StorageProvider
from apps.api.infrastructure.storage.supabase import SupabaseStorageProvider

SUPPORTED_OPTIONS = {
    "local": ("root",),
    "supabase": ("url", "service_key", "bucket"),
    "neon": ("endpoint", "access_key", "secret_key", "bucket", "region"),
    "gdrive": (
        "client_id",
        "client_secret",
        "refresh_token",
        "folder_id",
        "api_base",
        "upload_base",
        "token_url",
    ),
}


def build_provider(spec, default_local_root):
    if isinstance(spec, str):
        spec = {"type": spec}
    if not isinstance(spec, dict):
        raise RuntimeError(
            "Each AURALITH_STORAGE_PROVIDERS entry must be an object or a provider name"
        )
    type_name = str(spec.get("type", "")).strip().lower()
    if type_name not in SUPPORTED_OPTIONS:
        supported = ", ".join(sorted(SUPPORTED_OPTIONS))
        raise RuntimeError(
            f"Unknown storage provider '{type_name}'; use one of: {supported}"
        )
    unknown = set(spec) - {"type"} - set(SUPPORTED_OPTIONS[type_name])
    if unknown:
        raise RuntimeError(
            f"Unknown options for the {type_name} provider: {', '.join(sorted(unknown))}"
        )
    options = {name: value for name, value in spec.items() if name != "type"}
    if type_name == "local":
        return LocalStorageProvider(options.get("root") or default_local_root)
    if type_name == "supabase":
        return SupabaseStorageProvider(**options)
    if type_name == "neon":
        return S3StorageProvider(**options)
    return GoogleDriveStorageProvider(**options)


def local_storage_root(provider):
    """Return the filesystem root when the provider is a single local backend."""
    if isinstance(provider, LocalStorageProvider):
        return Path(provider.root)
    return None


def build_storage_provider(default_local_root):
    raw = os.getenv("AURALITH_STORAGE_PROVIDERS", "").strip()
    if not raw:
        single = os.getenv("AURALITH_STORAGE_PROVIDER", "local").strip().lower()
        return build_provider(single, default_local_root)
    try:
        specs = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"AURALITH_STORAGE_PROVIDERS must be valid JSON ({error})"
        ) from error
    if isinstance(specs, dict):
        specs = [specs]
    if not isinstance(specs, list) or not specs:
        raise RuntimeError("AURALITH_STORAGE_PROVIDERS must be a non-empty JSON list")
    providers = [build_provider(spec, default_local_root) for spec in specs]
    if len(providers) == 1:
        return providers[0]
    mirror = os.getenv("AURALITH_STORAGE_MIRROR", "true").strip().lower() != "false"
    return MultiStorageProvider(providers, mirror=mirror)
