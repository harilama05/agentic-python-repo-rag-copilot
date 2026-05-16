"""
Handles file uploads from the Streamlit UI or API.

Validates file size, extension, and content before saving to the uploads
directory.
"""

import shutil
from pathlib import Path
from typing import BinaryIO, Optional

from src.config import settings
from src.constants import ALLOWED_UPLOAD_EXTENSIONS, MAX_UPLOAD_SIZE_MB
from src.security.file_validator import validate_upload


def handle_upload(
    filename: str,
    file_obj: BinaryIO,
    sub_dir: Optional[str] = None,
) -> Path:
    """
    Save an uploaded file to the uploads directory.

    Args:
        filename: Original filename from the upload.
        file_obj: File-like binary object.
        sub_dir: Optional subdirectory inside uploads/.

    Returns:
        Path to the saved file.

    Raises:
        ValueError: If validation fails (bad extension, too large, etc.).
    """
    # Validate
    validate_upload(filename, file_obj)

    # Determine destination
    dest_dir = settings.uploads_dir
    if sub_dir:
        dest_dir = dest_dir / sub_dir
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_path = dest_dir / Path(filename).name

    # Save
    file_obj.seek(0)
    with open(dest_path, "wb") as out:
        shutil.copyfileobj(file_obj, out)

    return dest_path
