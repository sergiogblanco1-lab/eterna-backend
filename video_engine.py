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

        duracion_foto = 5.5
        transicion = 1.0
        fps = 30

        inputs = []
        filter_parts = []

        for i, photo_path in enumerate(photos):
            photo_path = os.path.abspath(photo_path)
            inputs.extend([
                "-loop", "1",
                "-t", str(duracion_foto),
                "-i", photo_path
            ])

            filter_parts.append(
                f"[{i}:v]"
                f"scale=900:1600:force_original_aspect_ratio=increase,"
                f"crop=720:1280,"
                f"zoompan="
                f"z='min(zoom+0.0008,1.08)':"
                f"x='iw/2-(iw/zoom/2)':"
                f"y='ih/2-(ih/zoom/2)':"
                f"d={int(duracion_foto * fps)}:s=720x1280:fps={fps},"
                f"setpts=PTS-STARTPTS,"
                f"format=yuv420p"
                f"[v{i}]"
            )

        # Encadenar transiciones xfade entre vídeos
        current = "v0"
        offset = duracion_foto - transicion

        for i in range(1, len(photos)):
            next_v = f"v{i}"
            out = f"x{i}"
            filter_parts.append(
                f"[{current}][{next_v}]"
                f"xfade=transition=fade:duration={transicion}:offset={offset}"
                f"[{out}]"
            )
            current = out
            offset += duracion_foto - transicion

        filter_complex = ";".join(filter_parts)

        command = [
            self.ffmpeg_bin,
            "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", f"[{current}]",
            "-r", str(fps),
            "-pix_fmt", "yuv420p",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            output_path
        ]

        self._run(command)

        if not os.path.exists(output_path):
            raise Exception("El vídeo no se generó correctamente")

        return output_path
