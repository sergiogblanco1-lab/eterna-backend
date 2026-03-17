import subprocess
import shutil
from typing import List, Optional
from pathlib import Path


class VideoEngine:
    def __init__(self, ffmpeg_bin: str = "ffmpeg"):
        self.ffmpeg_bin = ffmpeg_bin

        if shutil.which(self.ffmpeg_bin) is None:
            raise Exception("FFmpeg no está instalado en el sistema")

    def generar_video(
        self,
        imagenes: List[str],
        salida: str,
        frases: Optional[List[str]] = None,
        music_path: Optional[str] = None,
        image_duration: int = 5,
        transition_duration: int = 1,
        width: int = 720,
        height: int = 1280,
        fps: int = 30,
    ):
        if not imagenes:
            raise ValueError("No hay imágenes para generar el vídeo")

        salida_path = Path(salida)
        salida_path.parent.mkdir(parents=True, exist_ok=True)

        lista_path = salida_path.parent / "inputs.txt"

        with open(lista_path, "w", encoding="utf-8") as f:
            for img in imagenes:
                f.write(f"file '{Path(img).resolve()}'\n")
                f.write(f"duration {image_duration}\n")
            f.write(f"file '{Path(imagenes[-1]).resolve()}'\n")

        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(lista_path),
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                   f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
                   f"format=yuv420p",
            "-r", str(fps),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(salida_path)
        ]

        print("🎬 COMANDO FFMPEG:")
        print(" ".join(cmd))

        proc = subprocess.run(cmd, capture_output=True, text=True)

        print("🎬 STDOUT:", proc.stdout)
        print("❌ STDERR:", proc.stderr)

        if proc.returncode != 0:
            raise Exception(proc.stderr)

        if not salida_path.exists():
            raise Exception("El vídeo no se creó")

        return str(salida_path)
