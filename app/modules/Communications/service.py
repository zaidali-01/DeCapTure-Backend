import os
import pypdf

from groq import Groq
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.chatbot import BusinessDocument, ChatSession, ChatMessage


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_pdf_text(file_path: str, max_chars: int = 12_000) -> str:
    """Pull plain text from a PDF file, capped to stay inside context limits."""
    reader = pypdf.PdfReader(file_path)
    pages: list[str] = []
    total = 0
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)
        total += len(text)
        if total >= max_chars:
            break
    return "\n".join(pages)[:max_chars]


def _build_history(messages: list[ChatMessage]) -> list[dict]:
    """Convert ORM rows to the list[{role, content}] Groq expects."""
    return [{"role": m.role, "content": m.content} for m in messages]


# ── Groq client (initialised once) ───────────────────────────────────────────

from app.core.config import settings
client = Groq(api_key=settings.GROQ_API_KEY)
# ── Service functions ─────────────────────────────────────────────────────────

async def create_session(
    db: AsyncSession,
    business_id: int,
    customer_name: str | None,
) -> ChatSession:
    session = ChatSession(business_id=business_id, customer_name=customer_name)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def save_user_message(
    db: AsyncSession,
    session_id: int,
    content: str,
) -> ChatMessage:
    msg = ChatMessage(session_id=session_id, role="user", content=content)
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


async def generate_reply(
    db: AsyncSession,
    message_id: int,
) -> ChatMessage:
    """
    1. Load the user message + its session.
    2. Pull all PDF documents for that business.
    3. Ask Groq (Llama 3) with PDF context + conversation history.
    4. Persist and return the assistant message.
    """

    # ── 1. Fetch the user message ─────────────────────────────────────────────
    user_msg: ChatMessage | None = await db.get(ChatMessage, message_id)
    if user_msg is None:
        raise ValueError(f"Message {message_id} not found")
    if user_msg.role != "user":
        raise ValueError("message_id must point to a user message")

    chat_session: ChatSession | None = await db.get(ChatSession, user_msg.session_id)
    if chat_session is None:
        raise ValueError("Session not found")

    # ── 2. Fetch PDF context for this business ────────────────────────────────
    result = await db.execute(
        select(BusinessDocument).where(
            BusinessDocument.business_id == chat_session.business_id
        )
    )
    docs: list[BusinessDocument] = result.scalars().all()

    pdf_context = ""
    for doc in docs:
        if os.path.exists(doc.file_path):
            pdf_context += f"\n\n--- Document: {doc.filename} ---\n"
            pdf_context += _extract_pdf_text(doc.file_path)

    # ── 3. Fetch conversation history (excluding current message) ─────────────
    history_result = await db.execute(
        select(ChatMessage)
        .where(
            ChatMessage.session_id == user_msg.session_id,
            ChatMessage.id < message_id,
        )
        .order_by(ChatMessage.id)
    )
    history: list[ChatMessage] = history_result.scalars().all()

    # ── 4. Build messages list for Groq ───────────────────────────────────────
    system_prompt = (
        "You are a helpful customer support assistant for a business. "
        "Answer the customer's questions using ONLY the information found in the "
        "business documents provided below. "
        "If the answer is not in the documents, say you don't have that information "
        "and suggest the customer contact the business directly.\n\n"
        "=== BUSINESS DOCUMENTS ===\n"
        + (pdf_context if pdf_context else "No documents available.")
    )

    messages = [{"role": "system", "content": system_prompt}]
    messages += _build_history(history)
    messages.append({"role": "user", "content": user_msg.content})

    # ── 5. Call Groq API ──────────────────────────────────────────────────────
    response = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=messages,
        max_tokens=1024,
        temperature=0.7,
    )

    reply_text: str = response.choices[0].message.content

    # ── 6. Persist and return the assistant message ───────────────────────────
    assistant_msg = ChatMessage(
        session_id=user_msg.session_id,
        role="assistant",
        content=reply_text,
    )
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(assistant_msg)
    return assistant_msg