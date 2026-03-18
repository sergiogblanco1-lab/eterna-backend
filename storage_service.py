from pathlib import Path
from typing import List
from fastapi import UploadFile


class StorageService:

    def __init__(self):
        self.base = Path("storage")
        self.base.mkdir(exist_ok=True)

        self.media_dir = self.base
        

    def create_eterna_folder(self, eterna_id: str):
        folder = self.base / eterna_id
        folder.mkdir(exist_ok=True)
        return folder


    async def save_uploaded_images(self, folder, photos: List[UploadFile]):
        for i, photo in enumerate(photos, start=1):
            content = await photo.read()
            with open(folder / f"foto_{i}.jpg", "wb") as f:
                f.write(content)


    async def save_uploaded_video(self, folder, video: UploadFile, name: str):
        content = await video.read()
        with open(folder / f"{name}.webm", "wb") as f:
            f.write(content)
