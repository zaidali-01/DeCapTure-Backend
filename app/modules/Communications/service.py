import os
import uuid
from datetime import datetime as _dt

import httpx as _httpx
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.business import Business
from app.models.communications import (
    BusinessChatbot,
    BusinessDocument,
    CommunicationMessage,
    CommunicationSession,
    EscalationRequest,
)
from app.modules.Communications.rag.chroma_client import (
    delete_document_chunks,
    get_collection,
)
from app.modules.Communications.rag.chunker import chunk_text
from app.modules.Communications.rag.embedder import embed_batch
from app.modules.Communications.rag.extractor import extract_text_from_pdf
from app.modules.Communications.rag.retriever import retrieve_relevant_chunks


DEFAULT_CHATBOT_NAME = "Primary Assistant"


def get_groq_client():
    if not settings.GROQ_API_KEY:
        return None

    try:
        from groq import Groq
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "groq is required for chatbot responses. "
            "Install project dependencies with `pip install -r requirements.txt`."
        ) from exc

    return Groq(api_key=settings.GROQ_API_KEY)


async def ensure_business_exists(db: AsyncSession, business_id: int) -> Business:
    result = await db.execute(select(Business).where(Business.id == business_id))
    business = result.scalar_one_or_none()
    if not business:
        raise ValueError("Business not found")
    return business


async def _index_document_chunks(
    *,
    business_id: int,
    chatbot_id: int,
    document_id: int,
    file_path: str,
) -> int:
    raw_text = extract_text_from_pdf(file_path)
    chunks = chunk_text(raw_text, chunk_size=500, overlap=50)
    if not chunks:
        return 0

    embeddings = embed_batch(chunks)
    collection = get_collection(business_id)
    collection.add(
        ids=[str(uuid.uuid4()) for _ in chunks],
        documents=chunks,
        embeddings=embeddings,
        metadatas=[
            {
                "document_id": document_id,
                "business_id": business_id,
                "chatbot_id": chatbot_id,
                "chunk_index": i,
            }
            for i in range(len(chunks))
        ],
    )
    return len(chunks)


async def _migrate_unassigned_documents(
    db: AsyncSession,
    business_id: int,
    chatbot_id: int,
) -> None:
    result = await db.execute(
        select(BusinessDocument).where(
            BusinessDocument.business_id == business_id,
            BusinessDocument.chatbot_id.is_(None),
        )
    )
    legacy_docs = result.scalars().all()
    for doc in legacy_docs:
        if not os.path.exists(doc.file_path):
            doc.chatbot_id = chatbot_id
            db.add(doc)
            continue

        try:
            chunk_count = await _index_document_chunks(
                business_id=business_id,
                chatbot_id=chatbot_id,
                document_id=doc.id,
                file_path=doc.file_path,
            )
            doc.chunk_count = chunk_count
        except Exception:
            # Keep the legacy document available in DB even if re-indexing fails.
            pass
        doc.chatbot_id = chatbot_id
        db.add(doc)

    if legacy_docs:
        await db.commit()


async def ensure_default_chatbot(
    db: AsyncSession,
    business_id: int,
) -> BusinessChatbot:
    await ensure_business_exists(db, business_id)
    result = await db.execute(
        select(BusinessChatbot).where(BusinessChatbot.business_id == business_id).order_by(BusinessChatbot.id.asc())
    )
    chatbot = result.scalars().first()
    if chatbot:
        await _migrate_unassigned_documents(db, business_id, chatbot.id)
        return chatbot

    chatbot = BusinessChatbot(
        business_id=business_id,
        name=DEFAULT_CHATBOT_NAME,
        system_prompt=None,
        is_store_bot=False,
    )
    db.add(chatbot)
    await db.commit()
    await db.refresh(chatbot)
    await _migrate_unassigned_documents(db, business_id, chatbot.id)
    return chatbot


async def get_chatbot(
    db: AsyncSession,
    chatbot_id: int,
) -> BusinessChatbot:
    chatbot = await db.get(BusinessChatbot, chatbot_id)
    if not chatbot:
        raise ValueError("Chatbot not found")
    return chatbot


