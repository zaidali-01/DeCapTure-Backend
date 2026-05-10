from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from fastapi import HTTPException
from datetime import date
from pathlib import Path

from app.models.inventory import ProductInventory
from app.models.sales import Sales, SalesInventoryBridge
from app.models.accounts import DailyAccounts
from app.models.store import StoreListing, StoreListingImage


STORE_UPLOADS_ROOT = Path(__file__).resolve().parents[3] / "uploads"


async def create_product(db: AsyncSession, business_id: int, data):
    product = ProductInventory(
        name=data.name,
        description=data.description,
        price=data.price,
        quantity=data.quantity,
        business_id=business_id
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


async def get_products(db: AsyncSession, business_id: int):
    result = await db.execute(
        select(ProductInventory).where(ProductInventory.business_id == business_id)
    )
    return result.scalars().all()


async def get_product_by_id(db: AsyncSession, product_id: int, business_id: int):
    result = await db.execute(
        select(ProductInventory).where(
            ProductInventory.id == product_id,
            ProductInventory.business_id == business_id
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


async def update_product(db: AsyncSession, product_id: int, business_id: int, data):
    product = await get_product_by_id(db, product_id, business_id)

    await db.execute(
        update(ProductInventory)
        .where(ProductInventory.id == product_id)
        .values(
            name=data.name if data.name else product.name,
            description=data.description if data.description else product.description,
            price=data.price if data.price else product.price,
            quantity=data.quantity if data.quantity is not None else product.quantity
        )
    )
    await db.commit()

    result = await db.execute(select(ProductInventory).where(ProductInventory.id == product_id))
    return result.scalar_one()


async def delete_product(db: AsyncSession, product_id: int, business_id: int):
    product = await get_product_by_id(db, product_id, business_id)

    listing_result = await db.execute(
        select(StoreListing).where(
            StoreListing.product_id == product_id,
            StoreListing.business_id == business_id,
        )
    )
    listing = listing_result.scalar_one_or_none()

    if listing:
        image_result = await db.execute(
            select(StoreListingImage).where(StoreListingImage.listing_id == listing.id)
        )
        images = image_result.scalars().all()
        for image in images:
            if not image.file_path:
                continue
            file_on_disk = STORE_UPLOADS_ROOT.parent / image.file_path.lstrip("/")
            if file_on_disk.exists():
                file_on_disk.unlink()

    await db.execute(delete(ProductInventory).where(ProductInventory.id == product_id))
    await db.commit()

    from app.modules.Audit.service import log as audit_log

    await audit_log(
        db,
        action="delete_product",
        entity_type="product",
        entity_id=product_id,
        business_id=business_id,
        detail={"product_name": product.name},
    )

    return {"message": "Product deleted successfully"}


async def create_sale(
    db: AsyncSession,
    user_id: int,
    business_id: int,
    data,
    contact_id: int = None,
):
    sale = Sales(
        user_id=user_id,
        business_id=business_id,
        payment_method=data.payment_method,
        transaction_id=data.transaction_id,
        salesman_id=user_id
    )
    db.add(sale)
    await db.commit()
    await db.refresh(sale)

    total_amount = 0
    low_stock_products = []

    for item in data.items:
        product = await get_product_by_id(db, item.listing_id, business_id)

        if product.quantity < item.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for {product.name}")

        product.quantity -= item.quantity
        total_amount += float(product.price) * item.quantity
        db.add(product)

        LOW_STOCK_THRESHOLD = 5
        if product.quantity <= LOW_STOCK_THRESHOLD:
            print(
                f"[LOW STOCK ALERT] Product '{product.name}' (ID: {product.id}) "
                f"has only {product.quantity} units left for business {business_id}."
            )
            # This print serves as a hook for a future notification service.
            low_stock_products.append(
                {
                    "id": product.id,
                    "name": product.name,
                    "quantity": product.quantity,
                }
            )

        db.add(SalesInventoryBridge(
            sales_id=sale.id,
            listing_id=item.listing_id,
            quantity=item.quantity
        ))

    await db.commit()

    if low_stock_products:
        from app.modules.Notifications.service import create_notification

        for product_info in low_stock_products:
            await create_notification(
                db=db,
                user_id=user_id,
                type="low_stock",
                title=f"Low stock: {product_info['name']}",
                body=f"Only {product_info['quantity']} units remaining.",
                business_id=business_id,
                entity_type="product",
                entity_id=product_info["id"],
            )

    today = date.today()
    result = await db.execute(
        select(DailyAccounts).where(
            DailyAccounts.business_id == business_id,
            DailyAccounts.date == today
        )
    )
    daily = result.scalar_one_or_none()

    if daily:
        daily.revenue = float(daily.revenue or 0) + total_amount
        daily.sales = int(daily.sales or 0) + 1
        db.add(daily)
    else:
        db.add(DailyAccounts(
            business_id=business_id,
            date=today,
            revenue=total_amount,
            sales=1,
            cost=0,
            salary_cost=0,
            operational_cost=0,
            miscellaneous=0
        ))

    await db.commit()
    await db.refresh(sale)

    if contact_id:
        from app.modules.Loyalty.service import award_points

        await award_points(
            db,
            contact_id=contact_id,
            business_id=business_id,
            amount_spent=total_amount,
            reference=str(sale.id),
        )

    from app.modules.Audit.service import log as audit_log

    await audit_log(
        db,
        action="create_sale",
        user_id=user_id,
        business_id=business_id,
        entity_type="sale",
        entity_id=sale.id,
        detail={"total_amount": total_amount, "items_count": len(data.items)},
    )

    return sale


async def buy_product(db: AsyncSession, user_id: int, business_id: int, product_id: int, quantity: int):
    product = await get_product_by_id(db, product_id, business_id)

    if product.quantity < quantity:
        raise HTTPException(status_code=400, detail="Insufficient stock")

    class TempItem:
        def __init__(self, listing_id, quantity):
            self.listing_id = listing_id
            self.quantity = quantity

    class TempSale:
        def __init__(self):
            self.payment_method = "cash"
            self.transaction_id = f"quick-{product_id}"
            self.items = [TempItem(product_id, quantity)]

    return await create_sale(db, user_id, business_id, TempSale())


async def list_sales(db: AsyncSession, business_id: int):
    result = await db.execute(
        select(Sales)
        .join(SalesInventoryBridge, Sales.id == SalesInventoryBridge.sales_id)
        .join(ProductInventory, ProductInventory.id == SalesInventoryBridge.listing_id)
        .where(ProductInventory.business_id == business_id)
    )
    return result.scalars().unique().all()


async def get_sale_details(db: AsyncSession, sale_id: int, business_id: int):
    sale_result = await db.execute(select(Sales).where(Sales.id == sale_id))
    sale = sale_result.scalar_one_or_none()

    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")

    bridge_result = await db.execute(
        select(SalesInventoryBridge).where(SalesInventoryBridge.sales_id == sale_id)
    )
    bridges = bridge_result.scalars().all()

    items = []
    for b in bridges:
        product = await db.get(ProductInventory, b.listing_id)
        items.append({
            "product_id": product.id,
            "name": product.name,
            "quantity": b.quantity,
            "price": float(product.price)
        })

    return {
        "sale_id": sale.id,
        "user_id": sale.user_id,
        "transaction_id": sale.transaction_id,
        "payment_method": sale.payment_method,
        "created_at": sale.created_at,
        "items": items
    }
