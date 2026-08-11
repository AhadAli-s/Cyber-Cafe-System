from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, Float, DateTime,
    ForeignKey, Text
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    UserID = Column(Integer, primary_key=True, autoincrement=True)
    Username = Column(String(50), unique=True, nullable=False)
    PasswordHash = Column(String(255), nullable=False)
    PrepaidBalance = Column(Float, default=0.0)
    MemberTier = Column(String(20), default="Standard")
    CreatedAt = Column(DateTime, default=datetime.utcnow)

    sessions = relationship("Session", back_populates="user")


class Employee(Base):
    __tablename__ = "employees"

    EmployeeID = Column(Integer, primary_key=True, autoincrement=True)
    FullName = Column(String(100), nullable=False)
    Role = Column(String(20), nullable=False)  # SuperAdmin, Manager, Cashier
    Username = Column(String(50), unique=True, nullable=False)
    PasswordHash = Column(String(255), nullable=False)
    Status = Column(String(20), default="Active")

    audit_logs = relationship("AuditLog", back_populates="employee")


class Computer(Base):
    __tablename__ = "computers"

    ComputerID = Column(Integer, primary_key=True, autoincrement=True)
    PC_Name = Column(String(50), nullable=False)
    IPAddress = Column(String(45), nullable=False)
    MACAddress = Column(String(17), unique=True, nullable=False)
    CurrentStatus = Column(String(20), default="Offline")
    # Available, Occupied, Locked, Offline, Maintenance

    sessions = relationship("Session", back_populates="computer")


class PricingPlan(Base):
    __tablename__ = "pricing_plans"

    PlanID = Column(Integer, primary_key=True, autoincrement=True)
    PlanName = Column(String(100), nullable=False)
    HourlyRate = Column(Float, nullable=False)
    MinDuration = Column(Integer, default=0)  # minutes
    IsPackage = Column(Boolean, default=False)

    sessions = relationship("Session", back_populates="pricing_plan")


class Session(Base):
    __tablename__ = "sessions"

    SessionID = Column(Integer, primary_key=True, autoincrement=True)
    ComputerID = Column(Integer, ForeignKey("computers.ComputerID"), nullable=False)
    UserID = Column(Integer, ForeignKey("users.UserID"), nullable=True)  # nullable for guest sessions
    PlanID = Column(Integer, ForeignKey("pricing_plans.PlanID"), nullable=True)
    StartTime = Column(DateTime, default=datetime.utcnow)
    EndTime = Column(DateTime, nullable=True)
    SessionType = Column(String(10), default="Postpaid")  # Prepaid, Postpaid
    TotalCost = Column(Float, default=0.0)

    computer = relationship("Computer", back_populates="sessions")
    user = relationship("User", back_populates="sessions")
    pricing_plan = relationship("PricingPlan", back_populates="sessions")
    transactions = relationship("Transaction", back_populates="session")
    print_logs = relationship("PrintLog", back_populates="session")


class Transaction(Base):
    __tablename__ = "transactions"

    TransactionID = Column(Integer, primary_key=True, autoincrement=True)
    SessionID = Column(Integer, ForeignKey("sessions.SessionID"), nullable=False)
    AmountPaid = Column(Float, nullable=False)
    PaymentMethod = Column(String(20), default="Cash")
    Timestamp = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="transactions")


class Inventory(Base):
    __tablename__ = "inventory"

    ItemID = Column(Integer, primary_key=True, autoincrement=True)
    ItemName = Column(String(100), nullable=False)
    UnitCost = Column(Float, nullable=False)
    SalePrice = Column(Float, nullable=False)
    StockQuantity = Column(Integer, default=0)


class PrintLog(Base):
    __tablename__ = "print_logs"

    PrintID = Column(Integer, primary_key=True, autoincrement=True)
    SessionID = Column(Integer, ForeignKey("sessions.SessionID"), nullable=False)
    PagesCount = Column(Integer, nullable=False)
    IsColor = Column(Boolean, default=False)
    PaperSize = Column(String(5), default="A4")
    TotalCharge = Column(Float, nullable=False)

    session = relationship("Session", back_populates="print_logs")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    LogID = Column(Integer, primary_key=True, autoincrement=True)
    EmployeeID = Column(Integer, ForeignKey("employees.EmployeeID"), nullable=False)
    ActionDescription = Column(Text, nullable=False)
    Timestamp = Column(DateTime, default=datetime.utcnow)
    IPAddress = Column(String(45), nullable=True)

    employee = relationship("Employee", back_populates="audit_logs")