async def list_chatbots(
    db: AsyncSession,
    business_id: int,
):
    await ensure_default_chatbot(db, business_id)
    result = await db.execute(
        select(BusinessChatbot)
        .where(BusinessChatbot.business_id == business_id)
        .order_by(BusinessChatbot.id.asc())
    )
    return result.scalars().all()


async def create_chatbot(
    db: AsyncSession,
    business_id: int,
    name: str,
    system_prompt: str | None = None,
) -> BusinessChatbot:
    await ensure_business_exists(db, business_id)
    chatbot = BusinessChatbot(
        business_id=business_id,
        name=name,
        system_prompt=system_prompt,
        is_store_bot=False,
    )
    db.add(chatbot)
    await db.commit()
    await db.refresh(chatbot)
    return chatbot


async def update_chatbot(
    db: AsyncSession,
    chatbot_id: int,
    name: str | None = None,
    system_prompt: str | None = None,
) -> BusinessChatbot:
    chatbot = await get_chatbot(db, chatbot_id)
    if name is not None:
        chatbot.name = name
    if system_prompt is not None:
        chatbot.system_prompt = system_prompt
    db.add(chatbot)
    await db.commit()
    await db.refresh(chatbot)
    return chatbot


async def delete_chatbot(
    db: AsyncSession,
    chatbot_id: int,
) -> dict:
    chatbot = await get_chatbot(db, chatbot_id)
    result = await db.execute(
        select(BusinessChatbot).where(
            BusinessChatbot.business_id == chatbot.business_id,
            BusinessChatbot.id != chatbot.id,
        )
    )
    remaining = result.scalars().all()
    if not remaining:
        raise HTTPException(status_code=400, detail="At least one chatbot must remain for the business")

    doc_result = await db.execute(
        select(BusinessDocument).where(BusinessDocument.chatbot_id == chatbot_id)
    )
    docs = doc_result.scalars().all()
    for doc in docs:
        delete_document_chunks(chatbot.business_id, doc.id)
        await db.delete(doc)

    session_result = await db.execute(
        select(CommunicationSession).where(CommunicationSession.chatbot_id == chatbot_id)
    )
    sessions = session_result.scalars().all()
    fallback_chatbot = remaining[0]
    for session in sessions:
        session.chatbot_id = fallback_chatbot.id
        session.business_id = fallback_chatbot.business_id
        db.add(session)

    await db.delete(chatbot)
    await db.commit()
    return {"message": "Chatbot deleted successfully"}


async def select_store_chatbot(
    db: AsyncSession,
    chatbot_id: int,
) -> BusinessChatbot:
    chatbot = await get_chatbot(db, chatbot_id)
    await db.execute(
        update(BusinessChatbot)
        .where(BusinessChatbot.business_id == chatbot.business_id)
        .values(is_store_bot=False)
    )
    chatbot.is_store_bot = True
    db.add(chatbot)
    await db.commit()
    await db.refresh(chatbot)
    return chatbot


