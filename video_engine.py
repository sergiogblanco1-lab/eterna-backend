import os
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

            # Fondo desenfocado cinematográfico
            bg = ImageOps.fit(img.copy(), size, method=Image.Resampling.LANCZOS)
            bg = bg.filter(ImageFilter.GaussianBlur(radius=20))

            # Imagen principal encajada
            fg = ImageOps.contain(img, size, method=Image.Resampling.LANCZOS)

            canvas = bg.copy()
            x = (target_w - fg.width) // 2
            y = (target_h - fg.height) // 2
            canvas.paste(fg, (x, y))

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

        work_dir = Path(output_path).parent
        prepared_images: List[str] = []

        for i, img_path in enumerate(image_paths, start=1):
            prepared = str(work_dir / f"prepared_{i}.jpg")
            self._prepare_image_for_video(img_path, prepared)
            prepared_images.append(prepared)

        total_inputs = []
        for img in prepared_images:
            total_inputs.extend(["-loop", "1", "-t", str(seconds_per_image), "-i", img])

        filter_parts = []
        stream_names = []

        for i in range(len(prepared_images)):
            label = f"v{i}"
            draw = ""

            if i < len(phrases) and phrases[i].strip():
                phrase = self._escape_drawtext(phrases[i].strip())
                draw = (
                    f",drawtext=text='{phrase}':"
                    f"fontcolor=white:fontsize=42:"
                    f"x=(w-text_w)/2:y=h-220:"
                    f"box=1:boxcolor=black@0.35:boxborderw=20"
                )

            filter_parts.append(
                f"[{i}:v]"
                f"scale=720:1280,"
                f"setsar=1,"
                f"format=yuv420p"
                f"{draw}"
                f"[{label}]"
            )
            stream_names.append(f"[{label}]")

        current = "v0"
        offset = seconds_per_image - transition_duration

        if len(prepared_images) == 1:
            final_video_label = "[v0]"
        else:
            last_label = None
            for i in range(1, len(prepared_images)):
                in_a = f"[{current}]" if i == 1 else f"[x{i-1}]"
                in_b = f"[v{i}]"
                out = f"[x{i}]"
                filter_parts.append(
                    f"{in_a}{in_b}xfade=transition=fade:duration={transition_duration}:offset={offset}{out}"
                )
                offset += seconds_per_image - transition_duration
                last_label = out

            final_video_label = last_label

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
            output_path,
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
                f"STDERR:\n{result.stderr}"
            )

        return output_path
