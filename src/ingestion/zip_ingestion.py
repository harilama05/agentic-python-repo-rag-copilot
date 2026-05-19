"""
ZIP repository ingestion.

This module validates and extracts an uploaded ZIP archive, finds the likely
repository root, traverses it, and returns only files accepted by the repository
indexing pipeline.
"""

import hashlib
import re
import shutil
import zipfile
from pathlib import Path

from src.config import settings
from src.ingestion.repository_files import PreparedRepository, prepare_local_repository


MAX_ZIP_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_ZIP_FILES = 5000
RUNTIME_ZIP_DIR = settings.uploads_dir / "zip_repositories"


def _sanitize_name(name: str) -> str:
    name = name.strip()

    if not name:
        return "uploaded_repo"

    name = Path(name).stem
    name = re.sub(r"[^a-zA-Z0-9_]+", "_", name)
    name = name.strip("_").lower()

    return name or "uploaded_repo"


def make_zip_repo_id(filename: str, zip_bytes: bytes) -> str:
    safe_name = _sanitize_name(filename)
    digest = hashlib.sha1(zip_bytes).hexdigest()[:10]

    return f"zip_{safe_name}_{digest}"


def _validate_zip_members(zip_file: zipfile.ZipFile) -> None:
    members = zip_file.infolist()

    if len(members) > MAX_ZIP_FILES:
        raise ValueError(
            f"ZIP contains too many files: {len(members)} > {MAX_ZIP_FILES}"
        )

    total_size = 0

    for member in members:
        total_size += member.file_size

        if total_size > MAX_ZIP_UNCOMPRESSED_BYTES:
            raise ValueError(
                "ZIP is too large after extraction. "
                f"Limit: {MAX_ZIP_UNCOMPRESSED_BYTES // (1024 * 1024)} MB"
            )

        member_name = member.filename.replace("\\", "/")

        if member_name.startswith("/") or ".." in Path(member_name).parts:
            raise ValueError(f"Unsafe ZIP path detected: {member.filename}")


def _safe_extract(zip_file: zipfile.ZipFile, extract_dir: Path) -> None:
    """Safely extract a ZIP file and prevent Zip Slip path traversal."""
    extract_dir = extract_dir.resolve()

    for member in zip_file.infolist():
        member_name = member.filename.replace("\\", "/")

        if not member_name or member_name.endswith("/"):
            continue

        if member_name.startswith("__MACOSX/"):
            continue

        target_path = (extract_dir / member_name).resolve()

        if not str(target_path).startswith(str(extract_dir)):
            raise ValueError(f"Unsafe ZIP path detected: {member.filename}")

        target_path.parent.mkdir(parents=True, exist_ok=True)

        with zip_file.open(member) as source, target_path.open("wb") as target:
            shutil.copyfileobj(source, target)


def _find_repo_root(extract_dir: Path) -> Path:
    """
    Find the likely repo root after extraction.

    Many repository ZIP files contain a single top-level folder. In that case,
    return that folder; otherwise return the extraction directory.
    """
    visible_children = [
        path
        for path in extract_dir.iterdir()
        if path.name not in {"__MACOSX", ".DS_Store"}
    ]

    directories = [path for path in visible_children if path.is_dir()]
    files = [path for path in visible_children if path.is_file()]

    if len(directories) == 1 and not files:
        return directories[0]

    return extract_dir


def ingest_zip_bytes(
    filename: str,
    zip_bytes: bytes,
    force_refresh: bool = True,
) -> PreparedRepository:
    """
    Extract a ZIP archive and prepare its supported files for indexing.

    Only .txt, .py, .json, and .md files are included in the returned
    PreparedRepository.
    """
    if not filename.lower().endswith(".zip"):
        raise ValueError("Only .zip files are supported.")

    if not zip_bytes:
        raise ValueError("Uploaded ZIP file is empty.")

    repo_id = make_zip_repo_id(filename, zip_bytes)
    safe_name = _sanitize_name(filename)

    target_dir = RUNTIME_ZIP_DIR / repo_id
    extract_dir = target_dir / "extracted"
    zip_path = target_dir / "source.zip"

    RUNTIME_ZIP_DIR.mkdir(parents=True, exist_ok=True)

    if target_dir.exists() and force_refresh:
        shutil.rmtree(target_dir)

    target_dir.mkdir(parents=True, exist_ok=True)
    zip_path.write_bytes(zip_bytes)

    try:
        with zipfile.ZipFile(zip_path, "r") as zip_file:
            _validate_zip_members(zip_file)
            _safe_extract(zip_file, extract_dir)
    except zipfile.BadZipFile as exc:
        raise ValueError("Uploaded file is not a valid ZIP archive.") from exc

    repo_root = _find_repo_root(extract_dir)

    return prepare_local_repository(
        repo_root,
        repo_id=repo_id,
        name=safe_name,
        metadata={
            "source_type": "zip",
            "original_filename": filename,
        },
    )


def ingest_zip_path(
    zip_path: str | Path,
    force_refresh: bool = True,
) -> PreparedRepository:
    zip_path = Path(zip_path)
    zip_bytes = zip_path.read_bytes()

    return ingest_zip_bytes(
        filename=zip_path.name,
        zip_bytes=zip_bytes,
        force_refresh=force_refresh,
    )