async def get_store_chatbot_for_business(
    db: AsyncSession,
    business_id: int,
) -> BusinessChatbot | None:
    result = await db.execute(
        select(BusinessChatbot).where(
            BusinessChatbot.business_id == business_id,
            BusinessChatbot.is_store_bot.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def ingest_document(
    db: AsyncSession,
    chatbot_id: int,
    filename: str,
    file_path: str,
) -> BusinessDocument:
    chatbot = await get_chatbot(db, chatbot_id)

    doc = BusinessDocument(
        business_id=chatbot.business_id,
        chatbot_id=chatbot.id,
        filename=filename,
        file_path=file_path,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    chunk_count = await _index_document_chunks(
        business_id=chatbot.business_id,
        chatbot_id=chatbot.id,
        document_id=doc.id,
        file_path=file_path,
    )

    doc.chunk_count = chunk_count
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


async def ingest_document_for_business(
    db: AsyncSession,
    business_id: int,
    filename: str,
    file_path: str,
) -> BusinessDocument:
    chatbot = await ensure_default_chatbot(db, business_id)
    return await ingest_document(db, chatbot.id, filename, file_path)


async def list_documents(db: AsyncSession, chatbot_id: int):
    await get_chatbot(db, chatbot_id)
    result = await db.execute(
        select(BusinessDocument)
        .where(BusinessDocument.chatbot_id == chatbot_id)
        .order_by(BusinessDocument.id.desc())
    )
    return result.scalars().all()


async def list_documents_for_business(db: AsyncSession, business_id: int):
    chatbot = await ensure_default_chatbot(db, business_id)
    return await list_documents(db, chatbot.id)


async def delete_document(db: AsyncSession, document_id: int, chatbot_id: int):
    chatbot = await get_chatbot(db, chatbot_id)
    result = await db.execute(
        select(BusinessDocument).where(
            BusinessDocument.id == document_id,
            BusinessDocument.chatbot_id == chatbot_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise ValueError("Document not found")

    delete_document_chunks(chatbot.business_id, document_id)

    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    await db.delete(doc)
    await db.commit()
    return {"message": f"'{doc.filename}' deleted"}


async def delete_document_for_business(db: AsyncSession, document_id: int, business_id: int):
    chatbot = await ensure_default_chatbot(db, business_id)
    return await delete_document(db, document_id, chatbot.id)


async def create_session(
    db: AsyncSession,
    business_id: int | None,
    chatbot_id: int | None,
    customer_name: str | None,
    customer_user_id: int | None = None,
) -> CommunicationSession:
    selected_chatbot: BusinessChatbot | None = None
    if chatbot_id:
        selected_chatbot = await get_chatbot(db, chatbot_id)
    elif business_id:
        selected_chatbot = await ensure_default_chatbot(db, business_id)
    else:
        raise ValueError("Business or chatbot is required")

    session = CommunicationSession(
        business_id=selected_chatbot.business_id,
        chatbot_id=selected_chatbot.id,
        customer_user_id=customer_user_id,
        customer_name=customer_name,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def list_customer_sessions(
    db: AsyncSession,
    customer_user_id: int,
    business_id: int | None = None,
):
    conditions = [CommunicationSession.customer_user_id == customer_user_id]
    if business_id is not None:
        conditions.append(CommunicationSession.business_id == business_id)

    result = await db.execute(
        select(CommunicationSession)
        .where(*conditions)
        .order_by(CommunicationSession.id.desc())
    )
    sessions = result.scalars().all()
    return await _serialize_sessions(db, sessions)


async def list_chatbot_sessions(
    db: AsyncSession,
    chatbot_id: int,
):
    await get_chatbot(db, chatbot_id)
    result = await db.execute(
        select(CommunicationSession)
        .where(CommunicationSession.chatbot_id == chatbot_id)
        .order_by(CommunicationSession.id.desc())
    )
    sessions = result.scalars().all()
    return await _serialize_sessions(db, sessions)


async def _serialize_sessions(
    db: AsyncSession,
    sessions: list[CommunicationSession],
):
    summaries = []
    for session in sessions:
        message_result = await db.execute(
            select(CommunicationMessage)
            .where(CommunicationMessage.session_id == session.id)
            .order_by(CommunicationMessage.id.desc())
            .limit(1)
        )
        last_message = message_result.scalar_one_or_none()
        escalation = await get_escalation_by_session(db, session.id)
        summaries.append(
            {
                "id": session.id,
                "business_id": session.business_id,
                "chatbot_id": session.chatbot_id,
                "customer_user_id": session.customer_user_id,
                "customer_name": session.customer_name,
                "created_at": session.created_at,
                "last_message": last_message.content if last_message else None,
                "last_message_at": last_message.created_at if last_message else None,
                "escalation_status": escalation.status if escalation else "none",
            }
        )
    return summaries


def _isoformat(value):
    return value.isoformat() if value else None


def _build_message_event(
    event_type: str,
    message: CommunicationMessage,
    escalation: EscalationRequest | None = None,
) -> dict:
    payload = {
        "event_type": event_type,
        "session_id": message.session_id,
        "message_id": message.id,
        "role": message.role,
        "content": message.content,
        "sources": message.sources or [],
        "created_at": _isoformat(message.created_at),
    }

    if escalation is not None:
        payload["escalation"] = {
            "id": escalation.id,
            "business_id": escalation.business_id,
            "status": escalation.status,
            "agent_user_id": escalation.agent_user_id,
            "requested_at": _isoformat(escalation.requested_at),
            "resolved_at": _isoformat(escalation.resolved_at),
        }

    return payload


async def _commit_and_refresh_message(
    db: AsyncSession,
    message: CommunicationMessage,
) -> CommunicationMessage:
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message


async def _create_system_message(
    db: AsyncSession,
    session_id: int,
    content: str,
) -> CommunicationMessage:
    return await _commit_and_refresh_message(
        db,
        CommunicationMessage(
            session_id=session_id,
            role="system",
            content=content,
        ),
    )


def _to_provider_role(role: str) -> str:
    """
    Translate internal chat roles into provider-safe chat completion roles.
    We keep richer roles in our own database, but only send supported values
    back to the model when resuming a mixed bot/human conversation.
    """
    normalized = (role or "").strip().lower()
    if normalized in {"user", "assistant", "system"}:
        return normalized
    if normalized == "customer":
        return "user"
    if normalized in {"agent", "human", "support"}:
        return "assistant"
    return "user"


async def get_session_history(db: AsyncSession, session_id: int):
    result = await db.execute(
        select(CommunicationMessage)
        .where(CommunicationMessage.session_id == session_id)
        .order_by(CommunicationMessage.id)
    )
    return result.scalars().all()


async def _resolve_session_chatbot(
    db: AsyncSession,
    session: CommunicationSession,
) -> BusinessChatbot:
    if session.chatbot_id:
        return await get_chatbot(db, session.chatbot_id)

    chatbot = await ensure_default_chatbot(db, session.business_id)
    session.chatbot_id = chatbot.id
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return chatbot


async def ask(
    db: AsyncSession,
    session_id: int,
    question: str,
) -> CommunicationMessage:
    session: CommunicationSession | None = await db.get(CommunicationSession, session_id)
    if not session:
        raise ValueError("Session not found")

    chatbot = await _resolve_session_chatbot(db, session)
    groq_client = get_groq_client()
    if groq_client is None:
        raise ValueError("GROQ_API_KEY is not configured")

    user_msg = CommunicationMessage(
        session_id=session_id,
        role="user",
        content=question,
    )
    user_msg = await _commit_and_refresh_message(db, user_msg)
    _publish_to_supabase(
        channel=f"session-{session_id}",
        payload=_build_message_event("user_message", user_msg),
    )

    scored_chunks = retrieve_relevant_chunks(
        business_id=chatbot.business_id,
        chatbot_id=chatbot.id,
        question=question,
        top_k=5,
    )

    if scored_chunks:
        context = "\n\n".join(
            f"[Source {i + 1}]\n{text}"
            for i, (text, _) in enumerate(scored_chunks)
        )
        source_snippets = [text[:200] + "..." for text, _ in scored_chunks]
    else:
        context = "No relevant documents found for this chatbot."
        source_snippets = []

    history_result = await db.execute(
        select(CommunicationMessage)
        .where(
            CommunicationMessage.session_id == session_id,
            CommunicationMessage.id != user_msg.id,
        )
        .order_by(CommunicationMessage.id)
        .limit(10)
    )
    history = history_result.scalars().all()

    base_prompt = (
        chatbot.system_prompt
        or "You are a helpful customer support assistant. "
        "Answer ONLY using the context below. "
        "If the answer is not in the context, say you don't have that information "
        "and suggest the customer contact the business directly."
    )
    system_prompt = f"{base_prompt}\n\n=== CONTEXT FROM CHATBOT DOCUMENTS ===\n{context}"

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        if not msg.content:
            continue
        messages.append(
            {
                "role": _to_provider_role(msg.role),
                "content": msg.content,
            }
        )
    messages.append({"role": "user", "content": question})

    response = groq_client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=messages,
        max_tokens=1024,
        temperature=0.3,
    )
    answer_text = response.choices[0].message.content

    assistant_msg = CommunicationMessage(
        session_id=session_id,
        role="assistant",
        content=answer_text,
        sources=source_snippets,
    )
    assistant_msg = await _commit_and_refresh_message(db, assistant_msg)
    _publish_to_supabase(
        channel=f"session-{session_id}",
        payload=_build_message_event("assistant_message", assistant_msg),
    )
    return assistant_msg


def _publish_to_supabase(channel: str, payload: dict) -> None:
    """
    Fire-and-forget broadcast to Supabase Realtime REST API.
    Never raises - failures are silently logged so message saving is never blocked.
    Channel naming: "session-{session_id}" (hyphens, not underscores).
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        return

    try:
        url = f"{settings.SUPABASE_URL}/realtime/v1/api/broadcast"
        headers = {
            "Content-Type": "application/json",
            "apikey": settings.SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_ANON_KEY}",
        }
        body = {
            "messages": [
                {
                    "topic": channel,
                    "event": "new_message",
                    "payload": payload,
                }
            ]
        }
        _httpx.post(url, json=body, headers=headers, timeout=5)
    except Exception as exc:
        print(f"[Supabase broadcast error] {exc}")


async def request_escalation(
    db: AsyncSession,
    session_id: int,
) -> EscalationRequest:
    session = await db.get(CommunicationSession, session_id)
    if not session:
        raise ValueError("Session not found")

    escalation = EscalationRequest(
        session_id=session_id,
        business_id=session.business_id,
        status="pending",
    )
    db.add(escalation)
    await db.commit()
    await db.refresh(escalation)

    system_msg = await _create_system_message(
        db,
        session_id,
        "Customer has requested a human agent. Please wait.",
    )
    _publish_to_supabase(
        channel=f"session-{session_id}",
        payload=_build_message_event(
            "escalation_requested",
            system_msg,
            escalation=escalation,
        ),
    )
    return escalation


async def get_pending_escalations(
    db: AsyncSession,
    business_id: int,
) -> list:
    result = await db.execute(
        select(EscalationRequest).where(
            EscalationRequest.business_id == business_id,
            EscalationRequest.status.in_(["pending", "active"]),
        )
    )
    return result.scalars().all()


async def claim_escalation(
    db: AsyncSession,
    escalation_id: int,
    agent_user_id: int,
) -> EscalationRequest:
    escalation = await db.get(EscalationRequest, escalation_id)
    if not escalation:
        raise ValueError("Escalation not found")

    escalation.status = "active"
    escalation.agent_user_id = agent_user_id
    db.add(escalation)
    await db.commit()
    await db.refresh(escalation)

    system_msg = await _create_system_message(
        db,
        escalation.session_id,
        "A human agent has joined the chat.",
    )

    _publish_to_supabase(
        channel=f"session-{escalation.session_id}",
        payload=_build_message_event(
            "escalation_claimed",
            system_msg,
            escalation=escalation,
        ),
    )
    return escalation


async def send_human_message(
    db: AsyncSession,
    session_id: int,
    content: str,
    role: str,
) -> CommunicationMessage:
    msg = CommunicationMessage(
        session_id=session_id,
        role=role,
        content=content,
    )
    msg = await _commit_and_refresh_message(db, msg)

    _publish_to_supabase(
        channel=f"session-{session_id}",
        payload=_build_message_event("human_message", msg),
    )
    return msg


async def close_escalation(
    db: AsyncSession,
    escalation_id: int,
    agent_user_id: int,
) -> EscalationRequest:
    escalation = await db.get(EscalationRequest, escalation_id)
    if not escalation:
        raise ValueError("Escalation not found")

    escalation.status = "closed"
    escalation.resolved_at = _dt.utcnow()
    db.add(escalation)
    await db.commit()
    await db.refresh(escalation)

    system_msg = await _create_system_message(
        db,
        escalation.session_id,
        "The agent has closed this session. Thank you.",
    )

    _publish_to_supabase(
        channel=f"session-{escalation.session_id}",
        payload=_build_message_event(
            "escalation_closed",
            system_msg,
            escalation=escalation,
        ),
    )
    return escalation


async def get_escalation_by_session(
    db: AsyncSession,
    session_id: int,
) -> EscalationRequest | None:
    result = await db.execute(
        select(EscalationRequest).where(
            EscalationRequest.session_id == session_id,
            EscalationRequest.status.in_(["pending", "active"]),
        )
    )
    return result.scalar_one_or_none()
