from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship

from database import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(100), nullable=True)

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

    # ID público único de la ETERNA
    eterna_id = Column(String(100), unique=True, nullable=False, index=True)

    # Relaciones
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    recipient_id = Column(Integer, ForeignKey("recipients.id"), nullable=False)

    # Contenido principal
    phrase1 = Column(Text, nullable=False)
    phrase2 = Column(Text, nullable=False)
    phrase3 = Column(Text, nullable=False)
    image_count = Column(Integer, default=0)

    # Archivos y rutas
    storage_folder = Column(String(500), nullable=False)
    video_path = Column(String(500), nullable=True)  # futuro vídeo principal
    reaction_video_path = Column(String(500), nullable=True)  # futuro vídeo reacción
    cover_image_path = Column(String(500), nullable=True)  # futura portada/opcional

    # Estado del pedido / experiencia
    status = Column(String(50), default="created", nullable=False)
    # Ejemplos:
    # created
    # paid
    # delivered
    # opened
    # reaction_uploaded
    # completed

    # Compartición / entrega
    share_token = Column(String(120), unique=True, nullable=True, index=True)
    share_url = Column(String(500), nullable=True)
    delivery_method = Column(String(50), nullable=True)
    # Ejemplos:
    # whatsapp
    # email
    # qr
    # manual

    delivered_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)

    # Reacción
    reaction_requested = Column(Boolean, default=False)
    reaction_uploaded_at = Column(DateTime, nullable=True)

    # Pago
    payment_status = Column(String(50), default="pending", nullable=False)
    # Ejemplos:
    # pending
    # paid
    # failed
    # refunded

    payment_method = Column(String(50), nullable=True)
    # Ejemplos:
    # stripe
    # bizum
    # manual

    payment_reference = Column(String(255), nullable=True)
    amount_cents = Column(Integer, nullable=True)
    currency = Column(String(10), default="EUR")

    # Extras por si luego quieres ampliar
    private_note = Column(Text, nullable=True)
    sender_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = relationship("Customer", back_populates="orders")
    recipient = relationship("Recipient", back_populates="orders")
