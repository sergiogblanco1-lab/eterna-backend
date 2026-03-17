import subprocess
import shutil
from pathlib import Path
from typing import List, Optional


class VideoEngine:

    def __init__(self, ffmpeg_bin: str = "ffmpeg"):
        self.ffmpeg_bin = ffmpeg_bin
        if shutil.which(self.ffmpeg_bin) is None:
            raise Exception("FFmpeg no está instalado")

    def generar_video(
        self,
        imagenes: List[str],
        salida: str,
        frases: Optional[List[str]] = None,
        image_duration: int = 5,
        width: int = 720,
        height: int = 1280,
        fps: int = 30,
    ):
        if not imagenes:
            raise Exception("No hay imágenes")

        salida_path = Path(salida)
        salida_path.parent.mkdir(parents=True, exist_ok=True)

        clips = []

        for i, img in enumerate(imagenes):
            clip_path = salida_path.parent / f"clip_{i}.mp4"

            cmd = [
                self.ffmpeg_bin,
                "-y",
                "-loop", "1",
                "-i", img,
                "-t", str(image_duration),
                "-vf", f"scale={width}:{height},format=yuv420p",
                "-r", str(fps),
                "-pix_fmt", "yuv420p",
                str(clip_path)
            ]

            subprocess.run(cmd, check=True)
            clips.append(str(clip_path))

        # Crear lista para concatenar
        list_file = salida_path.parent / "list.txt"
        with open(list_file, "w") as f:
            for clip in clips:
                f.write(f"file '{clip}'\n")

        # Concatenar clips
        cmd_concat = [
            self.ffmpeg_bin,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            str(salida_path)
        ]

        subprocess.run(cmd_concat, check=True)

        return str(salida_path)
