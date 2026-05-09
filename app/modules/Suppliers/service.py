from datetime import date

from fastapi import HTTPException
from sqlalchemy import delete, select

from app.models.accounts import DailyAccounts
from app.models.inventory import ProductInventory
from app.models.inventory_ext import (
    ProductCategory,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
)
from app.schemas.inventory_ext import (
    CategoryCreate,
    PurchaseOrderCreate,
    PurchaseOrderStatusUpdate,
    SupplierCreate,
    SupplierUpdate,
)


async def create_category(db, business_id, data: CategoryCreate):
    cat = ProductCategory(business_id=business_id, **data.dict())
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


async def list_categories(db, business_id):
    result = await db.execute(
        select(ProductCategory).where(ProductCategory.business_id == business_id)
    )
    return result.scalars().all()


async def delete_category(db, category_id, business_id):
    result = await db.execute(
        select(ProductCategory).where(
            ProductCategory.id == category_id,
            ProductCategory.business_id == business_id,
        )
    )
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    await db.execute(delete(ProductCategory).where(ProductCategory.id == category_id))
    await db.commit()
    return {"message": "Category deleted"}


async def create_supplier(db, business_id, data: SupplierCreate):
    supplier = Supplier(business_id=business_id, **data.dict())
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return supplier


async def list_suppliers(db, business_id):
    result = await db.execute(select(Supplier).where(Supplier.business_id == business_id))
    return result.scalars().all()


async def update_supplier(db, supplier_id, business_id, data: SupplierUpdate):
    result = await db.execute(
        select(Supplier).where(
            Supplier.id == supplier_id,
            Supplier.business_id == business_id,
        )
    )
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(supplier, field, value)
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return supplier


async def delete_supplier(db, supplier_id, business_id):
    result = await db.execute(
        select(Supplier).where(
            Supplier.id == supplier_id,
            Supplier.business_id == business_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Supplier not found")
    await db.execute(delete(Supplier).where(Supplier.id == supplier_id))
    await db.commit()
    return {"message": "Supplier deleted"}


async def _ensure_supplier(db, supplier_id, business_id):
    if supplier_id is None:
        return
    result = await db.execute(
        select(Supplier).where(
            Supplier.id == supplier_id,
            Supplier.business_id == business_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Supplier not found")


async def _ensure_product(db, product_id, business_id):
    if product_id is None:
        return
    result = await db.execute(
        select(ProductInventory).where(
            ProductInventory.id == product_id,
            ProductInventory.business_id == business_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Product not found")


async def create_purchase_order(db, business_id, user_id, data: PurchaseOrderCreate):
    await _ensure_supplier(db, data.supplier_id, business_id)
    for item in data.items:
        await _ensure_product(db, item.product_id, business_id)

    po = PurchaseOrder(
        business_id=business_id,
        supplier_id=data.supplier_id,
        created_by=user_id,
        status="pending",
        order_date=data.order_date,
        expected_date=data.expected_date,
        notes=data.notes,
    )
    db.add(po)
    await db.commit()
    await db.refresh(po)

    for item in data.items:
        db.add(
            PurchaseOrderItem(
                purchase_order_id=po.id,
                product_id=item.product_id,
                product_name=item.product_name,
                quantity_ordered=item.quantity_ordered,
                quantity_received=0,
                unit_cost=item.unit_cost,
            )
        )
    await db.commit()
    return po


async def list_purchase_orders(db, business_id, status=None):
    query = select(PurchaseOrder).where(PurchaseOrder.business_id == business_id)
    if status:
        query = query.where(PurchaseOrder.status == status)
    query = query.order_by(PurchaseOrder.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


async def get_purchase_order_detail(db, po_id, business_id):
    po_result = await db.execute(
        select(PurchaseOrder).where(
            PurchaseOrder.id == po_id,
            PurchaseOrder.business_id == business_id,
        )
    )
    po = po_result.scalar_one_or_none()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    items_result = await db.execute(
        select(PurchaseOrderItem).where(PurchaseOrderItem.purchase_order_id == po_id)
    )
    items = items_result.scalars().all()
    total_cost = sum(float(i.unit_cost) * i.quantity_ordered for i in items)

    return {
        "id": po.id,
        "business_id": po.business_id,
        "supplier_id": po.supplier_id,
        "created_by": po.created_by,
        "status": po.status,
        "order_date": str(po.order_date),
        "expected_date": str(po.expected_date) if po.expected_date else None,
        "received_date": str(po.received_date) if po.received_date else None,
        "notes": po.notes,
        "total_cost": total_cost,
        "items": [
            {
                "id": i.id,
                "product_id": i.product_id,
                "product_name": i.product_name,
                "quantity_ordered": i.quantity_ordered,
                "quantity_received": i.quantity_received,
                "unit_cost": float(i.unit_cost),
            }
            for i in items
        ],
    }


async def update_po_status(db, po_id, business_id, data: PurchaseOrderStatusUpdate):
    """
    When status is changed to 'received':
    - Set received_date
    - For each item, add quantity_ordered to the linked product's inventory
    - Record the total cost in DailyAccounts.cost for today
    """
    if data.status not in {"pending", "ordered", "received", "cancelled"}:
        raise HTTPException(status_code=400, detail="Invalid purchase order status")

    po_result = await db.execute(
        select(PurchaseOrder).where(
            PurchaseOrder.id == po_id,
            PurchaseOrder.business_id == business_id,
        )
    )
    po = po_result.scalar_one_or_none()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    po.status = data.status
    if data.received_date:
        po.received_date = data.received_date

    total_cost = 0.0
    if data.status == "received":
        items_result = await db.execute(
            select(PurchaseOrderItem).where(
                PurchaseOrderItem.purchase_order_id == po_id
            )
        )
        items = items_result.scalars().all()

        for item in items:
            item.quantity_received = item.quantity_ordered
            db.add(item)
            total_cost += float(item.unit_cost) * item.quantity_ordered

            if item.product_id:
                product = await db.get(ProductInventory, item.product_id)
                if product and product.business_id == business_id:
                    product.quantity = int(product.quantity or 0) + item.quantity_ordered
                    db.add(product)

        today = date.today()
        acc_result = await db.execute(
            select(DailyAccounts).where(
                DailyAccounts.business_id == business_id,
                DailyAccounts.date == today,
            )
        )
        acc = acc_result.scalar_one_or_none()
        if acc:
            acc.cost = float(acc.cost or 0) + total_cost
            db.add(acc)
        else:
            db.add(
                DailyAccounts(
                    business_id=business_id,
                    date=today,
                    cost=total_cost,
                    revenue=0,
                    sales=0,
                    salary_cost=0,
                    operational_cost=0,
                    miscellaneous=0,
                )
            )

        from app.modules.Audit.service import log as audit_log

        await audit_log(
            db,
            action="po_received",
            business_id=business_id,
            entity_type="purchase_order",
            entity_id=po_id,
            detail={"total_cost": total_cost},
        )

    db.add(po)
    await db.commit()
    await db.refresh(po)
    return po
