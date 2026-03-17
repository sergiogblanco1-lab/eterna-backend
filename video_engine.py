import subprocess
from pathlib import Path
from typing import List, Optional


class VideoEngine:
    def generar_video(
        self,
        imagenes: List[str],
        salida: str,
        frases: Optional[List[str]] = None,
        image_duration: int = 4,
        width: int = 720,
        height: int = 1280,
        fps: int = 25,
    ) -> str:
        if not imagenes:
            raise Exception("No hay imágenes para generar el vídeo")

        output_path = Path(salida)
        work_dir = output_path.parent
        work_dir.mkdir(parents=True, exist_ok=True)

        clips = []

        for i, imagen in enumerate(imagenes):
            clip_path = work_dir / f"clip_{i}.mp4"

            cmd = [
                "ffmpeg",
                "-y",
                "-loop", "1",
                "-i", imagen,
                "-t", str(image_duration),
                "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
                "-r", str(fps),
                "-pix_fmt", "yuv420p",
                "-c:v", "libx264",
                str(clip_path),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(result.stderr)

            clips.append(clip_path)

        list_file = work_dir / "concat.txt"
        with open(list_file, "w", encoding="utf-8") as f:
            for clip in clips:
                f.write(f"file '{clip.as_posix()}'\n")

        cmd_concat = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            str(output_path),
        ]

        result = subprocess.run(cmd_concat, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(result.stderr)

        return str(output_path)
