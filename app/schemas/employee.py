from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class EmployeeCreate(BaseModel):
    user_id: int
    designation: Optional[str] = None
    department: Optional[str] = None
    joined_date: Optional[date] = None
    salary: Optional[int] = 0


class EmployeeUpdate(BaseModel):
    designation: Optional[str] = None
    department: Optional[str] = None
    salary: Optional[int] = None
    is_active: Optional[bool] = None


class EmployeeResponse(BaseModel):
    id: int
    user_id: int
    business_id: int
    designation: Optional[str]
    department: Optional[str]
    joined_date: Optional[date]
    salary: int
    is_active: bool

    class Config:
        from_attributes = True


class AttendanceCreate(BaseModel):
    employee_id: int
    date: date
    status: str  # present | absent | half_day | on_leave
    check_in: Optional[datetime] = None
    check_out: Optional[datetime] = None
    notes: Optional[str] = None


class AttendanceResponse(AttendanceCreate):
    id: int
    business_id: int

    class Config:
        from_attributes = True


class LeaveCreate(BaseModel):
    employee_id: int
    leave_type: str
    start_date: date
    end_date: date
    reason: Optional[str] = None


class LeaveUpdate(BaseModel):
    status: str  # approved | rejected


class LeaveResponse(BaseModel):
    id: int
    employee_id: int
    business_id: int
    leave_type: str
    start_date: date
    end_date: date
    reason: Optional[str]
    status: str
    applied_at: datetime

    class Config:
        from_attributes = True


class AttendanceSummary(BaseModel):
    employee_id: int
    total_present: int
    total_absent: int
    total_half_day: int
    total_on_leave: int
    total_days: int
