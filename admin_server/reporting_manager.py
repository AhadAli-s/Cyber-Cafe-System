import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from database.database import SessionLocal
from database.models import Transaction, AuditLog, Employee, utc_now


def get_revenue_summary(start_date: datetime, end_date: datetime):
    """
    Returns a dict: {"SessionTime": x, "Print": y, "POS": z, "Total": total}
    for all Transactions in [start_date, end_date].
    """
    db = SessionLocal()
    try:
        transactions = (
            db.query(Transaction)
            .filter(Transaction.Timestamp >= start_date, Transaction.Timestamp <= end_date)
            .all()
        )
        summary = {"SessionTime": 0.0, "Print": 0.0, "POS": 0.0}
        for t in transactions:
            category = t.Category or "SessionTime"
            summary[category] = summary.get(category, 0.0) + t.AmountPaid

        summary["Total"] = round(sum(summary.values()), 2)
        for key in ("SessionTime", "Print", "POS"):
            summary[key] = round(summary[key], 2)
        summary["TransactionCount"] = len(transactions)
        return summary
    finally:
        db.close()


def get_date_range_for_preset(preset: str):
    """Returns (start_date, end_date) datetimes for 'Today', 'This Week', 'This Month'."""
    now = utc_now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if preset == "Today":
        return today_start, now
    elif preset == "This Week":
        start = today_start - timedelta(days=today_start.weekday())
        return start, now
    elif preset == "This Month":
        start = today_start.replace(day=1)
        return start, now
    else:
        return today_start, now


def get_audit_logs(start_date: datetime = None, end_date: datetime = None, limit: int = 200):
    """Returns audit log entries with employee names, most recent first"""
    db = SessionLocal()
    try:
        query = db.query(AuditLog, Employee.FullName).join(
            Employee, AuditLog.EmployeeID == Employee.EmployeeID
        )
        if start_date:
            query = query.filter(AuditLog.Timestamp >= start_date)
        if end_date:
            query = query.filter(AuditLog.Timestamp <= end_date)

        results = query.order_by(AuditLog.Timestamp.desc()).limit(limit).all()
        return [
            {
                "timestamp": log.Timestamp,
                "employee_name": full_name,
                "action": log.ActionDescription,
            }
            for log, full_name in results
        ]
    finally:
        db.close()