from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str


class EternaCreateResponse(BaseModel):
    ok: bool
    eterna_id: str
    message: str
    video_url: str | None = None
