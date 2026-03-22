from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, select, join
from fastapi import HTTPException
from datetime import date

from app.models.inventory import ProductInventory
from app.models.sales import Sales, SalesInventoryBridge
from app.models.accounts import DailyAccounts

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


async def update_product(db: AsyncSession, product_id: int, business_id: int, data):
    result = await db.execute(
        select(ProductInventory).where(
            ProductInventory.id == product_id,
            ProductInventory.business_id == business_id
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

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
    result = await db.execute(
        select(ProductInventory).where(
            ProductInventory.id == product_id,
            ProductInventory.business_id == business_id
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    await db.execute(delete(ProductInventory).where(ProductInventory.id == product_id))
    await db.commit()
    return {"message": "Product deleted successfully"}


async def create_sale(db: AsyncSession, user_id: int, business_id: int, data):
    sale = Sales(
        user_id=user_id,
        payment_method=data.payment_method,
        transaction_id=data.transaction_id,
        salesman_id=user_id
    )
    db.add(sale)
    await db.commit()
    await db.refresh(sale)

    for item in data.items:
        result = await db.execute(
            select(ProductInventory).where(
                ProductInventory.id == item.listing_id,
                ProductInventory.business_id == business_id
            )
        )
        product = result.scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item.listing_id} not found")
        if product.quantity < item.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for product {product.name}")

        product.quantity -= item.quantity
        db.add(product)

        bridge = SalesInventoryBridge(
            sales_id=sale.id,
            listing_id=item.listing_id,
            quantity=item.quantity
        )
        db.add(bridge)

    await db.commit()

    today = date.today()
    result = await db.execute(
        select(DailyAccounts).where(DailyAccounts.business_id == business_id, DailyAccounts.date == today)
    )
    daily_account = result.scalar_one_or_none()
    total_sale_amount = sum(
        [(await db.get(ProductInventory, item.listing_id)).price * item.quantity for item in data.items]
    )

    if daily_account:
        daily_account.revenue += total_sale_amount
        daily_account.sales += 1
        db.add(daily_account)
    else:
        daily_account = DailyAccounts(
            business_id=business_id,
            date=today,
            revenue=total_sale_amount,
            sales=1,
            cost=0,
            salary_cost=0,
            operational_cost=0,
            miscellaneous=0
        )
        db.add(daily_account)

    await db.commit()
    await db.refresh(sale)
    return sale



async def list_sales(db: AsyncSession, business_id: int):
    result = await db.execute(
        select(Sales).where(
            Sales.user_id == Sales.user_id  
        )
    )
    return result.scalars().all()


async def get_sale_details(db: AsyncSession, sale_id: int, business_id: int):
    sale_result = await db.execute(
        select(Sales).where(Sales.id == sale_id)
    )
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
