from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.sql import func

from database import Base


class EternaOrder(Base):
    __tablename__ = "eterna_orders"

    id = Column(String, primary_key=True, index=True)
    paid = Column(Boolean, default=False, nullable=False)

    customer_name = Column(String, nullable=False)
    customer_email = Column(String, nullable=False)

    recipient_name = Column(String, nullable=False)
    recipient_phone = Column(String, nullable=False)

    phrase_1 = Column(Text, nullable=True)
    phrase_2 = Column(Text, nullable=True)
    phrase_3 = Column(Text, nullable=True)

    stripe_session_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
