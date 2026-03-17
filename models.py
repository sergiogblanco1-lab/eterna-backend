from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from database import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=True)
    email = Column(String, unique=True, index=True, nullable=True)
    phone = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=True)

    orders = relationship("EternaOrder", back_populates="customer")


class Recipient(Base):
    __tablename__ = "recipients"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    consent_confirmed = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=True)

    orders = relationship("EternaOrder", back_populates="recipient")


class EternaOrder(Base):
    __tablename__ = "eterna_orders"

    id = Column(String, primary_key=True, index=True)
    customer_id = Column(String, ForeignKey("customers.id"))
    recipient_id = Column(String, ForeignKey("recipients.id"))

    phrase_1 = Column(Text, nullable=True)
    phrase_2 = Column(Text, nullable=True)
    phrase_3 = Column(Text, nullable=True)

    photos_json = Column(Text, nullable=True)
    final_video_path = Column(String, nullable=True)

    public_slug = Column(String, unique=True, index=True, nullable=True)
    state = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=True)

    customer = relationship("Customer", back_populates="orders")
    recipient = relationship("Recipient", back_populates="orders")
