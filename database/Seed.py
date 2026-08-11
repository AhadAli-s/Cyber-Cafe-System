import bcrypt
from database import SessionLocal, init_db
from models import Employee, Computer, PricingPlan, User


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def seed_data():
    init_db()
    db = SessionLocal()

    try:
        # Default Super Admin
        if not db.query(Employee).filter_by(Username="admin").first():
            admin = Employee(
                FullName="System Administrator",
                Role="SuperAdmin",
                Username="admin",
                PasswordHash=hash_password("Admin@123"),
                Status="Active"
            )
            db.add(admin)

        # Sample workstations
        sample_pcs = [
            {"PC_Name": "PC-01", "IPAddress": "192.168.1.101", "MACAddress": "00:1A:2B:3C:4D:01"},
            {"PC_Name": "PC-02", "IPAddress": "192.168.1.102", "MACAddress": "00:1A:2B:3C:4D:02"},
            {"PC_Name": "PC-03", "IPAddress": "192.168.1.103", "MACAddress": "00:1A:2B:3C:4D:03"},
        ]
        for pc in sample_pcs:
            if not db.query(Computer).filter_by(MACAddress=pc["MACAddress"]).first():
                db.add(Computer(**pc, CurrentStatus="Offline"))

        # Base pricing plans
        sample_plans = [
            {"PlanName": "Standard Hourly", "HourlyRate": 100.0, "MinDuration": 15, "IsPackage": False},
            {"PlanName": "Night Owl Package", "HourlyRate": 60.0, "MinDuration": 240, "IsPackage": True},
            {"PlanName": "3-Hour Gaming Bundle", "HourlyRate": 80.0, "MinDuration": 180, "IsPackage": True},
        ]
        for plan in sample_plans:
            if not db.query(PricingPlan).filter_by(PlanName=plan["PlanName"]).first():
                db.add(PricingPlan(**plan))

        # Sample walk-in member
        if not db.query(User).filter_by(Username="guest_member").first():
            member = User(
                Username="guest_member",
                PasswordHash=hash_password("Member@123"),
                PrepaidBalance=500.0,
                MemberTier="Standard"
            )
            db.add(member)

        db.commit()
        print("Seed data inserted successfully.")

    except Exception as e:
        db.rollback()
        print(f"Seeding failed: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()