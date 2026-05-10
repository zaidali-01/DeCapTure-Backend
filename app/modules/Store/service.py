from collections import defaultdict
from pathlib import Path
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business
from app.models.inventory import ProductInventory
from app.models.module import UserRole
from app.models.communications import BusinessChatbot
from app.models.store import StoreListing, StoreListingImage, StoreOrder, StoreOrderItem
from app.modules.POS.service import create_sale


ORDER_STATUSES = {"pending", "confirmed", "cancelled", "fulfilled"}
LISTING_TYPES = {"product", "service"}
STORE_IMAGE_DIR = Path(__file__).resolve().parents[3] / "uploads" / "store"
STORE_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


class _StoreSaleItem:
    def __init__(self, listing_id: int, quantity: int):
        self.listing_id = listing_id
        self.quantity = quantity


class _StoreFulfillmentSale:
    def __init__(self, order_id: int, items: list[_StoreSaleItem]):
        self.payment_method = "store_order"
        self.transaction_id = f"store-order-{order_id}"
        self.items = items


async def _assert_business_role(
    db: AsyncSession,
    user_id: int,
    business_id: int,
    allowed_roles: list[str],
) -> None:
    result = await db.execute(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.business_id == business_id,
        )
    )
    roles = result.scalars().all()
    if not any(role.role in allowed_roles for role in roles):
        raise HTTPException(status_code=403, detail="Not allowed")


def _serialize_listing(
    listing: StoreListing,
    product: ProductInventory,
    business_name: str | None = None,
    images: list[StoreListingImage] | None = None,
):
    return {
        "id": listing.id,
        "business_id": listing.business_id,
        "product_id": listing.product_id,
        "is_published": bool(listing.is_published),
        "listing_type": listing.listing_type or "product",
        "headline": listing.headline,
        "display_description": listing.display_description,
        "created_at": listing.created_at,
        "updated_at": listing.updated_at,
        "product_name": product.name,
        "product_description": product.description,
        "product_price": float(product.price or 0),
        "product_quantity": int(product.quantity or 0),
        "business_name": business_name,
        "images": [
            {
                "id": image.id,
                "file_path": image.file_path,
                "sort_order": image.sort_order or 0,
            }
            for image in sorted(images or [], key=lambda item: (item.sort_order or 0, item.id or 0))
        ],
    }


async def _listing_images_by_listing_ids(
    db: AsyncSession,
    listing_ids: list[int],
):
    if not listing_ids:
        return {}
    result = await db.execute(
        select(StoreListingImage)
        .where(StoreListingImage.listing_id.in_(listing_ids))
        .order_by(StoreListingImage.sort_order.asc(), StoreListingImage.id.asc())
    )
    images = result.scalars().all()
    grouped: dict[int, list[StoreListingImage]] = defaultdict(list)
    for image in images:
        grouped[image.listing_id].append(image)
    return grouped


def _normalize_listing_type(value: str | None) -> str:
    normalized = (value or "product").strip().lower()
    if normalized not in LISTING_TYPES:
        raise HTTPException(status_code=400, detail="Listing type must be product or service")
    return normalized


