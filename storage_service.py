import json
import os
import shutil
from typing import List, Optional

from fastapi import UploadFile, HTTPException

from config import settings


ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm"}


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def get_extension(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


class StorageService:
    def __init__(self):
        ensure_dir(settings.uploads_dir)
        ensure_dir(settings.exports_dir)
        ensure_dir(settings.reactions_dir)

    def order_root(self, order_id: str) -> str:
        return os.path.join(settings.uploads_dir, order_id)

    def order_photos_dir(self, order_id: str) -> str:
        return os.path.join(self.order_root(order_id), "photos")

    def order_sender_video_path(self, order_id: str, ext: str) -> str:
        return os.path.join(self.order_root(order_id), f"sender_message{ext}")

    def order_final_video_path(self, order_id: str) -> str:
        return os.path.join(settings.exports_dir, f"{order_id}.mp4")

    def order_reaction_video_path(self, order_id: str, ext: str) -> str:
        return os.path.join(settings.reactions_dir, f"{order_id}{ext}")

    def create_order_dirs(self, order_id: str) -> None:
        ensure_dir(self.order_root(order_id))
        ensure_dir(self.order_photos_dir(order_id))

    def save_photos(self, order_id: str, photos: List[UploadFile]) -> List[str]:
        self.create_order_dirs(order_id)
        saved = []

        for index, photo in enumerate(photos, start=1):
            if not photo.filename:
                raise HTTPException(status_code=400, detail="Una foto no tiene nombre válido.")

            ext = get_extension(photo.filename)
            if ext not in ALLOWED_IMAGE_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Formato de imagen no permitido: {ext}"
                )

            filename = f"photo_{index}{ext}"
            path = os.path.join(self.order_photos_dir(order_id), filename)

            with open(path, "wb") as buffer:
                shutil.copyfileobj(photo.file, buffer)

            saved.append(filename)

        return saved

    def save_sender_video(self, order_id: str, video: Optional[UploadFile]) -> Optional[str]:
        if not video or not video.filename:
            return None

        self.create_order_dirs(order_id)
        ext = get_extension(video.filename)

        if ext not in ALLOWED_VIDEO_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Formato de vídeo no permitido: {ext}"
            )

        path = self.order_sender_video_path(order_id, ext)

        with open(path, "wb") as buffer:
            shutil.copyfileobj(video.file, buffer)

        return path

    def photos_json(self, saved_photos: List[str]) -> str:
        return json.dumps(saved_photos, ensure_ascii=False)

    def photos_from_json(self, photos_json: str) -> List[str]:
        return json.loads(photos_json)
