from pathlib import Path
from typing import List

from fastapi import UploadFile


class StorageService:
    def __init__(self, base_dir: str = "storage"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.media_dir = self.base_dir / "media"
        self.media_dir.mkdir(parents=True, exist_ok=True)

    def create_eterna_folder(self, eterna_id: str) -> Path:
        folder_path = self.media_dir / eterna_id
        folder_path.mkdir(parents=True, exist_ok=True)
        return folder_path

    async def save_uploaded_images(self, folder_path: Path, photos: List[UploadFile]) -> List[str]:
        saved_paths: List[str] = []

        for index, photo in enumerate(photos, start=1):
            extension = Path(photo.filename or "").suffix.lower()
            if extension not in [".jpg", ".jpeg", ".png", ".webp"]:
                extension = ".jpg"

            file_path = folder_path / f"foto_{index}{extension}"

            content = await photo.read()
            if not content:
                raise ValueError(f"La foto {index} está vacía.")

            with open(file_path, "wb") as f:
                f.write(content)

            saved_paths.append(str(file_path))

        return saved_paths

    async def save_uploaded_video(self, folder_path: Path, video_file: UploadFile, filename_prefix: str) -> str:
        extension = Path(video_file.filename or "").suffix.lower()
        if extension not in [".mp4", ".mov", ".webm", ".m4v"]:
            extension = ".mp4"

        file_path = folder_path / f"{filename_prefix}{extension}"

        content = await video_file.read()
        if not content:
            raise ValueError(f"El archivo '{filename_prefix}' está vacío.")

        with open(file_path, "wb") as f:
            f.write(content)

        return str(file_path)
