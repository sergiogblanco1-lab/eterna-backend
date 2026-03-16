import os
from pydantic import BaseModel


class Settings(BaseModel):

    uploads_dir: str = "storage/uploads"
    exports_dir: str = "storage/exports"
    reactions_dir: str = "storage/reactions"

    ffmpeg_path: str = "ffmpeg"

    database_url: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///eterna.db"
    )

    public_base_url: str = os.getenv(
        "PUBLIC_BASE_URL",
        "https://eterna-backend-0six.onrender.com"
    )


settings = Settings()
