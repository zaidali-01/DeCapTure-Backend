import os
import shutil

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.chatbot import BusinessDocument
from app.schemas.chatbot import (
    DocumentResponse,
    SessionCreate,
    SessionResponse,
    MessageSend,
    MessageResponse,
    ReplyResponse,
)
from app.modules.Communications import service

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])

UPLOAD_DIR = "uploads/documents"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ── 1. Upload a PDF for a business ────────────────────────────────────────────

@router.post(
    "/documents/{business_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a PDF knowledge-base document for a business",
)
async def upload_document(
    business_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    dest_path = os.path.join(UPLOAD_DIR, f"{business_id}_{file.filename}")
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    doc = BusinessDocument(
        business_id=business_id,
        filename=file.filename,
        file_path=dest_path,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


# ── 2. Start a chat session ───────────────────────────────────────────────────

@router.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Open a new chat session for a customer",
)
async def create_session(
    payload: SessionCreate,
    db: AsyncSession = Depends(get_db),
):
    session = await service.create_session(
        db, payload.business_id, payload.customer_name
    )
    return session


# ── 3. Customer sends a message ───────────────────────────────────────────────

@router.post(
    "/message",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Customer sends a message — returns the saved message with its id",
)
async def send_message(
    payload: MessageSend,
    db: AsyncSession = Depends(get_db),
):
    msg = await service.save_user_message(db, payload.session_id, payload.content)
    return msg


# ── 4. Chatbot generates and returns a reply ──────────────────────────────────

@router.post(
    "/reply/{message_id}",
    response_model=ReplyResponse,
    summary="Chatbot reads the PDFs and replies to the given user message",
)
async def get_reply(
    message_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        assistant_msg = await service.generate_reply(db, message_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return ReplyResponse(
        message_id=assistant_msg.id,
        session_id=assistant_msg.session_id,
        reply=assistant_msg.content,
    )