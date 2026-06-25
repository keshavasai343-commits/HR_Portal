from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from datetime import datetime, date
from typing import Optional
import sqlite3
import os

from database import get_db, init_db
from models import (
    DepartmentCreate, EmployeeCreate, EmployeeUpdate,
    PayrollGenerate, LeaveCreate, AttendanceAction,
)

init_db()

app = FastAPI(title="HR/Payroll System", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def row_to_dict(row):
    if row is None:
        return None
    return dict(row)


def rows_to_list(rows):
    return [dict(r) for r in rows]


# ── Dashboard ─────────────────────────────────────────────

@app.get("/api/dashboard")
def dashboard():
    conn = get_db()
    total_employees = conn.execute("SELECT COUNT(*) c FROM employees WHERE is_active=1").fetchone()["c"]
    total_departments = conn.execute("SELECT COUNT(*) c FROM departments").fetchone()["c"]
    pending_leaves = conn.execute("SELECT COUNT(*) c FROM leave_requests WHERE status='pending'").fetchone()["c"]
    total_payroll = conn.execute("SELECT COALESCE(SUM(net_salary),0) t FROM payroll WHERE status='processed'").fetchone()["t"]

    recent_employees = rows_to_list(conn.execute("""
        SELECT e.*, d.name as department_name
        FROM employees e LEFT JOIN departments d ON e.department_id = d.id
        WHERE e.is_active = 1 ORDER BY e.created_at DESC LIMIT 5
    """).fetchall())

    recent_leaves = rows_to_list(conn.execute("""
        SELECT l.*, e.first_name, e.last_name, e.emp_code
        FROM leave_requests l JOIN employees e ON l.employee_id = e.id
        ORDER BY l.created_at DESC LIMIT 5
    """).fetchall())

    dept_counts = rows_to_list(conn.execute("""
        SELECT d.name, COUNT(e.id) as count
        FROM departments d LEFT JOIN employees e ON d.id = e.department_id AND e.is_active = 1
        GROUP BY d.id ORDER BY count DESC
    """).fetchall())

    conn.close()
    return {
        "total_employees": total_employees,
        "total_departments": total_departments,
        "pending_leaves": pending_leaves,
        "total_payroll": total_payroll,
        "recent_employees": recent_employees,
        "recent_leaves": recent_leaves,
        "dept_counts": dept_counts,
    }


# ── Departments ───────────────────────────────────────────

@app.get("/api/departments")
def list_departments():
    conn = get_db()
    rows = conn.execute("""
        SELECT d.*, COUNT(e.id) as employee_count
        FROM departments d LEFT JOIN employees e ON d.id = e.department_id AND e.is_active = 1
        GROUP BY d.id ORDER BY d.name
    """).fetchall()
    conn.close()
    return rows_to_list(rows)


@app.post("/api/departments")
def create_department(dept: DepartmentCreate):
    conn = get_db()
    try:
        cur = conn.execute("INSERT INTO departments (name, description) VALUES (?, ?)",
                           (dept.name, dept.description))
        conn.commit()
        dept_id = cur.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(400, "Department already exists")
    conn.close()
    return {"id": dept_id, "message": "Department created"}


@app.delete("/api/departments/{dept_id}")
def delete_department(dept_id: int):
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) c FROM employees WHERE department_id=? AND is_active=1",
                         (dept_id,)).fetchone()["c"]
    if count > 0:
        conn.close()
        raise HTTPException(400, "Cannot delete department with active employees")
    conn.execute("DELETE FROM departments WHERE id=?", (dept_id,))
    conn.commit()
    conn.close()
    return {"message": "Department deleted"}


# ── Employees ─────────────────────────────────────────────

@app.get("/api/employees")
def list_employees(search: str = "", department: str = ""):
    conn = get_db()
    query = """
        SELECT e.*, d.name as department_name
        FROM employees e LEFT JOIN departments d ON e.department_id = d.id
        WHERE e.is_active = 1
    """
    params = []
    if search:
        query += " AND (e.first_name LIKE ? OR e.last_name LIKE ? OR e.emp_code LIKE ? OR e.email LIKE ?)"
        params.extend([f"%{search}%"] * 4)
    if department:
        query += " AND e.department_id = ?"
        params.append(department)
    query += " ORDER BY e.created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows_to_list(rows)


@app.get("/api/employees/next-code")
def next_employee_code():
    conn = get_db()
    next_id = conn.execute("SELECT COALESCE(MAX(id),0)+1 n FROM employees").fetchone()["n"]
    conn.close()
    return {"code": f"EMP{next_id:04d}"}


