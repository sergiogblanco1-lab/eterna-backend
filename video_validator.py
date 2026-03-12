"""Motor simple de vídeo ETERNA.

Este scaffold genera un vídeo placeholder usando ffmpeg con fondo negro y texto.
Sustituye `build_ffmpeg_command` por tu pipeline cinematográfico V7 cuando lo tengas final.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from app.config import settings
from app.services.storage_service import export_path


PLACEHOLDER_FILTER = (
    "color=c=black:s=1080x1920:d=12,"
    "drawtext=text='ETERNA':fontcolor=white:fontsize=72:x=(w-text_w)/2:y=320,"
    "drawtext=text='Tu recuerdo está en camino':fontcolor=white:fontsize=42:x=(w-text_w)/2:y=460"
)


def build_ffmpeg_command(output_path: str) -> list[str]:
    return [
        settings.ffmpeg_path,
        "-y",
        "-f",
        "lavfi",
        "-i",
        PLACEHOLDER_FILTER,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        output_path,
    ]


def render_order_video(order_uuid: str) -> str:
    Path(settings.exports_dir).mkdir(parents=True, exist_ok=True)
    output_path = export_path(order_uuid)
    cmd = build_ffmpeg_command(output_path)
    subprocess.run(cmd, check=True)
    return output_path
