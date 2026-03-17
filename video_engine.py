import os
import shutil
import subprocess
from typing import List


class VideoEngine:
    def __init__(self, ffmpeg_bin: str = "ffmpeg"):
        self.ffmpeg_bin = ffmpeg_bin

    def _check_ffmpeg(self) -> None:
        if shutil.which(self.ffmpeg_bin) is None:
            raise Exception("FFmpeg no está instalado o no está disponible en el sistema")

    def _run(self, command: List[str]) -> None:
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(result.stderr.strip() or "Error ejecutando FFmpeg")

    def generate_video(self, order_id: str, photos: list[str], phrases: list[str], output_path: str) -> str:
        self._check_ffmpeg()

        if not photos:
            raise Exception("No hay fotos para generar el vídeo")

        output_path = os.path.abspath(output_path)
        output_dir = os.path.dirname(output_path)
        os.makedirs(output_dir, exist_ok=True)

        clips_dir = os.path.join(output_dir, "clips")
        os.makedirs(clips_dir, exist_ok=True)

        clip_paths = []

        # 1. Crear un clip por cada foto
        for index, photo_path in enumerate(photos, start=1):
            photo_path = os.path.abspath(photo_path)
            clip_path = os.path.abspath(os.path.join(clips_dir, f"clip_{index}.mp4"))

            command = [
                self.ffmpeg_bin,
                "-y",
                "-loop", "1",
                "-i", photo_path,
                "-t", "3",
                "-vf",
                (
                    "scale=720:1280:force_original_aspect_ratio=decrease,"
                    "pad=720:1280:(ow-iw)/2:(oh-ih)/2:black,"
                    "format=yuv420p"
                ),
                "-r", "30",
                "-pix_fmt", "yuv420p",
                "-c:v", "libx264",
                clip_path
            ]

            self._run(command)

            if not os.path.exists(clip_path):
                raise Exception(f"No se pudo crear el clip {index}")

            clip_paths.append(clip_path)

        # 2. Crear concat.txt con rutas absolutas
        concat_file = os.path.abspath(os.path.join(clips_dir, "concat.txt"))
        with open(concat_file, "w", encoding="utf-8") as f:
            for clip_path in clip_paths:
                safe_path = clip_path.replace("\\", "/").replace("'", "'\\''")
                f.write(f"file '{safe_path}'\n")

        if not os.path.exists(concat_file):
            raise Exception("No se pudo crear concat.txt")

        # 3. Unir clips
        command_concat = [
            self.ffmpeg_bin,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            output_path
        ]

        self._run(command_concat)

        if not os.path.exists(output_path):
            raise Exception("El vídeo no se generó correctamente")

        return output_path