@app.get("/api/employees/{emp_id}")
def get_employee(emp_id: int):
    conn = get_db()
    emp = row_to_dict(conn.execute("""
        SELECT e.*, d.name as department_name
        FROM employees e LEFT JOIN departments d ON e.department_id = d.id WHERE e.id=?
    """, (emp_id,)).fetchone())
    if not emp:
        conn.close()
        raise HTTPException(404, "Employee not found")

    payrolls = rows_to_list(conn.execute(
        "SELECT * FROM payroll WHERE employee_id=? ORDER BY created_at DESC", (emp_id,)).fetchall())
    leaves = rows_to_list(conn.execute(
        "SELECT * FROM leave_requests WHERE employee_id=? ORDER BY created_at DESC", (emp_id,)).fetchall())
    attendance = rows_to_list(conn.execute(
        "SELECT * FROM attendance WHERE employee_id=? ORDER BY date DESC LIMIT 30", (emp_id,)).fetchall())
    conn.close()
    return {**emp, "payrolls": payrolls, "leaves": leaves, "attendance": attendance}


@app.post("/api/employees")
def create_employee(emp: EmployeeCreate):
    conn = get_db()
    try:
        cur = conn.execute("""
            INSERT INTO employees (emp_code, first_name, last_name, email, phone,
                department_id, designation, date_of_joining, date_of_birth, gender,
                address, base_salary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (emp.emp_code, emp.first_name, emp.last_name, emp.email, emp.phone,
              emp.department_id, emp.designation, emp.date_of_joining, emp.date_of_birth,
              emp.gender, emp.address, emp.base_salary))
        conn.commit()
        emp_id = cur.lastrowid
    except sqlite3.IntegrityError as e:
        conn.close()
        raise HTTPException(400, str(e))
    conn.close()
    return {"id": emp_id, "message": "Employee created"}


@app.put("/api/employees/{emp_id}")
def update_employee(emp_id: int, emp: EmployeeUpdate):
    conn = get_db()
    try:
        conn.execute("""
            UPDATE employees SET first_name=?, last_name=?, email=?, phone=?,
                department_id=?, designation=?, date_of_joining=?, date_of_birth=?,
                gender=?, address=?, base_salary=?
            WHERE id=?
        """, (emp.first_name, emp.last_name, emp.email, emp.phone, emp.department_id,
              emp.designation, emp.date_of_joining, emp.date_of_birth, emp.gender,
              emp.address, emp.base_salary, emp_id))
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.close()
        raise HTTPException(400, str(e))
    conn.close()
    return {"message": "Employee updated"}


@app.delete("/api/employees/{emp_id}")
def deactivate_employee(emp_id: int):
    conn = get_db()
    conn.execute("UPDATE employees SET is_active=0 WHERE id=?", (emp_id,))
    conn.commit()
    conn.close()
    return {"message": "Employee deactivated"}


# ── Payroll ───────────────────────────────────────────────

@app.get("/api/payroll")
def list_payroll():
    conn = get_db()
    payrolls = rows_to_list(conn.execute("""
        SELECT p.*, e.first_name, e.last_name, e.emp_code, d.name as department_name
        FROM payroll p JOIN employees e ON p.employee_id = e.id
        LEFT JOIN departments d ON e.department_id = d.id
        ORDER BY p.created_at DESC
    """).fetchall())
    summary = rows_to_list(conn.execute("""
        SELECT pay_period, COUNT(*) as count, SUM(gross_salary) as total_gross,
               SUM(net_salary) as total_net, status
        FROM payroll GROUP BY pay_period, status ORDER BY pay_period DESC
    """).fetchall())
    conn.close()
    return {"payrolls": payrolls, "summary": summary}


@app.post("/api/payroll/generate")
def generate_payroll(items: list[PayrollGenerate]):
    conn = get_db()
    generated = 0
    for item in items:
        emp = conn.execute("SELECT * FROM employees WHERE id=? AND is_active=1",
                           (item.employee_id,)).fetchone()
        if not emp:
            continue
        existing = conn.execute("SELECT id FROM payroll WHERE employee_id=? AND pay_period=?",
                                (item.employee_id, item.pay_period)).fetchone()
        if existing:
            continue

        base = emp["base_salary"]
        hra = round(base * 0.40, 2)
        transport = round(base * 0.10, 2)
        ot_rate = round(base / 160, 2)
        gross = round(base + hra + transport + item.bonus + (item.overtime_hours * ot_rate), 2)

        if gross <= 25000:
            tax = 0
        elif gross <= 50000:
            tax = round(gross * 0.10, 2)
        elif gross <= 100000:
            tax = round(gross * 0.20, 2)
        else:
            tax = round(gross * 0.30, 2)

        insurance = round(base * 0.02, 2)
        net = round(gross - tax - insurance - item.other_deductions, 2)

        conn.execute("""
            INSERT INTO payroll (employee_id, pay_period, base_salary, hra,
                transport_allowance, bonus, overtime_hours, overtime_rate,
                gross_salary, tax_deduction, insurance_deduction, other_deductions,
                net_salary, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft')
        """, (item.employee_id, item.pay_period, base, hra, transport, item.bonus,
              item.overtime_hours, ot_rate, gross, tax, insurance, item.other_deductions, net))
        generated += 1

    conn.commit()
    conn.close()
    return {"message": f"Payroll generated for {generated} employee(s)"}


@app.post("/api/payroll/{payroll_id}/process")
def process_payroll(payroll_id: int):
    conn = get_db()
    conn.execute("UPDATE payroll SET status='processed' WHERE id=?", (payroll_id,))
    conn.commit()
    conn.close()
    return {"message": "Payroll processed"}


# ── Leaves ────────────────────────────────────────────────

@app.get("/api/leaves")
def list_leaves(status: str = ""):
    conn = get_db()
    query = """
        SELECT l.*, e.first_name, e.last_name, e.emp_code
        FROM leave_requests l JOIN employees e ON l.employee_id = e.id
    """
    params = []
    if status:
        query += " WHERE l.status = ?"
        params.append(status)
    query += " ORDER BY l.created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows_to_list(rows)


@app.post("/api/leaves")
def create_leave(leave: LeaveCreate):
    start = datetime.strptime(leave.start_date, "%Y-%m-%d").date()
    end = datetime.strptime(leave.end_date, "%Y-%m-%d").date()
    days = (end - start).days + 1
    if days < 1:
        raise HTTPException(400, "End date must be after start date")

    conn = get_db()
    cur = conn.execute("""
        INSERT INTO leave_requests (employee_id, leave_type, start_date, end_date, days, reason)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (leave.employee_id, leave.leave_type, leave.start_date, leave.end_date, days, leave.reason))
    conn.commit()
    leave_id = cur.lastrowid
    conn.close()
    return {"id": leave_id, "message": "Leave request submitted"}


@app.post("/api/leaves/{leave_id}/approve")
def approve_leave(leave_id: int):
    conn = get_db()
    conn.execute("UPDATE leave_requests SET status='approved' WHERE id=?", (leave_id,))
    conn.commit()
    conn.close()
    return {"message": "Leave approved"}


@app.post("/api/leaves/{leave_id}/reject")
def reject_leave(leave_id: int):
    conn = get_db()
    conn.execute("UPDATE leave_requests SET status='rejected' WHERE id=?", (leave_id,))
    conn.commit()
    conn.close()
    return {"message": "Leave rejected"}


# ── Attendance ────────────────────────────────────────────

@app.get("/api/attendance")
def get_attendance():
    conn = get_db()
    today = date.today().isoformat()
    today_records = rows_to_list(conn.execute("""
        SELECT a.*, e.first_name, e.last_name, e.emp_code
        FROM attendance a JOIN employees e ON a.employee_id = e.id
        WHERE a.date = ? ORDER BY a.check_in
    """, (today,)).fetchall())
    conn.close()
    return {"date": today, "records": today_records}


@app.post("/api/attendance")
def mark_attendance(data: AttendanceAction):
    conn = get_db()
    today = date.today().isoformat()
    now = datetime.now().strftime("%H:%M:%S")

    existing = row_to_dict(conn.execute(
        "SELECT * FROM attendance WHERE employee_id=? AND date=?",
        (data.employee_id, today)).fetchone())

    if data.action == "check_in":
        if existing:
            conn.close()
            raise HTTPException(400, "Already checked in today")
        conn.execute("INSERT INTO attendance (employee_id, date, check_in, status) VALUES (?,?,?,'present')",
                     (data.employee_id, today, now))
        conn.commit()
        conn.close()
        return {"message": f"Checked in at {now}"}

    elif data.action == "check_out":
        if not existing:
            conn.close()
            raise HTTPException(400, "Not checked in yet")
        if existing.get("check_out"):
            conn.close()
            raise HTTPException(400, "Already checked out")
        conn.execute("UPDATE attendance SET check_out=? WHERE id=?", (now, existing["id"]))
        conn.commit()
        conn.close()
        return {"message": f"Checked out at {now}"}

    conn.close()
    raise HTTPException(400, "Invalid action")


# ── Serve React frontend in production ────────────────────

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

if os.path.isdir(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

    @app.get("/{path:path}")
    def serve_frontend(path: str):
        file_path = os.path.join(STATIC_DIR, path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
