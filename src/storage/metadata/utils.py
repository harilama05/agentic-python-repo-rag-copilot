import hashlib
from datetime import datetime, timezone
from typing import Any

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def make_stable_chunk_id(
    repo_id: str,
    relative_path: str,
    start_line: int | None,
    end_line: int | None,
    text: str,
) -> str:
    raw = f"{repo_id}:{relative_path}:{start_line}:{end_line}:{text}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()

def get_chunk_text(chunk: Any) -> str:
    return (
        getattr(chunk, "text", None)
        or getattr(chunk, "content", None)
        or getattr(chunk, "code", None)
        or ""
    )

def get_chunk_metadata(chunk: Any) -> dict[str, Any]:
    metadata = getattr(chunk, "metadata", None)
    if isinstance(metadata, dict):
        return metadata
    return {}

def get_metadata_value(
    metadata: dict[str, Any],
    *keys: str,
    default: Any = None,
) -> Any:
    for key in keys:
        value = metadata.get(key)
        if value is not None:
            return value
    return default


def sanitize_postgres_text(value: Any) -> Any:
    """Remove NUL bytes because PostgreSQL TEXT/VARCHAR fields cannot store them."""
    if isinstance(value, str):
        return value.replace("\x00", "")
    return value

def sanitize_postgres_text_or_empty(value: Any) -> str:
    """Return a NUL-free string, using an empty string for None."""
    if value is None:
        return ""
    return str(value).replace("\x00", "")
