from fastapi import APIRouter

router = APIRouter(prefix="/upload", tags=["upload"])


@router.get("/health")
def upload_health():
    return {"status": "ok"}
