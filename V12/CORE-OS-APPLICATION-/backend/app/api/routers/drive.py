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
from app.schemas.drive import DriveFileOut
from app.services import drive_service as svc

router = APIRouter(prefix="/drive", tags=["drive"])


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
    return FileResponse(abs_path, filename=row.filename, media_type=row.content_type)


@router.delete("/files/{file_id}")
def delete_file(
    file_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    svc.delete_file(db, principal, file_id)
    return success_response({"id": str(file_id)}, "File deleted")
