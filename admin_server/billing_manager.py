import sys
import os
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from database.database import SessionLocal
from database.models import PrintLog, Inventory, Transaction, Session, utc_now

# Rs. per page, by (paper_size, is_color)
PRINT_RATES = {
    ("A4", False): 5.0,
    ("A4", True): 15.0,
    ("A3", False): 10.0,
    ("A3", True): 25.0,
}


def record_print_job(session_id: int, pages: int, is_color: bool, paper_size: str = "A4",
                      payment_method: str = "Cash"):
    if pages <= 0:
        return False, "Page count must be positive", None

    rate = PRINT_RATES.get((paper_size, is_color))
    if rate is None:
        return False, f"No rate defined for {paper_size} / {'Color' if is_color else 'B&W'}", None

    total_charge = round(rate * pages, 2)

    db = SessionLocal()
    try:
        session = db.query(Session).filter_by(SessionID=session_id).first()
        if not session:
            return False, "Session not found", None

        print_log = PrintLog(
            SessionID=session_id,
            PagesCount=pages,
            IsColor=is_color,
            PaperSize=paper_size,
            TotalCharge=total_charge
        )
        db.add(print_log)

        transaction = Transaction(
            SessionID=session_id,
            AmountPaid=total_charge,
            PaymentMethod=payment_method,
            Timestamp=utc_now(),
            Category="Print"
        )
        db.add(transaction)

        db.commit()
        return True, "Print job recorded", total_charge

    except Exception as e:
        db.rollback()
        return False, str(e), None
    finally:
        db.close()


def get_inventory_items():
    db = SessionLocal()
    try:
        return db.query(Inventory).order_by(Inventory.ItemName).all()
    finally:
        db.close()


def record_pos_sale(session_id: int, item_id: int, quantity: int, payment_method: str = "Cash"):
    if quantity <= 0:
        return False, "Quantity must be positive", None

    db = SessionLocal()
    try:
        session = db.query(Session).filter_by(SessionID=session_id).first()
        if not session:
            return False, "Session not found", None

        item = db.query(Inventory).filter_by(ItemID=item_id).first()
        if not item:
            return False, "Item not found", None

        if item.StockQuantity < quantity:
            return False, f"Insufficient stock (only {item.StockQuantity} left)", None

        total_charge = round(item.SalePrice * quantity, 2)
        item.StockQuantity -= quantity

        transaction = Transaction(
            SessionID=session_id,
            AmountPaid=total_charge,
            PaymentMethod=payment_method,
            Timestamp=utc_now(),
            Category="POS"
        )
        db.add(transaction)

        db.commit()
        return True, f"Sold {quantity}x {item.ItemName}", total_charge

    except Exception as e:
        db.rollback()
        return False, str(e), None
    finally:
        db.close()


def get_session_extra_charges(session_id: int) -> float:
    db = SessionLocal()
    try:
        transactions = db.query(Transaction).filter_by(SessionID=session_id).all()
        return round(sum(t.AmountPaid for t in transactions), 2)
    finally:
        db.close()