from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import settings

router = APIRouter(tags=["video"])


@router.get("/video/{order_uuid}")
def stream_video(order_uuid: str):
    video_path = Path(settings.exports_dir) / f"{order_uuid}.mp4"
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Vídeo no encontrado")
    return FileResponse(video_path, media_type="video/mp4", filename=f"{order_uuid}.mp4")
