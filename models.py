import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Customer(Base):
    __tablename__ = "customers"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, index=True)
    phone = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    orders = relationship("EternaOrder", back_populates="customer")


class Recipient(Base):
    __tablename__ = "recipients"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    consent_confirmed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    orders = relationship("EternaOrder", back_populates="recipient")


class EternaOrder(Base):
    __tablename__ = "eterna_orders"

    id = Column(String, primary_key=True, default=gen_uuid)

    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    recipient_id = Column(String, ForeignKey("recipients.id"), nullable=False)

    phrase_1 = Column(Text, nullable=False)
    phrase_2 = Column(Text, nullable=False)
    phrase_3 = Column(Text, nullable=False)

    photos_json = Column(Text, nullable=False, default="[]")
    sender_video_path = Column(String, nullable=True)
    final_video_path = Column(String, nullable=True)
    reaction_video_path = Column(String, nullable=True)

    public_slug = Column(String, nullable=False, unique=True, index=True)
    state = Column(String, nullable=False, default="uploaded")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    customer = relationship("Customer", back_populates="orders")
    recipient = relationship("Recipient", back_populates="orders")
