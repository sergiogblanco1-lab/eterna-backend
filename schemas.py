from datetime import datetime
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str


class CreateEternaResponse(BaseModel):
    ok: bool
    order_id: str
    public_url: str
    state: str


class AdminOrderItem(BaseModel):
    id: str
    state: str
    customer_name: str
    customer_email: str
    customer_phone: str
    recipient_name: str
    recipient_phone: str
    created_at: datetime
    final_video_path: str | None = None
