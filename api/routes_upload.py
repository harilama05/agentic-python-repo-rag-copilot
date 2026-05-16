"""
Upload API routes.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File

router = APIRouter(prefix="/api/upload", tags=["upload"])


@router.post("/file")
async def upload_file(file: UploadFile = File(...)):
    """Upload and index a single file."""
    try:
        from src.ingestion.upload_handler import handle_upload

        saved_path = handle_upload(
            filename=file.filename or "unknown.py",
            file_obj=file.file,
        )

        return {
            "status": "uploaded",
            "filename": file.filename,
            "saved_path": str(saved_path),
        }

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