async def _get_product(db: AsyncSession, product_id: int, business_id: int) -> ProductInventory:
    result = await db.execute(
        select(ProductInventory).where(
            ProductInventory.id == product_id,
            ProductInventory.business_id == business_id,
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


async def _get_listing_with_product(db: AsyncSession, listing_id: int, published_only: bool = False):
    result = await db.execute(
        select(StoreListing, ProductInventory, Business)
        .join(ProductInventory, ProductInventory.id == StoreListing.product_id)
        .join(Business, Business.id == StoreListing.business_id)
        .where(StoreListing.id == listing_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Listing not found")
    listing, product, business = row
    if published_only and not listing.is_published:
        raise HTTPException(status_code=404, detail="Listing not found")
    return listing, product, business


async def _get_listing_images(db: AsyncSession, listing_id: int):
    result = await db.execute(
        select(StoreListingImage)
        .where(StoreListingImage.listing_id == listing_id)
        .order_by(StoreListingImage.sort_order.asc(), StoreListingImage.id.asc())
    )
    return result.scalars().all()


async def _ensure_publish_requirements(db: AsyncSession, listing: StoreListing):
    images = await _get_listing_images(db, listing.id)
    if not images:
        raise HTTPException(status_code=400, detail="At least one image is required before publishing")
    if not listing.listing_type:
        raise HTTPException(status_code=400, detail="Listing type is required before publishing")


async def list_public_businesses(db: AsyncSession):
    listing_counts = (
        select(
            StoreListing.business_id,
            func.count(StoreListing.id).label("published_listing_count"),
        )
        .where(StoreListing.is_published.is_(True))
        .group_by(StoreListing.business_id)
        .subquery()
    )
    store_bot_counts = (
        select(
            BusinessChatbot.business_id,
            func.max(BusinessChatbot.id).label("store_bot_id"),
        )
        .where(BusinessChatbot.is_store_bot.is_(True))
        .group_by(BusinessChatbot.business_id)
        .subquery()
    )
    result = await db.execute(
        select(Business, listing_counts.c.published_listing_count, store_bot_counts.c.store_bot_id)
        .join(listing_counts, listing_counts.c.business_id == Business.id)
        .outerjoin(store_bot_counts, store_bot_counts.c.business_id == Business.id)
        .order_by(Business.name.asc())
    )
    rows = result.all()
    return [
        {
            "id": business.id,
            "name": business.name,
            "industry": business.industry,
            "description": business.description,
            "phone": business.phone,
            "email": business.email,
            "published_listing_count": int(count or 0),
            "has_store_bot": bool(store_bot_id),
            "store_bot_id": store_bot_id,
        }
        for business, count, store_bot_id in rows
    ]


async def get_public_business(db: AsyncSession, business_id: int):
    listing_count = await db.execute(
        select(func.count(StoreListing.id)).where(
            StoreListing.business_id == business_id,
            StoreListing.is_published.is_(True),
        )
    )
    count = listing_count.scalar() or 0
    if count == 0:
        raise HTTPException(status_code=404, detail="Business not found")

    business = await db.get(Business, business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    store_bot_result = await db.execute(
        select(BusinessChatbot).where(
            BusinessChatbot.business_id == business_id,
            BusinessChatbot.is_store_bot.is_(True),
        )
    )
    store_bot = store_bot_result.scalar_one_or_none()
    return {
        "id": business.id,
        "name": business.name,
        "industry": business.industry,
        "description": business.description,
        "phone": business.phone,
        "email": business.email,
        "published_listing_count": int(count),
        "has_store_bot": bool(store_bot),
        "store_bot_id": store_bot.id if store_bot else None,
    }


async def list_public_listings(
    db: AsyncSession,
    business_id: int | None = None,
    search: str | None = None,
):
    query = (
        select(StoreListing, ProductInventory, Business)
        .join(ProductInventory, ProductInventory.id == StoreListing.product_id)
        .join(Business, Business.id == StoreListing.business_id)
        .where(StoreListing.is_published.is_(True))
        .order_by(StoreListing.id.desc())
    )
    if business_id:
        query = query.where(StoreListing.business_id == business_id)
    if search:
        like = f"%{search.strip()}%"
        query = query.where(
            ProductInventory.name.ilike(like) | Business.name.ilike(like)
        )

    result = await db.execute(query)
    rows = result.all()
    images_by_listing = await _listing_images_by_listing_ids(db, [listing.id for listing, _, _ in rows])
    return [
        _serialize_listing(listing, product, business.name, images_by_listing.get(listing.id, []))
        for listing, product, business in rows
    ]


async def get_public_listing(db: AsyncSession, listing_id: int):
    listing, product, business = await _get_listing_with_product(db, listing_id, published_only=True)
    images = await _get_listing_images(db, listing.id)
    return _serialize_listing(listing, product, business.name, images)


async def list_business_store_listings(
    db: AsyncSession,
    user_id: int,
    business_id: int,
):
    await _assert_business_role(db, user_id, business_id, ["business_owner", "manager"])
    result = await db.execute(
        select(StoreListing, ProductInventory)
        .join(ProductInventory, ProductInventory.id == StoreListing.product_id)
        .where(StoreListing.business_id == business_id)
        .order_by(StoreListing.id.desc())
    )
    rows = result.all()
    images_by_listing = await _listing_images_by_listing_ids(db, [listing.id for listing, _ in rows])

    inventory_result = await db.execute(
        select(ProductInventory).where(ProductInventory.business_id == business_id)
    )
    inventory = inventory_result.scalars().all()
    listing_by_product = {listing.product_id: listing for listing, _ in rows}
    product_by_listing = {listing.id: product for listing, product in rows}

    response = []
    for product in inventory:
        listing = listing_by_product.get(product.id)
        if listing:
            response.append(_serialize_listing(listing, product, None, images_by_listing.get(listing.id, [])))
        else:
            response.append(
                {
                    "id": None,
                    "business_id": business_id,
                    "product_id": product.id,
                    "is_published": False,
                    "listing_type": "product",
                    "headline": None,
                    "display_description": None,
                    "created_at": None,
                    "updated_at": None,
                    "product_name": product.name,
                    "product_description": product.description,
                    "product_price": float(product.price or 0),
                    "product_quantity": int(product.quantity or 0),
                    "business_name": None,
                    "images": [],
                }
            )
    return response


async def upsert_store_listing(
    db: AsyncSession,
    user_id: int,
    business_id: int,
    product_id: int,
    payload,
):
    await _assert_business_role(db, user_id, business_id, ["business_owner", "manager"])
    product = await _get_product(db, product_id, business_id)
    result = await db.execute(
        select(StoreListing).where(
            StoreListing.business_id == business_id,
            StoreListing.product_id == product_id,
        )
    )
    listing = result.scalar_one_or_none()
    if not listing:
        listing = StoreListing(
            business_id=business_id,
            product_id=product_id,
        )
        db.add(listing)
        await db.flush()

    if payload.is_published is not None:
        listing.is_published = payload.is_published
    if payload.listing_type is not None:
        listing.listing_type = _normalize_listing_type(payload.listing_type)
    if payload.headline is not None:
        listing.headline = payload.headline
    if payload.display_description is not None:
        listing.display_description = payload.display_description

    if listing.is_published:
        await _ensure_publish_requirements(db, listing)

    await db.commit()
    await db.refresh(listing)
    images = await _get_listing_images(db, listing.id)
    return _serialize_listing(listing, product, None, images)


async def upload_listing_images(
    db: AsyncSession,
    user_id: int,
    business_id: int,
    product_id: int,
    files,
):
    await _assert_business_role(db, user_id, business_id, ["business_owner", "manager"])
    product = await _get_product(db, product_id, business_id)
    result = await db.execute(
        select(StoreListing).where(
            StoreListing.business_id == business_id,
            StoreListing.product_id == product_id,
        )
    )
    listing = result.scalar_one_or_none()
    if not listing:
        listing = StoreListing(
            business_id=business_id,
            product_id=product_id,
            listing_type="product",
            is_published=False,
            headline=product.name,
            display_description=product.description,
        )
        db.add(listing)
        await db.commit()
        await db.refresh(listing)

    existing_images = await _get_listing_images(db, listing.id)
    next_sort = len(existing_images)
    for file in files:
        extension = Path(file.filename or "").suffix.lower()
        if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
            raise HTTPException(status_code=400, detail="Only JPG, PNG, or WEBP images are accepted")
        filename = f"{listing.id}-{uuid.uuid4().hex}{extension}"
        destination = STORE_IMAGE_DIR / filename
        content = await file.read()
        destination.write_bytes(content)
        db.add(
            StoreListingImage(
                listing_id=listing.id,
                file_path=f"/uploads/store/{filename}",
                sort_order=next_sort,
            )
        )
        next_sort += 1

    await db.commit()
    await db.refresh(listing)
    images = await _get_listing_images(db, listing.id)
    return _serialize_listing(listing, product, None, images)


async def delete_listing_image(
    db: AsyncSession,
    user_id: int,
    business_id: int,
    product_id: int,
    image_id: int,
):
    await _assert_business_role(db, user_id, business_id, ["business_owner", "manager"])
    product = await _get_product(db, product_id, business_id)
    result = await db.execute(
        select(StoreListing).where(
            StoreListing.business_id == business_id,
            StoreListing.product_id == product_id,
        )
    )
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    image = await db.get(StoreListingImage, image_id)
    if not image or image.listing_id != listing.id:
        raise HTTPException(status_code=404, detail="Image not found")

    existing_images = await _get_listing_images(db, listing.id)
    if listing.is_published and len(existing_images) <= 1:
        raise HTTPException(status_code=400, detail="Published listings must keep at least one image")

    if image.file_path:
        file_on_disk = STORE_IMAGE_DIR.parent.parent / image.file_path.lstrip("/")
        if file_on_disk.exists():
            file_on_disk.unlink()

    await db.delete(image)
    await db.commit()
    await db.refresh(listing)
    images = await _get_listing_images(db, listing.id)
    return _serialize_listing(listing, product, None, images)


async def create_store_order(db: AsyncSession, user_id: int, payload) -> dict:
    if not payload.items:
        raise HTTPException(status_code=400, detail="At least one item is required")

    listing_ids = [item.listing_id for item in payload.items]
    result = await db.execute(
        select(StoreListing, ProductInventory)
        .join(ProductInventory, ProductInventory.id == StoreListing.product_id)
        .where(StoreListing.id.in_(listing_ids))
    )
    rows = result.all()
    listing_map = {listing.id: (listing, product) for listing, product in rows}
    if len(listing_map) != len(set(listing_ids)):
        raise HTTPException(status_code=404, detail="One or more listings were not found")

    for item in payload.items:
        listing, product = listing_map[item.listing_id]
        if not listing.is_published:
            raise HTTPException(status_code=400, detail="One or more items are not published")
        if listing.business_id != payload.business_id:
            raise HTTPException(status_code=400, detail="Items must belong to the same business")
        if int(product.quantity or 0) < item.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient quantity for {product.name}")

    order = StoreOrder(
        business_id=payload.business_id,
        buyer_user_id=user_id,
        buyer_name=payload.buyer_name,
        buyer_phone=payload.buyer_phone,
        buyer_email=payload.buyer_email,
        status="pending",
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    items = []
    for item in payload.items:
        listing, product = listing_map[item.listing_id]
        order_item = StoreOrderItem(
            order_id=order.id,
            product_id=product.id,
            product_name_snapshot=product.name,
            unit_price_snapshot=product.price,
            quantity=item.quantity,
        )
        db.add(order_item)
        items.append(order_item)

    await db.commit()
    for item in items:
        await db.refresh(item)

    return {
        "id": order.id,
        "business_id": order.business_id,
        "buyer_user_id": order.buyer_user_id,
        "buyer_name": order.buyer_name,
        "buyer_phone": order.buyer_phone,
        "buyer_email": order.buyer_email,
        "status": order.status,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "items": items,
    }


async def list_user_store_orders(db: AsyncSession, user_id: int):
    result = await db.execute(
        select(StoreOrder, Business)
        .join(Business, Business.id == StoreOrder.business_id)
        .where(StoreOrder.buyer_user_id == user_id)
        .order_by(StoreOrder.id.desc())
    )
    rows = result.all()
    if not rows:
        return []

    order_ids = [order.id for order, _ in rows]
    items_result = await db.execute(
        select(StoreOrderItem).where(StoreOrderItem.order_id.in_(order_ids))
    )
    items = items_result.scalars().all()
    items_by_order = defaultdict(list)
    for item in items:
        items_by_order[item.order_id].append(item)

    return [
        {
            "id": order.id,
            "business_id": order.business_id,
            "buyer_user_id": order.buyer_user_id,
            "fulfilled_sale_id": order.fulfilled_sale_id,
            "buyer_name": order.buyer_name,
            "buyer_phone": order.buyer_phone,
            "buyer_email": order.buyer_email,
            "status": order.status,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
            "items": items_by_order.get(order.id, []),
            "business_name": business.name,
        }
        for order, business in rows
    ]


async def list_business_store_orders(
    db: AsyncSession,
    user_id: int,
    business_id: int,
):
    await _assert_business_role(db, user_id, business_id, ["business_owner", "manager"])
    result = await db.execute(
        select(StoreOrder)
        .where(StoreOrder.business_id == business_id)
        .order_by(StoreOrder.id.desc())
    )
    orders = result.scalars().all()
    if not orders:
        return []

    order_ids = [order.id for order in orders]
    items_result = await db.execute(
        select(StoreOrderItem).where(StoreOrderItem.order_id.in_(order_ids))
    )
    items = items_result.scalars().all()
    items_by_order = defaultdict(list)
    for item in items:
        items_by_order[item.order_id].append(item)

    return [
        {
            "id": order.id,
            "business_id": order.business_id,
            "buyer_user_id": order.buyer_user_id,
            "fulfilled_sale_id": order.fulfilled_sale_id,
            "buyer_name": order.buyer_name,
            "buyer_phone": order.buyer_phone,
            "buyer_email": order.buyer_email,
            "status": order.status,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
            "items": items_by_order.get(order.id, []),
            "business_name": None,
        }
        for order in orders
    ]


async def update_store_order_status(
    db: AsyncSession,
    user_id: int,
    business_id: int,
    order_id: int,
    status: str,
):
    await _assert_business_role(db, user_id, business_id, ["business_owner", "manager"])
    normalized = status.strip().lower()
    if normalized not in ORDER_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")

    order = await db.get(StoreOrder, order_id)
    if not order or order.business_id != business_id:
        raise HTTPException(status_code=404, detail="Order not found")

    previous_status = order.status
    order.status = normalized
    db.add(order)

    if normalized == "fulfilled" and previous_status != "fulfilled" and not order.fulfilled_sale_id:
        items_result = await db.execute(
            select(StoreOrderItem).where(StoreOrderItem.order_id == order_id)
        )
        items = items_result.scalars().all()
        sale_items: list[_StoreSaleItem] = []
        for item in items:
            if not item.product_id:
                continue
            product = await db.get(ProductInventory, item.product_id)
            if not product:
                continue
            if int(product.quantity or 0) < item.quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient quantity to fulfill {item.product_name_snapshot}",
                )
            sale_items.append(_StoreSaleItem(item.product_id, item.quantity))

        sale = await create_sale(
            db,
            user_id=user_id,
            business_id=business_id,
            data=_StoreFulfillmentSale(order.id, sale_items),
        )
        order.fulfilled_sale_id = sale.id
        db.add(order)

    await db.commit()
    await db.refresh(order)

    items_result = await db.execute(
        select(StoreOrderItem).where(StoreOrderItem.order_id == order_id)
    )
    items = items_result.scalars().all()
    return {
        "id": order.id,
        "business_id": order.business_id,
        "buyer_user_id": order.buyer_user_id,
        "fulfilled_sale_id": order.fulfilled_sale_id,
        "buyer_name": order.buyer_name,
        "buyer_phone": order.buyer_phone,
        "buyer_email": order.buyer_email,
        "status": order.status,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "items": items,
        "business_name": None,
    }
