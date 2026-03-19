import shutil
import subprocess
from pathlib import Path
from typing import List

from PIL import Image, ImageOps, ImageFilter


class VideoEngine:
    def __init__(self, temp_dir: str = "temp_frames"):
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def _prepare_image_for_video(
        self,
        input_path: str,
        output_path: str,
        size: tuple[int, int] = (720, 1280)
    ) -> None:
        target_w, target_h = size

        with Image.open(input_path) as img:
            img = img.convert("RGB")

            bg = ImageOps.fit(img.copy(), size, method=Image.Resampling.LANCZOS)
            bg = bg.filter(ImageFilter.GaussianBlur(radius=20))

            fg = ImageOps.contain(img, size, method=Image.Resampling.LANCZOS)

            canvas = bg.copy()
            x = (target_w - fg.width) // 2
            y = (target_h - fg.height) // 2
            canvas.paste(fg, (x, y))

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            canvas.save(output_path, format="JPEG", quality=95)

    def _escape_drawtext(self, text: str) -> str:
        return (
            text.replace("\\", "\\\\")
            .replace(":", "\\:")
            .replace("'", "\\'")
            .replace(",", "\\,")
            .replace("[", "\\[")
            .replace("]", "\\]")
            .replace("%", "\\%")
            .replace('"', '\\"')
            .replace("\n", " ")
        )

    def generate_video(
        self,
        image_paths: List[str],
        phrases: List[str],
        output_path: str,
        fps: int = 30,
        seconds_per_image: float = 5.5,
        transition_duration: float = 1.0
    ) -> str:
        if not image_paths:
            raise ValueError("No hay imágenes para generar el vídeo.")

        if shutil.which("ffmpeg") is None:
            raise RuntimeError("FFmpeg no está instalado o no está disponible en el sistema.")

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        work_dir = output_file.parent
        prepared_images: List[str] = []

        for i, img_path in enumerate(image_paths, start=1):
            prepared = str(work_dir / f"prepared_{i}.jpg")
            self._prepare_image_for_video(img_path, prepared)
            prepared_images.append(prepared)

        total_inputs = []
        for img in prepared_images:
            total_inputs.extend(["-loop", "1", "-t", str(seconds_per_image), "-i", img])

        filter_parts = []

        for i in range(len(prepared_images)):
            label = f"v{i}"
            draw = ""

            if i < len(phrases) and phrases[i].strip():
                phrase = self._escape_drawtext(phrases[i].strip())
                draw = (
                    f",drawtext=text='{phrase}':"
                    f"fontcolor=white:"
                    f"fontsize=42:"
                    f"x=(w-text_w)/2:"
                    f"y=h-220:"
                    f"box=1:"
                    f"boxcolor=black@0.35:"
                    f"boxborderw=20"
                )

            filter_parts.append(
                f"[{i}:v]"
                f"scale=720:1280,"
                f"setsar=1,"
                f"format=yuv420p"
                f"{draw}"
                f"[{label}]"
            )

        if len(prepared_images) == 1:
            final_video_label = "[v0]"
        else:
            offset = seconds_per_image - transition_duration

            for i in range(1, len(prepared_images)):
                in_a = "[v0]" if i == 1 else f"[x{i-1}]"
                in_b = f"[v{i}]"
                out = f"[x{i}]"

                filter_parts.append(
                    f"{in_a}{in_b}"
                    f"xfade=transition=fade:"
                    f"duration={transition_duration}:"
                    f"offset={offset}"
                    f"{out}"
                )

                offset += seconds_per_image - transition_duration

            final_video_label = f"[x{len(prepared_images) - 1}]"

        filter_complex = ";".join(filter_parts)

        cmd = [
            "ffmpeg",
            "-y",
            *total_inputs,
            "-filter_complex",
            filter_complex,
            "-map",
            final_video_label,
            "-r",
            str(fps),
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output_file),
        ]

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:
            raise RuntimeError(
                "FFmpeg falló al generar el vídeo.\n\n"
                f"COMANDO:\n{' '.join(cmd)}\n\n"
                f"STDERR:\n{result.stderr}"
            )

        if not output_file.exists():
            raise RuntimeError("FFmpeg terminó sin error, pero no se creó el archivo de vídeo.")

        if output_file.stat().st_size == 0:
            raise RuntimeError("El vídeo se creó, pero está vacío.")

        return str(output_file)
