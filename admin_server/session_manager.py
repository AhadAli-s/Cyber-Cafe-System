import sys
import os
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "database"))

from database import SessionLocal
from models import Session, Computer, User, PricingPlan, Transaction, utc_now


def start_session(computer_id: int, session_type: str = "Postpaid",
                   user_id: int = None, plan_id: int = None):
    """
    Starts a new session on a computer.
    session_type: 'Prepaid' or 'Postpaid'
    For Prepaid sessions, plan_id (a package/duration) is typically required.
    Returns (success: bool, message: str, session_id: int | None)
    """
    db = SessionLocal()
    try:
        computer = db.query(Computer).filter_by(ComputerID=computer_id).first()
        if not computer:
            return False, "Computer not found", None

        if computer.CurrentStatus == "Occupied":
            return False, "Computer already has an active session", None

        new_session = Session(
            ComputerID=computer_id,
            UserID=user_id,
            PlanID=plan_id,
            SessionType=session_type,
            StartTime=utc_now(),
            TotalCost=0.0
        )
        db.add(new_session)
        computer.CurrentStatus = "Occupied"
        db.commit()
        db.refresh(new_session)
        return True, "Session started", new_session.SessionID

    except Exception as e:
        db.rollback()
        return False, str(e), None
    finally:
        db.close()


def calculate_cost(session: Session, plan: PricingPlan) -> float:
    """
    Pro-rata minute pricing based on elapsed time and the plan's hourly rate.
    Package plans (IsPackage=True) charge the flat plan rate regardless of
    exact elapsed time, as long as MinDuration is met.
    """
    end_time = session.EndTime or utc_now()
    elapsed_minutes = (end_time - session.StartTime).total_seconds() / 60.0

    if plan is None:
        # No plan assigned — fall back to a zero-cost guest session (should not normally happen)
        return 0.0

    if plan.IsPackage:
        # Flat package rate once minimum duration is reached; pro-rata if ended early
        if elapsed_minutes >= plan.MinDuration:
            return round(plan.HourlyRate, 2)
        else:
            per_minute_rate = plan.HourlyRate / plan.MinDuration
            return round(per_minute_rate * elapsed_minutes, 2)
    else:
        per_minute_rate = plan.HourlyRate / 60.0
        return round(per_minute_rate * elapsed_minutes, 2)


def get_elapsed_minutes(session: Session) -> float:
    end_time = session.EndTime or utc_now()
    return (end_time - session.StartTime).total_seconds() / 60.0


def end_session(session_id: int, payment_method: str = "Cash"):
    """
    Ends a session, calculates final cost, creates a Transaction record,
    and frees up the computer.
    Returns (success: bool, message: str, total_cost: float | None)
    """
    db = SessionLocal()
    try:
        session = db.query(Session).filter_by(SessionID=session_id).first()
        if not session:
            return False, "Session not found", None

        if session.EndTime is not None:
            return False, "Session already ended", None

        session.EndTime = utc_now()

        plan = None
        if session.PlanID:
            plan = db.query(PricingPlan).filter_by(PlanID=session.PlanID).first()

        total_cost = calculate_cost(session, plan)
        session.TotalCost = total_cost

        # Record the payment
        transaction = Transaction(
            SessionID=session.SessionID,
            AmountPaid=total_cost,
            PaymentMethod=payment_method,
            Timestamp=utc_now(),
            Category="SessionTime"
        )
        db.add(transaction)

        # Free up the computer
        computer = db.query(Computer).filter_by(ComputerID=session.ComputerID).first()
        if computer:
            computer.CurrentStatus = "Available"

        db.commit()
        return True, "Session ended", total_cost

    except Exception as e:
        db.rollback()
        return False, str(e), None
    finally:
        db.close()


def top_up_prepaid_balance(user_id: int, amount: float):
    """Adds funds to a member's prepaid balance"""
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(UserID=user_id).first()
        if not user:
            return False, "User not found"

        user.PrepaidBalance += amount
        db.commit()
        return True, f"Balance updated: {user.PrepaidBalance}"

    except Exception as e:
        db.rollback()
        return False, str(e)
    finally:
        db.close()


def get_active_session_for_computer(computer_id: int):
    """Returns the currently active (not yet ended) session for a computer, or None"""
    db = SessionLocal()
    try:
        session = (
            db.query(Session)
            .filter_by(ComputerID=computer_id, EndTime=None)
            .order_by(Session.StartTime.desc())
            .first()
        )
        return session
    finally:
        db.close()