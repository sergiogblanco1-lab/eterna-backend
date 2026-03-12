from sqlalchemy.orm import Session

from app.models import EternaOrder, OrderStatus
from app.services.storage_service import local_public_video_url
from app.services.video_engine import render_order_video


def process_render_job(db: Session, order: EternaOrder) -> EternaOrder:
    order.status = OrderStatus.rendering
    db.commit()
    db.refresh(order)

    try:
        render_order_video(order.order_uuid)
        order.video_url = local_public_video_url(order.order_uuid)
        order.status = OrderStatus.completed
        order.render_error = None
    except Exception as exc:  # noqa: BLE001
        order.status = OrderStatus.failed
        order.render_error = str(exc)

    db.commit()
    db.refresh(order)
    return order
