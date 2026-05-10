import os
import shutil
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.modules.Communications import service
from app.modules.Users.service import get_current_user, get_current_user_optional, has_role
from app.schemas.communications import (
    AskResponse,
    ChatbotCreate,
    ChatbotResponse,
    ChatbotUpdate,
    DocumentResponse,
    EscalationCreate,
    EscalationResponse,
    HumanMessageSend,
    MessageResponse,
    MessageSend,
    SessionCreate,
    SessionResponse,
    SessionSummaryResponse,
)

router = APIRouter(prefix="/communications", tags=["Communications"])

UPLOAD_DIR = "uploads/documents"
os.makedirs(UPLOAD_DIR, exist_ok=True)


async def ensure_business_access(db: AsyncSession, user_id: int, business_id: int):
    allowed = await has_role(db, user_id, business_id, ["business_owner", "manager"])
    if not allowed:
        raise HTTPException(status_code=403, detail="Not allowed")


@router.post(
    "/documents/{business_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a PDF and ingest it into the business knowledge base",
)
async def upload_document(
    business_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_business_access(db, current_user.id, business_id)
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
        return await service.ingest_document_for_business(db, business_id, file.filename, dest_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")


@router.get(
    "/documents/{business_id}",
    response_model=List[DocumentResponse],
    summary="List uploaded documents for a business",
)
async def list_documents(
    business_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_business_access(db, current_user.id, business_id)
    try:
        await service.ensure_business_exists(db, business_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return await service.list_documents_for_business(db, business_id)


@router.delete(
    "/documents/{business_id}/{document_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a document for a business",
)
async def delete_document(
    business_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_business_access(db, current_user.id, business_id)
    try:
        return await service.delete_document_for_business(db, document_id, business_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/chatbots",
    response_model=List[ChatbotResponse],
    summary="List chatbots for a business",
)
async def list_chatbots(
    business_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_business_access(db, current_user.id, business_id)
    try:
        return await service.list_chatbots(db, business_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/chatbots",
    response_model=ChatbotResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a chatbot for a business",
)
async def create_chatbot(
    payload: ChatbotCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_business_access(db, current_user.id, payload.business_id)
    try:
        return await service.create_chatbot(db, payload.business_id, payload.name, payload.system_prompt)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put(
    "/chatbots/{chatbot_id}",
    response_model=ChatbotResponse,
    summary="Update chatbot metadata",
)
async def update_chatbot(
    chatbot_id: int,
    payload: ChatbotUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        chatbot = await service.get_chatbot(db, chatbot_id)
        await ensure_business_access(db, current_user.id, chatbot.business_id)
        return await service.update_chatbot(db, chatbot_id, payload.name, payload.system_prompt)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete(
    "/chatbots/{chatbot_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a chatbot",
)
async def delete_chatbot(
    chatbot_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        chatbot = await service.get_chatbot(db, chatbot_id)
        await ensure_business_access(db, current_user.id, chatbot.business_id)
        return await service.delete_chatbot(db, chatbot_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/chatbots/{chatbot_id}/select-store",
    response_model=ChatbotResponse,
    summary="Select one chatbot as the public store bot",
)
async def select_store_chatbot(
    chatbot_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        chatbot = await service.get_chatbot(db, chatbot_id)
        await ensure_business_access(db, current_user.id, chatbot.business_id)
        return await service.select_store_chatbot(db, chatbot_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/public/businesses/{business_id}/store-bot",
    response_model=Optional[ChatbotResponse],
    summary="Get the selected public store bot for a business",
)
async def public_store_bot(
    business_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await service.get_store_chatbot_for_business(db, business_id)


@router.post(
    "/chatbots/{chatbot_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a PDF and ingest it into a chatbot knowledge base",
)
async def upload_chatbot_document(
    chatbot_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        chatbot = await service.get_chatbot(db, chatbot_id)
        await ensure_business_access(db, current_user.id, chatbot.business_id)
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are accepted")

        dest_path = os.path.join(UPLOAD_DIR, f"bot{chatbot_id}_{file.filename}")
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        return await service.ingest_document(db, chatbot_id, file.filename, dest_path)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")


@router.get(
    "/chatbots/{chatbot_id}/documents",
    response_model=List[DocumentResponse],
    summary="List uploaded documents for a chatbot",
)
async def list_chatbot_documents(
    chatbot_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        chatbot = await service.get_chatbot(db, chatbot_id)
        await ensure_business_access(db, current_user.id, chatbot.business_id)
        return await service.list_documents(db, chatbot_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/chatbots/{chatbot_id}/sessions",
    response_model=List[SessionSummaryResponse],
    summary="List all sessions for a chatbot",
)
async def list_chatbot_sessions(
    chatbot_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        chatbot = await service.get_chatbot(db, chatbot_id)
        await ensure_business_access(db, current_user.id, chatbot.business_id)
        return await service.list_chatbot_sessions(db, chatbot_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete(
    "/chatbots/{chatbot_id}/documents/{document_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a document for a chatbot",
)
async def delete_chatbot_document(
    chatbot_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        chatbot = await service.get_chatbot(db, chatbot_id)
        await ensure_business_access(db, current_user.id, chatbot.business_id)
        return await service.delete_document(db, document_id, chatbot_id)
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
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await service.create_session(
            db,
            payload.business_id,
            payload.chatbot_id,
            payload.customer_name,
            current_user.id if current_user else None,
        )
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


@router.get(
    "/sessions/me",
    response_model=List[SessionSummaryResponse],
    summary="List sessions for the logged-in customer",
)
async def list_my_sessions(
    business_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_customer_sessions(db, current_user.id, business_id)


@router.post(
    "/escalate",
    response_model=EscalationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Customer - Request a human agent",
)
async def escalate(
    payload: EscalationCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await service.request_escalation(db, payload.session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/escalations/{business_id}",
    response_model=List[EscalationResponse],
    summary="Agent - List pending/active escalations for a business",
)
async def list_escalations(
    business_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_pending_escalations(db, business_id)


@router.post(
    "/escalations/{escalation_id}/claim",
    response_model=EscalationResponse,
    summary="Agent - Claim an escalation and join the session",
)
async def claim(
    escalation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await service.claim_escalation(db, escalation_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/human-message",
    response_model=MessageResponse,
    summary="Send a message from customer or agent during live escalation",
)
async def human_message(
    payload: HumanMessageSend,
    db: AsyncSession = Depends(get_db),
):
    try:
        msg = await service.send_human_message(
            db, payload.session_id, payload.content, payload.role
        )
        return msg
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/escalations/{escalation_id}/close",
    response_model=EscalationResponse,
    summary="Agent - Close a live escalation session",
)
async def close(
    escalation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await service.close_escalation(db, escalation_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/escalations/session/{session_id}",
    summary="Customer - Check if an escalation exists for this session",
)
async def escalation_status(
    session_id: int,
    db: AsyncSession = Depends(get_db),
):
    esc = await service.get_escalation_by_session(db, session_id)
    if not esc:
        return {"status": "none"}
    return EscalationResponse.model_validate(esc)
