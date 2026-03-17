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
        music_path: Optional[str] = None,
        image_duration: int = 5,
        transition_duration: int = 1,
        width: int = 720,
        height: int = 1280,
        fps: int = 30,
    ):
        if not imagenes:
            raise Exception("No hay imágenes")

        salida_path = Path(salida)
        salida_path.parent.mkdir(parents=True, exist_ok=True)

        clips_generados = []

        for i, img in enumerate(imagenes):
            clip_path = salida_path.parent / f"clip_{i}.mp4"

            cmd_clip = [
                self.ffmpeg_bin,
                "-y",
                "-loop", "1",
                "-t", str(image_duration),
                "-i", str(Path(img).resolve()),
                "-vf",
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
                f"format=yuv420p",
                "-r", str(fps),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                str(clip_path),
            ]

            proc = subprocess.run(cmd_clip, capture_output=True, text=True)

            print("🎬 CLIP CMD:", " ".join(cmd_clip))
            print("🎬 CLIP STDOUT:", proc.stdout)
            print("🎬 CLIP STDERR:", proc.stderr)

            if proc.returncode != 0:
                raise Exception(proc.stderr)

            clips_generados.append(clip_path)

        concat_file = salida_path.parent / "concat.txt"
        with open(concat_file, "w", encoding="utf-8") as f:
            for clip in clips_generados:
                f.write(f"file '{clip.resolve()}'\n")

        cmd_concat = [
            self.ffmpeg_bin,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            str(salida_path),
        ]

        proc = subprocess.run(cmd_concat, capture_output=True, text=True)

        print("🎬 CONCAT CMD:", " ".join(cmd_concat))
        print("🎬 CONCAT STDOUT:", proc.stdout)
        print("🎬 CONCAT STDERR:", proc.stderr)

        if proc.returncode != 0:
            raise Exception(proc.stderr)

        if not salida_path.exists():
            raise Exception("El vídeo no se creó")

        return str(salida_path)
