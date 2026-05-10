from datetime import date

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import CustomerContact
from app.models.crm import CustomerNote, FollowUp, Lead
from app.schemas.crm import (
    FollowUpCreate,
    FollowUpUpdate,
    LeadCreate,
    LeadUpdate,
    NoteCreate,
)


async def _ensure_contact_belongs_to_business(
    db: AsyncSession,
    business_id: int,
    contact_id: int,
) -> None:
    result = await db.execute(
        select(CustomerContact).where(
            CustomerContact.contact_id == contact_id,
            CustomerContact.business_id == business_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Contact not found")


async def create_lead(
    db: AsyncSession,
    business_id: int,
    user_id: int,
    data: LeadCreate,
) -> Lead:
    if data.contact_id:
        await _ensure_contact_belongs_to_business(db, business_id, data.contact_id)

    lead = Lead(business_id=business_id, **data.dict())
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    return lead


async def list_leads(
    db: AsyncSession,
    business_id: int,
    stage: str = None,
    assigned_to: int = None,
) -> list:
    query = select(Lead).where(Lead.business_id == business_id)
    if stage:
        query = query.where(Lead.stage == stage)
    if assigned_to:
        query = query.where(Lead.assigned_to == assigned_to)
    query = query.order_by(Lead.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


async def get_lead(
    db: AsyncSession,
    lead_id: int,
    business_id: int,
) -> Lead:
    result = await db.execute(
        select(Lead).where(
            Lead.id == lead_id,
            Lead.business_id == business_id,
        )
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


async def update_lead(
    db: AsyncSession,
    lead_id: int,
    business_id: int,
    data: LeadUpdate,
    user_id: int = None,
) -> Lead:
    lead = await get_lead(db, lead_id, business_id)
    old_stage = lead.stage
    for field, value in data.dict(exclude_unset=True).items():
        setattr(lead, field, value)
    db.add(lead)
    await db.commit()
    await db.refresh(lead)

    if data.stage and data.stage != old_stage:
        from app.modules.Audit.service import log as audit_log

        await audit_log(
            db,
            action="lead_stage_change",
            user_id=user_id,
            business_id=business_id,
            entity_type="lead",
            entity_id=lead_id,
            detail={"new_stage": data.stage},
        )

    return lead


async def delete_lead(
    db: AsyncSession,
    lead_id: int,
    business_id: int,
) -> dict:
    await get_lead(db, lead_id, business_id)
    await db.execute(delete(Lead).where(Lead.id == lead_id))
    await db.commit()
    return {"message": "Lead deleted"}


async def get_pipeline_summary(
    db: AsyncSession,
    business_id: int,
) -> dict:
    """Count and total value by pipeline stage."""
    result = await db.execute(
        select(
            Lead.stage,
            func.count(Lead.id).label("count"),
            func.coalesce(func.sum(Lead.value), 0).label("total_value"),
        )
        .where(Lead.business_id == business_id)
        .group_by(Lead.stage)
    )
    rows = result.all()
    return {
        "pipeline": [
            {"stage": r.stage, "count": r.count, "total_value": int(r.total_value)}
            for r in rows
        ]
    }


async def add_note(
    db: AsyncSession,
    business_id: int,
    author_id: int,
    data: NoteCreate,
) -> CustomerNote:
    await _ensure_contact_belongs_to_business(db, business_id, data.contact_id)

    note = CustomerNote(
        business_id=business_id,
        author_id=author_id,
        contact_id=data.contact_id,
        content=data.content,
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


async def list_notes(
    db: AsyncSession,
    business_id: int,
    contact_id: int,
) -> list:
    await _ensure_contact_belongs_to_business(db, business_id, contact_id)

    result = await db.execute(
        select(CustomerNote)
        .where(
            CustomerNote.business_id == business_id,
            CustomerNote.contact_id == contact_id,
        )
        .order_by(CustomerNote.created_at.desc())
    )
    return result.scalars().all()


async def create_followup(
    db: AsyncSession,
    business_id: int,
    data: FollowUpCreate,
) -> FollowUp:
    if data.contact_id:
        await _ensure_contact_belongs_to_business(db, business_id, data.contact_id)
    if data.lead_id:
        await get_lead(db, data.lead_id, business_id)

    fu = FollowUp(business_id=business_id, **data.dict())
    db.add(fu)
    await db.commit()
    await db.refresh(fu)
    return fu


async def list_followups(
    db: AsyncSession,
    business_id: int,
    assigned_to: int = None,
    overdue_only: bool = False,
) -> list:
    query = select(FollowUp).where(
        FollowUp.business_id == business_id,
        FollowUp.is_done == False,
    )
    if assigned_to:
        query = query.where(FollowUp.assigned_to == assigned_to)
    if overdue_only:
        query = query.where(FollowUp.due_date < date.today())
    query = query.order_by(FollowUp.due_date.asc())
    result = await db.execute(query)
    return result.scalars().all()


async def update_followup(
    db: AsyncSession,
    followup_id: int,
    business_id: int,
    data: FollowUpUpdate,
) -> FollowUp:
    result = await db.execute(
        select(FollowUp).where(
            FollowUp.id == followup_id,
            FollowUp.business_id == business_id,
        )
    )
    fu = result.scalar_one_or_none()
    if not fu:
        raise HTTPException(status_code=404, detail="Follow-up not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(fu, field, value)
    db.add(fu)
    await db.commit()
    await db.refresh(fu)
    return fu
