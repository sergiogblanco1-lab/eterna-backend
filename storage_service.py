import os
import shutil
from pathlib import Path
from typing import List

from fastapi import UploadFile


class StorageService:
    def __init__(self, base_folder: str = "storage"):
        self.base_folder = Path(base_folder)
        self.base_folder.mkdir(parents=True, exist_ok=True)

    def create_eterna_folder(self, eterna_id: str) -> Path:
        folder = self.base_folder / eterna_id
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    async def save_uploaded_images(
        self,
        eterna_folder: Path,
        files: List[UploadFile]
    ) -> List[str]:
        saved_paths: List[str] = []

        for index, file in enumerate(files, start=1):
            extension = Path(file.filename).suffix.lower() or ".jpg"
            safe_name = f"foto_{index}{extension}"
            dest = eterna_folder / safe_name

            with open(dest, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            saved_paths.append(str(dest))

        return saved_paths

    def save_phrases(self, eterna_folder: Path, phrases: List[str]) -> str:
        phrases_path = eterna_folder / "frases.txt"
        with open(phrases_path, "w", encoding="utf-8") as f:
            for phrase in phrases:
                f.write(phrase.strip() + "\n")
        return str(phrases_path)

    def get_video_output_path(self, eterna_folder: Path) -> str:
        return str(eterna_folder / "video.mp4")

    def get_public_video_url(self, eterna_id: str) -> str:
        return f"/media/{eterna_id}/video.mp4"
