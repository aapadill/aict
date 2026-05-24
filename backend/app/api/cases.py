from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.agents.workflow import AnalysisWorkflowError, latest_analysis_result, run_analysis_workflow
from app.models.analysis import LIMITATION_NOTICE, AnalysisResult, Citation
from app.services.chat import ChatWorkflowError, answer_follow_up
from app.storage import Analysis, Case, Document, JsonRepository, Message, repository

ALLOWED_UPLOAD_EXTENSIONS = {".md", ".pdf", ".txt"}

router = APIRouter(prefix="/cases", tags=["cases"])


class CaseCreateRequest(BaseModel):
    title: str = Field(min_length=1)
    description: str | None = None


class CaseUpdateRequest(BaseModel):
    title: str | None = None
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


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


class ChatResponse(BaseModel):
    role: str
    content: str
    citations: list[Citation]
    new_facts_detected: list[str]
    reassessment_recommended: bool


class MessageResponse(BaseModel):
    id: str
    case_id: str
    role: str
    content: str
    citations: list[Citation]
    created_at: str


class AnalysisRevisionResponse(BaseModel):
    id: str
    case_id: str
    status: str
    created_at: str
    updated_at: str
    revision: int
    active: bool
    summary: str
    risk_label: str
    risk_conclusion: str
    confidence: str


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


def _message_response(message: Message) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        case_id=message.caseid,
        role=message.role,
        content=message.content,
        citations=[Citation.model_validate(citation) for citation in message.citations],
        created_at=message.createdat,
    )


def _analysis_result(analysis: Analysis) -> AnalysisResult:
    result = AnalysisResult.model_validate(analysis.result)
    return result.model_copy(update={"limitation_notice": LIMITATION_NOTICE})


def _risk_label(conclusion: str) -> str:
    text = conclusion.lower()
    if "prohibited" in text:
        return "Prohibited"
    if "high-risk" in text or "high risk" in text:
        return "High risk"
    if "limited" in text or "transparency" in text:
        return "Limited risk"
    if "minimal" in text or "low" in text:
        return "Low risk"
    return "Needs review"


def _analysis_revision_response(
    analysis: Analysis,
    *,
    revision: int,
    active_analysis_id: str | None,
) -> AnalysisRevisionResponse:
    try:
        result = _analysis_result(analysis)
        summary = result.summary
        risk_conclusion = result.risk_classification.conclusion
        confidence = result.risk_classification.confidence
    except Exception:
        summary = ""
        risk_conclusion = ""
        confidence = "unknown"

    return AnalysisRevisionResponse(
        id=analysis.id,
        case_id=analysis.caseid,
        status=analysis.status,
        created_at=analysis.createdat,
        updated_at=analysis.updated_at,
        revision=revision,
        active=analysis.id == active_analysis_id,
        summary=summary,
        risk_label=_risk_label(risk_conclusion),
        risk_conclusion=risk_conclusion,
        confidence=confidence,
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


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(
    case_id: str,
    repo: JsonRepository = Depends(get_repository),
) -> None:
    if not repo.delete_case(case_id):
        raise _api_error(
            status.HTTP_404_NOT_FOUND,
            "case_not_found",
            f"Case '{case_id}' was not found.",
        )


@router.patch("/{case_id}", response_model=CaseResponse)
def update_case(
    case_id: str,
    request: CaseUpdateRequest,
    repo: JsonRepository = Depends(get_repository),
) -> CaseResponse:
    existing_case = _require_case(repo, case_id)
    title = request.title.strip() if request.title is not None else None
    description = request.description.strip() if request.description is not None else None
    if request.title is not None and not title:
        raise _api_error(
            status.HTTP_400_BAD_REQUEST,
            "invalid_title",
            "Case title cannot be blank.",
        )
    if (
        request.description is not None
        and repo.get_latest_analysis(case_id) is not None
        and description != (existing_case.description or "")
    ):
        raise _api_error(
            status.HTTP_409_CONFLICT,
            "case_locked",
            "Use-case description is locked after analysis has been generated.",
        )

    case = repo.update_case(case_id, title=title, description=description)
    if case is None:
        raise _api_error(
            status.HTTP_404_NOT_FOUND,
            "case_not_found",
            f"Case '{case_id}' was not found.",
        )
    return _case_response(case)


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
    if repo.get_latest_analysis(case_id) is not None:
        raise _api_error(
            status.HTTP_409_CONFLICT,
            "case_locked",
            "Document uploads are locked after analysis has been generated.",
        )
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


@router.delete("/{case_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case_document(
    case_id: str,
    document_id: str,
    repo: JsonRepository = Depends(get_repository),
) -> None:
    _require_case(repo, case_id)
    if repo.get_latest_analysis(case_id) is not None:
        raise _api_error(
            status.HTTP_409_CONFLICT,
            "case_locked",
            "Unlock the case before removing documents.",
        )
    if not repo.delete_document(case_id, document_id):
        raise _api_error(
            status.HTTP_404_NOT_FOUND,
            "document_not_found",
            f"Document '{document_id}' was not found for case '{case_id}'.",
        )


@router.post("/{case_id}/analyze", response_model=AnalysisResult)
def analyze_case(
    case_id: str,
    repo: JsonRepository = Depends(get_repository),
) -> AnalysisResult:
    try:
        return run_analysis_workflow(case_id, repo=repo)
    except AnalysisWorkflowError as exc:
        if exc.code == "case_not_found":
            raise _api_error(status.HTTP_404_NOT_FOUND, exc.code, exc.message) from exc
        if exc.code == "no_documents":
            raise _api_error(status.HTTP_400_BAD_REQUEST, exc.code, exc.message) from exc
        if exc.code == "llm_not_configured":
            raise _api_error(status.HTTP_422_UNPROCESSABLE_ENTITY, exc.code, exc.message) from exc
        if exc.code == "llm_call_failed":
            raise _api_error(status.HTTP_502_BAD_GATEWAY, exc.code, exc.message) from exc
        raise _api_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            exc.code,
            exc.message,
        ) from exc


