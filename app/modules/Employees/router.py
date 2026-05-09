from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.modules.Business.service import get_user_businesses
from app.modules.Employees import service
from app.modules.Users.service import get_current_user, has_role
from app.schemas.employee import (
    AttendanceCreate,
    AttendanceResponse,
    EmployeeCreate,
    EmployeeResponse,
    EmployeeUpdate,
    LeaveCreate,
    LeaveResponse,
    LeaveUpdate,
)

router = APIRouter(prefix="/employees", tags=["Employees"])


async def resolve_business(current_user, db, business_id):
    data = await get_user_businesses(db, current_user.id)
    businesses = data.get("businesses", []) if isinstance(data, dict) else data or []
    if not businesses:
        raise HTTPException(status_code=400, detail="No business found")
    if business_id:
        if any(b.id == business_id for b in businesses):
            return business_id
        raise HTTPException(status_code=404, detail="Business not found")
    return businesses[0].id


@router.post("/", response_model=EmployeeResponse)
async def add_employee(
    data: EmployeeCreate,
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    if not await has_role(
        db,
        current_user.id,
        business_id,
        ["business_owner", "manager"],
    ):
        raise HTTPException(status_code=403, detail="Not allowed")
    return await service.add_employee(db, business_id, data)


@router.get("/", response_model=List[EmployeeResponse])
async def list_employees(
    business_id: Optional[int] = Query(None),
    active_only: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    return await service.list_employees(db, business_id, active_only)


@router.put("/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    employee_id: int,
    data: EmployeeUpdate,
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    if not await has_role(
        db,
        current_user.id,
        business_id,
        ["business_owner", "manager"],
    ):
        raise HTTPException(status_code=403, detail="Not allowed")
    return await service.update_employee(db, employee_id, business_id, data)


@router.delete("/{employee_id}")
async def deactivate_employee(
    employee_id: int,
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    if not await has_role(db, current_user.id, business_id, ["business_owner"]):
        raise HTTPException(status_code=403, detail="Only owner can remove employees")
    return await service.remove_employee(db, employee_id, business_id)


@router.post("/attendance", response_model=AttendanceResponse)
async def mark_attendance(
    data: AttendanceCreate,
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    if not await has_role(
        db,
        current_user.id,
        business_id,
        ["business_owner", "manager"],
    ):
        raise HTTPException(status_code=403, detail="Not allowed")
    return await service.mark_attendance(db, business_id, data)


@router.get("/attendance", response_model=List[AttendanceResponse])
async def get_attendance(
    business_id: Optional[int] = Query(None),
    employee_id: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    return await service.get_attendance(
        db,
        business_id,
        employee_id,
        start_date,
        end_date,
    )


@router.get("/attendance/{employee_id}/summary")
async def attendance_summary(
    employee_id: int,
    business_id: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    return await service.get_attendance_summary(
        db,
        employee_id,
        business_id,
        start_date,
        end_date,
    )


@router.get("/salary/{employee_id}/calculate")
async def salary_calculation(
    employee_id: int,
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    if not await has_role(
        db,
        current_user.id,
        business_id,
        ["business_owner", "manager"],
    ):
        raise HTTPException(status_code=403, detail="Not allowed")
    return await service.calculate_monthly_salary(
        db,
        employee_id,
        business_id,
        year,
        month,
    )


@router.post("/leaves", response_model=LeaveResponse)
async def apply_leave(
    data: LeaveCreate,
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    return await service.apply_leave(db, business_id, data)


@router.get("/leaves", response_model=List[LeaveResponse])
async def list_leaves(
    business_id: Optional[int] = Query(None),
    employee_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    return await service.list_leaves(db, business_id, employee_id, status)


@router.put("/leaves/{leave_id}/review", response_model=LeaveResponse)
async def review_leave(
    leave_id: int,
    data: LeaveUpdate,
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    if not await has_role(
        db,
        current_user.id,
        business_id,
        ["business_owner", "manager"],
    ):
        raise HTTPException(status_code=403, detail="Not allowed")
    return await service.review_leave(
        db,
        leave_id,
        business_id,
        data,
        current_user.id,
    )
