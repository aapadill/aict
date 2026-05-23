from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.storage import Case, Document, JsonRepository, repository

ALLOWED_UPLOAD_EXTENSIONS = {".md", ".pdf", ".txt"}

router = APIRouter(prefix="/cases", tags=["cases"])


class CaseCreateRequest(BaseModel):
    title: str = Field(min_length=1)
    description: str | None = None


class DocumentResponse(BaseModel):
    id: str
    case_id: str
    filename: str
    content_type: str
    file_path: str
    status: str
    extracted_text_path: str | None
    created_at: str


class CaseResponse(BaseModel):
    id: str
    title: str
    description: str | None
    created_at: str
    updated_at: str


class CaseDetailResponse(CaseResponse):
    documents: list[DocumentResponse]


def get_repository() -> JsonRepository:
    return repository


def _case_response(case: Case) -> CaseResponse:
    return CaseResponse(
        id=case.id,
        title=case.title,
        description=case.description,
        created_at=case.createdat,
        updated_at=case.updatedat,
    )


def _document_response(document: Document) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        case_id=document.caseid,
        filename=document.filename,
        content_type=document.contenttype,
        file_path=document.filepath,
        status=document.status,
        extracted_text_path=document.extractedtextpath,
        created_at=document.createdat,
    )


def _case_detail_response(case: Case, documents: list[Document]) -> CaseDetailResponse:
    case_payload = _case_response(case)
    return CaseDetailResponse(
        **case_payload.model_dump(),
        documents=[_document_response(document) for document in documents],
    )


def _api_error(status_code: int, error: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "error": error,
            "message": message,
        },
    )


def _require_case(repo: JsonRepository, case_id: str) -> Case:
    case = repo.get_case(case_id)
    if case is None:
        raise _api_error(
            status.HTTP_404_NOT_FOUND,
            "case_not_found",
            f"Case '{case_id}' was not found.",
        )
    return case


def _safe_upload_filename(upload: UploadFile) -> str:
    raw_filename = (upload.filename or "").replace("\\", "/")
    filename = Path(raw_filename).name
    if not filename or filename in {".", ".."}:
        raise _api_error(
            status.HTTP_400_BAD_REQUEST,
            "invalid_filename",
            "Uploaded files must include a valid filename.",
        )
    return filename


def _validate_uploads(files: list[UploadFile]) -> list[str]:
    if not files:
        raise _api_error(
            status.HTTP_400_BAD_REQUEST,
            "missing_files",
            "Upload at least one .pdf, .txt, or .md file.",
        )

    filenames: list[str] = []
    for upload in files:
        filename = _safe_upload_filename(upload)
        extension = Path(filename).suffix.lower()
        if extension not in ALLOWED_UPLOAD_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_UPLOAD_EXTENSIONS))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "unsupported_file_type",
                    "message": f"Unsupported file type for '{filename}'. Allowed extensions: {allowed}.",
                    "filename": filename,
                    "allowed_extensions": sorted(ALLOWED_UPLOAD_EXTENSIONS),
                },
            )
        filenames.append(filename)
    return filenames


@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(
    request: CaseCreateRequest,
    repo: JsonRepository = Depends(get_repository),
) -> CaseResponse:
    title = request.title.strip()
    description = request.description.strip() if request.description else None
    if not title:
        raise _api_error(
            status.HTTP_400_BAD_REQUEST,
            "invalid_title",
            "Case title cannot be blank.",
        )

    case = repo.create_case(title=title, description=description)
    return _case_response(case)


@router.get("", response_model=list[CaseResponse])
def list_cases(repo: JsonRepository = Depends(get_repository)) -> list[CaseResponse]:
    return [_case_response(case) for case in repo.list_cases()]


@router.get("/{case_id}", response_model=CaseDetailResponse)
def get_case(
    case_id: str,
    repo: JsonRepository = Depends(get_repository),
) -> CaseDetailResponse:
    case = _require_case(repo, case_id)
    return _case_detail_response(case, repo.list_documents(case_id))


@router.post(
    "/{case_id}/documents",
    response_model=list[DocumentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def upload_documents(
    case_id: str,
    files: list[UploadFile] = File(...),
    repo: JsonRepository = Depends(get_repository),
) -> list[DocumentResponse]:
    _require_case(repo, case_id)
    filenames = _validate_uploads(files)
    case_upload_dir = repo.upload_dir / case_id

    try:
        case_upload_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise _api_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "file_save_failed",
            "Failed to prepare the upload directory.",
        ) from exc

    saved_documents: list[Document] = []
    for upload, filename in zip(files, filenames, strict=True):
        document_id = f"doc_{uuid.uuid4().hex}"
        target_path = case_upload_dir / f"{document_id}_{filename}"

        try:
            content = await upload.read()
            target_path.write_bytes(content)
            saved_documents.append(
                repo.save_document(
                    case_id=case_id,
                    filename=filename,
                    content_type=upload.content_type,
                    file_path=target_path,
                    status="uploaded",
                    document_id=document_id,
                )
            )
        except OSError as exc:
            raise _api_error(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "file_save_failed",
                f"Failed to save uploaded file '{filename}'.",
            ) from exc
        except Exception as exc:
            raise _api_error(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "document_metadata_save_failed",
                f"Failed to persist metadata for uploaded file '{filename}'.",
            ) from exc

    return [_document_response(document) for document in saved_documents]


@router.get("/{case_id}/documents", response_model=list[DocumentResponse])
def list_case_documents(
    case_id: str,
    repo: JsonRepository = Depends(get_repository),
) -> list[DocumentResponse]:
    _require_case(repo, case_id)
    return [_document_response(document) for document in repo.list_documents(case_id)]