@router.get("/{case_id}/analysis", response_model=AnalysisResult)
def get_case_analysis(
    case_id: str,
    repo: JsonRepository = Depends(get_repository),
) -> AnalysisResult:
    _require_case(repo, case_id)
    result = latest_analysis_result(case_id, repo=repo)
    if result is None:
        raise _api_error(
            status.HTTP_404_NOT_FOUND,
            "analysis_not_found",
            f"No saved analysis exists for case '{case_id}'.",
        )
    return result


@router.get("/{case_id}/analyses", response_model=list[AnalysisRevisionResponse])
def list_case_analyses(
    case_id: str,
    repo: JsonRepository = Depends(get_repository),
) -> list[AnalysisRevisionResponse]:
    _require_case(repo, case_id)
    active_analysis_id = repo.get_active_analysis_id(case_id)
    return [
        _analysis_revision_response(
            analysis,
            revision=index,
            active_analysis_id=active_analysis_id,
        )
        for index, analysis in enumerate(repo.list_analyses(case_id), start=1)
    ]


@router.get("/{case_id}/analyses/{analysis_id}", response_model=AnalysisResult)
def get_case_analysis_revision(
    case_id: str,
    analysis_id: str,
    repo: JsonRepository = Depends(get_repository),
) -> AnalysisResult:
    _require_case(repo, case_id)
    analysis = repo.get_analysis(case_id, analysis_id)
    if analysis is None:
        raise _api_error(
            status.HTTP_404_NOT_FOUND,
            "analysis_not_found",
            f"Analysis revision '{analysis_id}' was not found for case '{case_id}'.",
        )
    return _analysis_result(analysis)


@router.delete("/{case_id}/analysis", status_code=status.HTTP_204_NO_CONTENT)
def unlock_case_analysis(
    case_id: str,
    repo: JsonRepository = Depends(get_repository),
) -> None:
    _require_case(repo, case_id)
    repo.clear_analysis_state(case_id)


@router.post("/{case_id}/chat", response_model=ChatResponse)
def chat_with_case(
    case_id: str,
    request: ChatRequest,
    repo: JsonRepository = Depends(get_repository),
) -> ChatResponse:
    try:
        result = answer_follow_up(case_id=case_id, message=request.message, repo=repo)
    except ChatWorkflowError as exc:
        if exc.code in {"case_not_found", "analysis_not_found"}:
            raise _api_error(status.HTTP_404_NOT_FOUND, exc.code, exc.message) from exc
        if exc.code == "empty_message":
            raise _api_error(status.HTTP_400_BAD_REQUEST, exc.code, exc.message) from exc
        if exc.code == "llm_not_configured":
            raise _api_error(status.HTTP_422_UNPROCESSABLE_ENTITY, exc.code, exc.message) from exc
        if exc.code == "llm_call_failed":
            raise _api_error(status.HTTP_502_BAD_GATEWAY, exc.code, exc.message) from exc
        raise _api_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            exc.code,
            "Chat response could not be completed.",
        ) from exc

    return ChatResponse(
        role=result.role,
        content=result.content,
        citations=result.citations,
        new_facts_detected=result.new_facts_detected,
        reassessment_recommended=result.reassessment_recommended,
    )


@router.get("/{case_id}/messages", response_model=list[MessageResponse])
def list_case_messages(
    case_id: str,
    repo: JsonRepository = Depends(get_repository),
) -> list[MessageResponse]:
    _require_case(repo, case_id)
    return [_message_response(message) for message in repo.list_messages(case_id)]
