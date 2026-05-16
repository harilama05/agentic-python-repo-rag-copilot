"""
Upload file validation — checks size, extension, and basic content safety.
"""

from pathlib import Path
from typing import BinaryIO

from src.constants import ALLOWED_UPLOAD_EXTENSIONS, MAX_UPLOAD_SIZE_MB


def validate_upload(filename: str, file_obj: BinaryIO) -> None:
    """
    Validate an uploaded file.

    Raises ``ValueError`` if the file fails any check.
    """
    # Check extension
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        raise ValueError(
            f"Unsupported file extension: {suffix}. "
            f"Allowed: {', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}"
        )

    # Check size
    file_obj.seek(0, 2)  # Seek to end
    size_bytes = file_obj.tell()
    file_obj.seek(0)

    max_bytes = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if size_bytes > max_bytes:
        raise ValueError(
            f"File too large: {size_bytes / 1024 / 1024:.1f} MB "
            f"(max {MAX_UPLOAD_SIZE_MB} MB)"
        )

    # Check for null bytes (possible binary file)
    sample = file_obj.read(8192)
    file_obj.seek(0)

    if b"\x00" in sample:
        raise ValueError("File appears to be binary — only text files are allowed.")
