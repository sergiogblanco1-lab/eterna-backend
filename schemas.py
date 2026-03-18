from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str


class EternaCreationResponse(BaseModel):
    ok: bool
    eterna_id: str
    share_url: str
    message: str


class ReactionUploadResponse(BaseModel):
    ok: bool
    message: str
    reaction_url: str


class ErrorResponse(BaseModel):
    detail: str
