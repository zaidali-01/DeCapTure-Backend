from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def log(
    db: AsyncSession,
    action: str,
    user_id: int = None,
    business_id: int = None,
    entity_type: str = None,
    entity_id: int = None,
    detail: dict = None,
) -> None:
    """
    Fire-and-forget audit logger. Never raises.
    Call this after every significant write operation.
    """
    try:
        entry = AuditLog(
            user_id=user_id,
            business_id=business_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            detail=detail or {},
        )
        db.add(entry)
        await db.commit()
    except Exception as exc:
        print(f"[AuditLog error] {exc}")


async def get_audit_logs(
    db: AsyncSession,
    business_id: int,
    user_id: int = None,
    action: str = None,
    entity_type: str = None,
    limit: int = 100,
    offset: int = 0,
) -> list:
    query = select(AuditLog).where(AuditLog.business_id == business_id)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    if action:
        query = query.where(AuditLog.action == action)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    query = query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()
