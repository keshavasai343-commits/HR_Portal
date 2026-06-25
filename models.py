from pydantic import BaseModel, EmailStr
from typing import Optional


class DepartmentCreate(BaseModel):
    name: str
    description: str = ""


class EmployeeCreate(BaseModel):
    emp_code: str
    first_name: str
    last_name: str
    email: str
    phone: str = ""
    department_id: Optional[int] = None
    designation: str = ""
    date_of_joining: str
    date_of_birth: str = ""
    gender: str = ""
    address: str = ""
    base_salary: float = 0


class EmployeeUpdate(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: str = ""
    department_id: Optional[int] = None
    designation: str = ""
    date_of_joining: str
    date_of_birth: str = ""
    gender: str = ""
    address: str = ""
    base_salary: float = 0


class PayrollGenerate(BaseModel):
    employee_id: int
    pay_period: str
    bonus: float = 0
    overtime_hours: float = 0
    other_deductions: float = 0


class LeaveCreate(BaseModel):
    employee_id: int
    leave_type: str
    start_date: str
    end_date: str
    reason: str = ""


class AttendanceAction(BaseModel):
    employee_id: int
    action: str  # "check_in" or "check_out"
