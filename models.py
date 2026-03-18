from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.orm import relationship

from database import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(100), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    orders = relationship("EternaOrder", back_populates="customer")


class Recipient(Base):
    __tablename__ = "recipients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    phone = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    orders = relationship("EternaOrder", back_populates="recipient")


class EternaOrder(Base):
    __tablename__ = "eterna_orders"

    id = Column(Integer, primary_key=True, index=True)
    eterna_id = Column(String(100), unique=True, nullable=False, index=True)

    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    recipient_id = Column(Integer, ForeignKey("recipients.id"), nullable=False)

    phrase1 = Column(String(500), nullable=False)
    phrase2 = Column(String(500), nullable=False)
    phrase3 = Column(String(500), nullable=False)

    image_count = Column(Integer, nullable=False, default=0)
    storage_folder = Column(String(500), nullable=False)

    share_token = Column(String(120), unique=True, nullable=False, index=True)
    share_url = Column(String(500), nullable=False)

    status = Column(String(50), nullable=False, default="created")
    # created, opened, reaction_uploaded

    includes_reaction = Column(Boolean, default=True)
    reaction_permission_public = Column(Boolean, default=False)
    reaction_video_path = Column(String(500), nullable=True)

    gift_active = Column(Boolean, default=False)
    gift_amount_eur = Column(Float, default=0.0)
    gift_message = Column(String(500), nullable=True)

    giver_video_path = Column(String(500), nullable=True)
    final_video_path = Column(String(500), nullable=True)  # reservado para futuro

    created_at = Column(DateTime, default=datetime.utcnow)
    opened_at = Column(DateTime, nullable=True)
    reaction_uploaded_at = Column(DateTime, nullable=True)

    customer = relationship("Customer", back_populates="orders")
    recipient = relationship("Recipient", back_populates="orders")
