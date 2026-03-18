from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String)


class Recipient(Base):
    __tablename__ = "recipients"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    phone = Column(String)  # 🔥 IMPORTANTE


class EternaOrder(Base):
    __tablename__ = "eterna_orders"

    id = Column(Integer, primary_key=True)
    eterna_id = Column(String)
    customer_id = Column(Integer)
    recipient_id = Column(Integer)

    phrase1 = Column(String)
    phrase2 = Column(String)
    phrase3 = Column(String)

    storage_folder = Column(String)
    share_token = Column(String)
    share_url = Column(String)

    is_paid = Column(Boolean, default=False)  # 🔥 CLAVE
