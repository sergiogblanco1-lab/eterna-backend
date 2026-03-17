import os
import json


class StorageService:
    def __init__(self, base_folder: str = "storage/orders"):
        self.base_folder = base_folder
        os.makedirs(self.base_folder, exist_ok=True)

    def order_dir(self, order_id: str) -> str:
        path = os.path.join(self.base_folder, order_id)
        os.makedirs(path, exist_ok=True)
        return path

    def order_photos_dir(self, order_id: str) -> str:
        path = os.path.join(self.order_dir(order_id), "photos")
        os.makedirs(path, exist_ok=True)
        return path

    def order_video_dir(self, order_id: str) -> str:
        path = os.path.join(self.order_dir(order_id), "video")
        os.makedirs(path, exist_ok=True)
        return path

    def order_final_video_path(self, order_id: str) -> str:
        return os.path.join(self.order_video_dir(order_id), "final.mp4")

    async def save_photos(self, order_id: str, fotos) -> list[str]:
        folder = self.order_photos_dir(order_id)
        saved = []

        for index, foto in enumerate(fotos, start=1):
            extension = os.path.splitext(foto.filename)[1].lower() or ".jpg"
            filename = f"foto_{index}{extension}"
            path = os.path.join(folder, filename)

            contenido = await foto.read()
            if not contenido:
                continue

            with open(path, "wb") as f:
                f.write(contenido)

            saved.append(filename)

        return saved

    def photos_json(self, filenames: list[str]) -> str:
        return json.dumps(filenames, ensure_ascii=False)
