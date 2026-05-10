import os
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.business import Business
from app.models.communications import (
    BusinessDocument,
    CommunicationMessage,
    CommunicationSession,
)
from app.modules.Communications.rag.chroma_client import (
    delete_document_chunks,
    get_collection,
)
from app.modules.Communications.rag.chunker import chunk_text
from app.modules.Communications.rag.embedder import embed_batch
from app.modules.Communications.rag.extractor import extract_text_from_pdf
from app.modules.Communications.rag.retriever import retrieve_relevant_chunks


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


async def ingest_document(
    db: AsyncSession,
    business_id: int,
    filename: str,
    file_path: str,
) -> BusinessDocument:
    doc = BusinessDocument(
        business_id=business_id,
        filename=filename,
        file_path=file_path,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    raw_text = extract_text_from_pdf(file_path)

    chunks = chunk_text(raw_text, chunk_size=500, overlap=50)
    if not chunks:
        return doc

    embeddings = embed_batch(chunks)

    collection = get_collection(business_id)
    collection.add(
        ids=[str(uuid.uuid4()) for _ in chunks],
        documents=chunks,
        embeddings=embeddings,
        metadatas=[
            {"document_id": doc.id, "business_id": business_id, "chunk_index": i}
            for i in range(len(chunks))
        ],
    )

    doc.chunk_count = len(chunks)
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


async def list_documents(db: AsyncSession, business_id: int):
    result = await db.execute(
        select(BusinessDocument).where(BusinessDocument.business_id == business_id)
    )
    return result.scalars().all()


async def delete_document(db: AsyncSession, document_id: int, business_id: int):
    result = await db.execute(
        select(BusinessDocument).where(
            BusinessDocument.id == document_id,
            BusinessDocument.business_id == business_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise ValueError("Document not found")

    delete_document_chunks(business_id, document_id)

    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    await db.delete(doc)
    await db.commit()
    return {"message": f"'{doc.filename}' deleted"}


async def create_session(
    db: AsyncSession,
    business_id: int,
    customer_name: str | None,
) -> CommunicationSession:
    await ensure_business_exists(db, business_id)

    session = CommunicationSession(
        business_id=business_id,
        customer_name=customer_name,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session_history(db: AsyncSession, session_id: int):
    result = await db.execute(
        select(CommunicationMessage)
        .where(CommunicationMessage.session_id == session_id)
        .order_by(CommunicationMessage.id)
    )
    return result.scalars().all()


async def ask(
    db: AsyncSession,
    session_id: int,
    question: str,
) -> CommunicationMessage:
    session: CommunicationSession | None = await db.get(CommunicationSession, session_id)
    if not session:
        raise ValueError("Session not found")
    groq_client = get_groq_client()
    if groq_client is None:
        raise ValueError("GROQ_API_KEY is not configured")

    user_msg = CommunicationMessage(
        session_id=session_id,
        role="user",
        content=question,
    )
    db.add(user_msg)
    await db.commit()

    scored_chunks = retrieve_relevant_chunks(
        business_id=session.business_id,
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
        context = "No relevant documents found for this business."
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

    system_prompt = (
        "You are a helpful customer support assistant. "
        "Answer ONLY using the context below. "
        "If the answer is not in the context, say you don't have that information "
        "and suggest the customer contact the business directly.\n\n"
        "=== CONTEXT FROM BUSINESS DOCUMENTS ===\n"
        f"{context}"
    )

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})
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
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(assistant_msg)
    return assistant_msg


import httpx as _httpx
from datetime import datetime as _dt
from app.models.communications import EscalationRequest


def _publish_to_supabase(channel: str, payload: dict) -> None:
    """
    Fire-and-forget broadcast to Supabase Realtime REST API.
    Never raises - failures are silently logged so message saving is never blocked.
    Channel naming: "session-{session_id}" (hyphens, not underscores).
    """
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

    db.add(CommunicationMessage(
        session_id=session_id,
        role="system",
        content="Customer has requested a human agent. Please wait.",
    ))
    await db.commit()
    await db.refresh(escalation)
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

    db.add(CommunicationMessage(
        session_id=escalation.session_id,
        role="system",
        content="A human agent has joined the chat.",
    ))
    await db.commit()
    await db.refresh(escalation)

    _publish_to_supabase(
        channel=f"session-{escalation.session_id}",
        payload={
            "role": "system",
            "content": "A human agent has joined the chat.",
            "session_id": escalation.session_id,
        },
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
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    _publish_to_supabase(
        channel=f"session-{session_id}",
        payload={
            "role": role,
            "content": content,
            "session_id": session_id,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        },
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

    db.add(CommunicationMessage(
        session_id=escalation.session_id,
        role="system",
        content="The agent has closed this session. Thank you.",
    ))
    await db.commit()
    await db.refresh(escalation)

    _publish_to_supabase(
        channel=f"session-{escalation.session_id}",
        payload={
            "role": "system",
            "content": "The agent has closed this session. Thank you.",
            "session_id": escalation.session_id,
        },
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
