import os
import shutil
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.Communications import service
from app.schemas.communications import (
    AskResponse,
    DocumentResponse,
    MessageResponse,
    MessageSend,
    SessionCreate,
    SessionResponse,
)

router = APIRouter(prefix="/communications", tags=["Communications"])

UPLOAD_DIR = "uploads/documents"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post(
    "/documents/{business_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a PDF and ingest it into the business knowledge base",
)
async def upload_document(
    business_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        await service.ensure_business_exists(db, business_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    dest_path = os.path.join(UPLOAD_DIR, f"biz{business_id}_{file.filename}")
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        return await service.ingest_document(db, business_id, file.filename, dest_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")


@router.get(
    "/documents/{business_id}",
    response_model=List[DocumentResponse],
    summary="List uploaded documents for a business",
)
async def list_documents(
    business_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        await service.ensure_business_exists(db, business_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return await service.list_documents(db, business_id)


@router.delete(
    "/documents/{business_id}/{document_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a document for a business",
)
async def delete_document(
    business_id: int,
    document_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await service.delete_document(db, document_id, business_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Customer - Start a new chat session with a business",
)
async def create_session(
    payload: SessionCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await service.create_session(db, payload.business_id, payload.customer_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/ask",
    response_model=AskResponse,
    summary="Customer - Ask a question and get a RAG-grounded answer",
)
async def ask_question(
    payload: MessageSend,
    db: AsyncSession = Depends(get_db),
):
    try:
        assistant_msg = await service.ask(db, payload.session_id, payload.content)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {e}")

    return AskResponse(
        message_id=assistant_msg.id,
        session_id=assistant_msg.session_id,
        answer=assistant_msg.content,
        sources=assistant_msg.sources or [],
    )


@router.get(
    "/sessions/{session_id}/history",
    response_model=List[MessageResponse],
    summary="Customer - Get full conversation history",
)
async def get_history(
    session_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await service.get_session_history(db, session_id)
