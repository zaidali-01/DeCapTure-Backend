from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Attendance, Employee, LeaveRequest
from app.schemas.employee import (
    AttendanceCreate,
    EmployeeCreate,
    EmployeeUpdate,
    LeaveCreate,
    LeaveUpdate,
)


async def add_employee(
    db: AsyncSession,
    business_id: int,
    data: EmployeeCreate,
) -> Employee:
    result = await db.execute(
        select(Employee).where(
            Employee.user_id == data.user_id,
            Employee.business_id == business_id,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="User is already an employee of this business",
        )

    employee = Employee(
        user_id=data.user_id,
        business_id=business_id,
        designation=data.designation,
        department=data.department,
        joined_date=data.joined_date,
        salary=data.salary or 0,
    )
    db.add(employee)
    await db.commit()
    await db.refresh(employee)
    return employee


async def list_employees(
    db: AsyncSession,
    business_id: int,
    active_only: bool = True,
) -> list:
    query = select(Employee).where(Employee.business_id == business_id)
    if active_only:
        query = query.where(Employee.is_active == True)
    result = await db.execute(query)
    return result.scalars().all()


async def get_employee(
    db: AsyncSession,
    employee_id: int,
    business_id: int,
) -> Employee:
    result = await db.execute(
        select(Employee).where(
            Employee.id == employee_id,
            Employee.business_id == business_id,
        )
    )
    emp = result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return emp


async def update_employee(
    db: AsyncSession,
    employee_id: int,
    business_id: int,
    data: EmployeeUpdate,
) -> Employee:
    emp = await get_employee(db, employee_id, business_id)
    for field, value in data.dict(exclude_unset=True).items():
        setattr(emp, field, value)
    db.add(emp)
    await db.commit()
    await db.refresh(emp)
    return emp


async def remove_employee(
    db: AsyncSession,
    employee_id: int,
    business_id: int,
) -> dict:
    emp = await get_employee(db, employee_id, business_id)
    emp.is_active = False
    db.add(emp)
    await db.commit()
    return {"message": "Employee deactivated"}


async def mark_attendance(
    db: AsyncSession,
    business_id: int,
    data: AttendanceCreate,
) -> Attendance:
    await get_employee(db, data.employee_id, business_id)

    result = await db.execute(
        select(Attendance).where(
            Attendance.employee_id == data.employee_id,
            Attendance.business_id == business_id,
            Attendance.date == data.date,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.status = data.status
        existing.check_in = data.check_in
        existing.check_out = data.check_out
        existing.notes = data.notes
        db.add(existing)
        await db.commit()
        await db.refresh(existing)
        return existing

    attendance = Attendance(business_id=business_id, **data.dict())
    db.add(attendance)
    await db.commit()
    await db.refresh(attendance)
    return attendance


async def get_attendance(
    db: AsyncSession,
    business_id: int,
    employee_id: int = None,
    start_date: date = None,
    end_date: date = None,
) -> list:
    query = select(Attendance).where(Attendance.business_id == business_id)
    if employee_id:
        query = query.where(Attendance.employee_id == employee_id)
    if start_date:
        query = query.where(Attendance.date >= start_date)
    if end_date:
        query = query.where(Attendance.date <= end_date)
    query = query.order_by(Attendance.date.desc())
    result = await db.execute(query)
    return result.scalars().all()


async def get_attendance_summary(
    db: AsyncSession,
    employee_id: int,
    business_id: int,
    start_date: date = None,
    end_date: date = None,
) -> dict:
    await get_employee(db, employee_id, business_id)

    query = select(Attendance).where(
        Attendance.employee_id == employee_id,
        Attendance.business_id == business_id,
    )
    if start_date:
        query = query.where(Attendance.date >= start_date)
    if end_date:
        query = query.where(Attendance.date <= end_date)
    result = await db.execute(query)
    records = result.scalars().all()

    summary = {
        "employee_id": employee_id,
        "total_present": 0,
        "total_absent": 0,
        "total_half_day": 0,
        "total_on_leave": 0,
        "total_days": len(records),
    }
    for r in records:
        if r.status == "present":
            summary["total_present"] += 1
        elif r.status == "absent":
            summary["total_absent"] += 1
        elif r.status == "half_day":
            summary["total_half_day"] += 1
        elif r.status == "on_leave":
            summary["total_on_leave"] += 1
    return summary


async def apply_leave(
    db: AsyncSession,
    business_id: int,
    data: LeaveCreate,
) -> LeaveRequest:
    await get_employee(db, data.employee_id, business_id)
    if data.end_date < data.start_date:
        raise HTTPException(status_code=400, detail="End date cannot be before start date")

    leave = LeaveRequest(business_id=business_id, **data.dict())
    db.add(leave)
    await db.commit()
    await db.refresh(leave)
    return leave


async def list_leaves(
    db: AsyncSession,
    business_id: int,
    employee_id: int = None,
    status: str = None,
) -> list:
    query = select(LeaveRequest).where(LeaveRequest.business_id == business_id)
    if employee_id:
        query = query.where(LeaveRequest.employee_id == employee_id)
    if status:
        query = query.where(LeaveRequest.status == status)
    query = query.order_by(LeaveRequest.applied_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


async def review_leave(
    db: AsyncSession,
    leave_id: int,
    business_id: int,
    data: LeaveUpdate,
    agent_user_id: int = None,
) -> LeaveRequest:
    from datetime import datetime, timedelta

    if data.status not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="Status must be approved or rejected")

    result = await db.execute(
        select(LeaveRequest).where(
            LeaveRequest.id == leave_id,
            LeaveRequest.business_id == business_id,
        )
    )
    leave = result.scalar_one_or_none()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")

    leave.status = data.status
    leave.reviewed_at = datetime.utcnow()
    db.add(leave)

    if data.status == "approved":
        current = leave.start_date
        while current <= leave.end_date:
            existing = await db.execute(
                select(Attendance).where(
                    Attendance.employee_id == leave.employee_id,
                    Attendance.business_id == business_id,
                    Attendance.date == current,
                )
            )
            att = existing.scalar_one_or_none()
            if att:
                att.status = "on_leave"
                db.add(att)
            else:
                db.add(
                    Attendance(
                        employee_id=leave.employee_id,
                        business_id=business_id,
                        date=current,
                        status="on_leave",
                    )
                )
            current += timedelta(days=1)

    employee = await get_employee(db, leave.employee_id, business_id)

    from app.modules.Notifications.service import create_notification

    await create_notification(
        db=db,
        user_id=employee.user_id,
        type="leave_request",
        title=f"Leave request {data.status}",
        body=f"Your leave from {leave.start_date} to {leave.end_date} was {data.status}.",
        business_id=business_id,
        entity_type="leave",
        entity_id=leave.id,
    )

    from app.modules.Audit.service import log as audit_log

    await audit_log(
        db,
        action=f"leave_{data.status}",
        user_id=agent_user_id,
        business_id=business_id,
        entity_type="leave",
        entity_id=leave_id,
    )

    await db.commit()
    await db.refresh(leave)
    return leave


async def calculate_monthly_salary(
    db: AsyncSession,
    employee_id: int,
    business_id: int,
    year: int,
    month: int,
) -> dict:
    """Calculate net salary based on attendance for the month."""
    import calendar

    emp = await get_employee(db, employee_id, business_id)
    days_in_month = calendar.monthrange(year, month)[1]
    start = date(year, month, 1)
    end = date(year, month, days_in_month)

    result = await db.execute(
        select(Attendance).where(
            Attendance.employee_id == employee_id,
            Attendance.business_id == business_id,
            Attendance.date >= start,
            Attendance.date <= end,
        )
    )
    records = result.scalars().all()

    present = sum(1 for r in records if r.status == "present")
    half_day = sum(1 for r in records if r.status == "half_day")
    on_leave = sum(1 for r in records if r.status == "on_leave")
    absent = sum(1 for r in records if r.status == "absent")

    working_days = present + half_day * 0.5 + on_leave
    per_day = emp.salary / days_in_month if days_in_month else 0
    net_salary = round(per_day * working_days, 2)

    return {
        "employee_id": employee_id,
        "year": year,
        "month": month,
        "gross_salary": emp.salary,
        "working_days_counted": working_days,
        "days_present": present,
        "days_half": half_day,
        "days_on_leave": on_leave,
        "days_absent": absent,
        "net_salary": net_salary,
    }
