import json
import uuid

from sqlalchemy.orm import Session

from app.models import EternaOrder, OrderStatus
from app.schemas import OrderCreate
from app.utils.image_validator import validate_links


def create_order(db: Session, payload: OrderCreate) -> EternaOrder:
    order = EternaOrder(
        order_uuid=str(uuid.uuid4()),
        customer_name=payload.customer_name,
        customer_email=payload.customer_email,
        recipient_name=payload.recipient_name,
        phrases_text=json.dumps(payload.phrases, ensure_ascii=False),
        photos_text=json.dumps(validate_links(payload.photo_links), ensure_ascii=False),
        surprise_message=payload.surprise_message,
        is_sender_reaction_enabled=payload.is_sender_reaction_enabled,
        status=OrderStatus.paid,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order
