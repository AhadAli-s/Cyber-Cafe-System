import sys
import os
import bcrypt

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from database.database import SessionLocal
from database.models import Employee, AuditLog, utc_now
from datetime import datetime

# Currently logged-in employee, set after successful login.
# Simple module-level state since only one person operates the Admin app at a time.
current_employee = None

# What each role is allowed to do. Checked via has_permission().
ROLE_PERMISSIONS = {
    "SuperAdmin": {
        "manage_sessions", "manage_billing", "manage_pricing",
        "manage_staff", "view_reports", "remote_commands",
    },
    "Manager": {
        "manage_sessions", "manage_billing", "view_reports", "remote_commands",
    },
    "Cashier": {
        "manage_sessions", "manage_billing", "remote_commands",
    },
}


def login(username: str, password: str):
    """
    Verifies credentials against the employees table.
    Returns (success: bool, message: str)
    """
    global current_employee
    db = SessionLocal()
    try:
        employee = db.query(Employee).filter_by(Username=username).first()
        if not employee:
            return False, "Invalid username or password"

        if employee.Status != "Active":
            return False, "This account is not active"

        if not bcrypt.checkpw(password.encode("utf-8"), employee.PasswordHash.encode("utf-8")):
            return False, "Invalid username or password"

        current_employee = {
            "EmployeeID": employee.EmployeeID,
            "FullName": employee.FullName,
            "Role": employee.Role,
            "Username": employee.Username,
        }
        log_action(employee.EmployeeID, f"Logged in as {employee.Role}")
        return True, "Login successful"

    finally:
        db.close()


def logout():
    global current_employee
    if current_employee:
        log_action(current_employee["EmployeeID"], "Logged out")
    current_employee = None


def has_permission(permission: str) -> bool:
    if current_employee is None:
        return False
    role = current_employee["Role"]
    return permission in ROLE_PERMISSIONS.get(role, set())


def log_action(employee_id: int, description: str, ip_address: str = None):
    """Writes an entry to AuditLogs — used for any sensitive/administrative action"""
    db = SessionLocal()
    try:
        entry = AuditLog(
            EmployeeID=employee_id,
            ActionDescription=description,
            Timestamp=utc_now(),
            IPAddress=ip_address
        )
        db.add(entry)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()