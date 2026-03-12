from pathlib import Path
import shutil

from app.config import settings


for folder in [settings.storage_root, settings.uploads_dir, settings.exports_dir, settings.reaction_dir]:
    Path(folder).mkdir(parents=True, exist_ok=True)


def export_path(order_uuid: str) -> str:
    return str(Path(settings.exports_dir) / f"{order_uuid}.mp4")


def local_public_video_url(order_uuid: str) -> str:
    return f"{settings.public_base_url.rstrip('/')}/video/{order_uuid}"


def save_placeholder_video(src_path: str, order_uuid: str) -> str:
    dst = export_path(order_uuid)
    shutil.copyfile(src_path, dst)
    return dst
