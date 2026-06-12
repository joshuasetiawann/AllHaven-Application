"""Drive router: local file upload/list/download/soft-delete (workspace-scoped)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_principal
from app.core.database import get_db
from app.core.principal import Principal
from app.core.responses import success_response
from app.schemas.drive import DriveConfigOut, DriveFileOut
from app.services import drive_service as svc

router = APIRouter(prefix="/drive", tags=["drive"])

# Content types a browser could render/execute inline. We serve them as a plain
# download (octet-stream + attachment) so an uploaded .html/.svg can't run.
_RISKY_CONTENT_TYPES = {
    "text/html", "application/xhtml+xml", "image/svg+xml",
    "text/xml", "application/xml", "application/javascript", "text/javascript",
}


@router.get("/config")
def get_config() -> dict:
    return success_response(
        DriveConfigOut(max_upload_bytes=svc.upload_limit_bytes(), max_upload_mb=svc.upload_limit_mb()),
        "Drive config",
    )


@router.get("/files")
def list_files(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    files = svc.list_files(db, principal)
    return success_response([DriveFileOut.model_validate(f) for f in files], "Drive files")


@router.post("/files")
async def upload_file(
    file: UploadFile = File(...),
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    data = await file.read()
    row = svc.save_file(
        db, principal,
        filename=file.filename or "file",
        content_type=file.content_type or "application/octet-stream",
        data=data,
    )
    return success_response(DriveFileOut.model_validate(row), "File uploaded")


@router.get("/files/{file_id}/download")
def download_file(
    file_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> FileResponse:
    row, abs_path = svc.resolve_path(db, principal, file_id)
    # Force download and neutralize active types to prevent inline XSS.
    media = "application/octet-stream" if row.content_type in _RISKY_CONTENT_TYPES else row.content_type
    return FileResponse(abs_path, filename=row.filename, media_type=media, content_disposition_type="attachment")


@router.delete("/files/{file_id}")
def delete_file(
    file_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    svc.delete_file(db, principal, file_id)
    return success_response({"id": str(file_id)}, "File deleted")
