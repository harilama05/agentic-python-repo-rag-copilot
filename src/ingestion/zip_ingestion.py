import hashlib
import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

from src.config import RUNTIME_UPLOADS_DIR


MAX_ZIP_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_ZIP_FILES = 5000


@dataclass
class IngestedZipRepo:
    repo_id: str
    name: str
    original_filename: str
    local_path: Path


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
    """
    Safely extract a ZIP file and prevent Zip Slip path traversal.
    """
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

    Many ZIP files contain a single top-level folder:
    repo-main/
      src/
      README.md

    In that case, return repo-main.
    Otherwise, return extract_dir.
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


def _validate_python_repo(repo_root: Path) -> None:
    python_files = list(repo_root.rglob("*.py"))
    markdown_files = list(repo_root.rglob("*.md"))

    if not python_files and not markdown_files:
        raise ValueError(
            "The uploaded ZIP does not look like a Python repository. "
            "No .py or .md files were found."
        )


def ingest_zip_bytes(
    filename: str,
    zip_bytes: bytes,
    force_refresh: bool = True,
) -> IngestedZipRepo:
    if not filename.lower().endswith(".zip"):
        raise ValueError("Only .zip files are supported.")

    if not zip_bytes:
        raise ValueError("Uploaded ZIP file is empty.")

    repo_id = make_zip_repo_id(filename, zip_bytes)
    safe_name = _sanitize_name(filename)

    target_dir = RUNTIME_UPLOADS_DIR / repo_id
    extract_dir = target_dir / "extracted"
    zip_path = target_dir / "source.zip"

    RUNTIME_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

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
    _validate_python_repo(repo_root)

    return IngestedZipRepo(
        repo_id=repo_id,
        name=safe_name,
        original_filename=filename,
        local_path=repo_root,
    )


def ingest_zip_path(
    zip_path: str | Path,
    force_refresh: bool = True,
) -> IngestedZipRepo:
    zip_path = Path(zip_path)
    zip_bytes = zip_path.read_bytes()

    return ingest_zip_bytes(
        filename=zip_path.name,
        zip_bytes=zip_bytes,
        force_refresh=force_refresh,
    )