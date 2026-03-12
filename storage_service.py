from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import EternaOrder
from app.schemas import OrderCreate, OrderCreatedResponse, OrderStatusResponse
from app.services.emotional_order import create_order
from app.workers.render_worker import process_render_job

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderCreatedResponse, status_code=status.HTTP_202_ACCEPTED)
def create_eterna_order(payload: OrderCreate, db: Session = Depends(get_db)):
    order = create_order(db, payload)
    process_render_job(db, order)
    return OrderCreatedResponse(
        order_uuid=order.order_uuid,
        status=order.status,
        poll_url=f"/orders/{order.order_uuid}",
        checkout_url=None,
    )


@router.get("/{order_uuid}", response_model=OrderStatusResponse)
def get_order_status(order_uuid: str, db: Session = Depends(get_db)):
    order = db.query(EternaOrder).filter(EternaOrder.order_uuid == order_uuid).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    return OrderStatusResponse(
        order_uuid=order.order_uuid,
        status=order.status,
        video_url=order.video_url,
        render_error=order.render_error,
        updated_at=order.updated_at,
    )
