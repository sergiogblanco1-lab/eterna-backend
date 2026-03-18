from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from database import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    orders = relationship("EternaOrder", back_populates="customer")


class Recipient(Base):
    __tablename__ = "recipients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    orders = relationship("EternaOrder", back_populates="recipient")


class EternaOrder(Base):
    __tablename__ = "eterna_orders"

    id = Column(Integer, primary_key=True, index=True)
    eterna_id = Column(String(100), unique=True, nullable=False, index=True)

    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    recipient_id = Column(Integer, ForeignKey("recipients.id"), nullable=True)

    phrase1 = Column(Text, nullable=False)
    phrase2 = Column(Text, nullable=False)
    phrase3 = Column(Text, nullable=False)

    image_count = Column(Integer, default=0)

    storage_folder = Column(String(500), nullable=False)
    video_path = Column(String(500), nullable=True)
    status = Column(String(50), default="created")

    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="orders")
    recipient = relationship("Recipient", back_populates="orders")
