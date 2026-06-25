import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hr_payroll.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_code TEXT NOT NULL UNIQUE,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT DEFAULT '',
            department_id INTEGER,
            designation TEXT DEFAULT '',
            date_of_joining TEXT NOT NULL,
            date_of_birth TEXT DEFAULT '',
            gender TEXT DEFAULT '',
            address TEXT DEFAULT '',
            base_salary REAL NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department_id) REFERENCES departments(id)
        );

        CREATE TABLE IF NOT EXISTS payroll (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            pay_period TEXT NOT NULL,
            base_salary REAL NOT NULL,
            hra REAL NOT NULL DEFAULT 0,
            transport_allowance REAL NOT NULL DEFAULT 0,
            bonus REAL NOT NULL DEFAULT 0,
            overtime_hours REAL NOT NULL DEFAULT 0,
            overtime_rate REAL NOT NULL DEFAULT 0,
            gross_salary REAL NOT NULL,
            tax_deduction REAL NOT NULL DEFAULT 0,
            insurance_deduction REAL NOT NULL DEFAULT 0,
            other_deductions REAL NOT NULL DEFAULT 0,
            net_salary REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        );

        CREATE TABLE IF NOT EXISTS leave_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            leave_type TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            days INTEGER NOT NULL,
            reason TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        );

        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            check_in TEXT,
            check_out TEXT,
            status TEXT NOT NULL DEFAULT 'present',
            FOREIGN KEY (employee_id) REFERENCES employees(id),
            UNIQUE(employee_id, date)
        );
    """)
    if conn.execute("SELECT COUNT(*) FROM departments").fetchone()[0] == 0:
        conn.executemany("INSERT INTO departments (name, description) VALUES (?, ?)", [
            ("Engineering", "Software development and IT"),
            ("Human Resources", "HR operations and recruitment"),
            ("Finance", "Accounting and financial planning"),
            ("Marketing", "Marketing and communications"),
            ("Sales", "Sales and business development"),
            ("Operations", "Day-to-day business operations"),
        ])
    conn.commit()
    conn.close()
