from fastapi import HTTPException
from sqlalchemy import select

from app.models.contact import CustomerContact
from app.models.loyalty import LoyaltyAccount, LoyaltyTransaction

POINTS_PER_UNIT_CURRENCY = 1
POINTS_REDEMPTION_RATE = 10


async def _ensure_contact(db, contact_id, business_id):
    result = await db.execute(
        select(CustomerContact).where(
            CustomerContact.contact_id == contact_id,
            CustomerContact.business_id == business_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Customer contact not found")


async def get_or_create_account(db, contact_id, business_id):
    await _ensure_contact(db, contact_id, business_id)

    result = await db.execute(
        select(LoyaltyAccount).where(
            LoyaltyAccount.contact_id == contact_id,
            LoyaltyAccount.business_id == business_id,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        account = LoyaltyAccount(
            contact_id=contact_id,
            business_id=business_id,
            points=0,
            total_earned=0,
            total_redeemed=0,
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)
    return account


async def award_points(
    db,
    contact_id,
    business_id,
    amount_spent: float,
    reference: str = None,
):
    """Call this after a sale is created."""
    points_earned = int(amount_spent * POINTS_PER_UNIT_CURRENCY)
    if points_earned <= 0:
        return None

    account = await get_or_create_account(db, contact_id, business_id)
    account.points += points_earned
    account.total_earned += points_earned
    db.add(account)

    db.add(
        LoyaltyTransaction(
            account_id=account.id,
            business_id=business_id,
            type="earned",
            points=points_earned,
            reference=reference,
            note=f"Earned for purchase of {amount_spent:.2f}",
        )
    )
    await db.commit()
    await db.refresh(account)
    return account


async def redeem_points(db, contact_id, business_id, points_to_redeem: int):
    """Returns the discount amount the cashier should apply."""
    account = await get_or_create_account(db, contact_id, business_id)
    if account.points < points_to_redeem:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient points. Available: {account.points}",
        )

    discount = points_to_redeem / POINTS_REDEMPTION_RATE
    account.points -= points_to_redeem
    account.total_redeemed += points_to_redeem
    db.add(account)

    db.add(
        LoyaltyTransaction(
            account_id=account.id,
            business_id=business_id,
            type="redeemed",
            points=-points_to_redeem,
            note=f"Redeemed for {discount:.2f} discount",
        )
    )
    await db.commit()
    await db.refresh(account)
    return {
        "points_redeemed": points_to_redeem,
        "discount_value": discount,
        "remaining_points": account.points,
    }


async def get_account_by_contact(db, contact_id, business_id):
    account = await get_or_create_account(db, contact_id, business_id)
    result = await db.execute(
        select(LoyaltyTransaction)
        .where(LoyaltyTransaction.account_id == account.id)
        .order_by(LoyaltyTransaction.created_at.desc())
        .limit(20)
    )
    transactions = result.scalars().all()
    return {
        "contact_id": contact_id,
        "points": account.points,
        "total_earned": account.total_earned,
        "total_redeemed": account.total_redeemed,
        "redemption_value": account.points / POINTS_REDEMPTION_RATE,
        "transactions": [
            {
                "type": t.type,
                "points": t.points,
                "note": t.note,
                "created_at": str(t.created_at),
            }
            for t in transactions
        ],
    }


async def manual_adjust(db, contact_id, business_id, points: int, note: str):
    """Manually add or remove points (owner privilege)."""
    account = await get_or_create_account(db, contact_id, business_id)
    account.points = max(0, account.points + points)
    if points > 0:
        account.total_earned += points
    db.add(account)
    db.add(
        LoyaltyTransaction(
            account_id=account.id,
            business_id=business_id,
            type="adjusted",
            points=points,
            note=note,
        )
    )
    await db.commit()
    await db.refresh(account)
    return account
