import subprocess
import shutil
from pathlib import Path
from typing import List

from PIL import Image, ImageOps


class VideoEngine:

    def generate_video(
        self,
        image_paths: List[str],
        phrases: List[str],
        output_path: str,
        seconds_per_image: int = 5
    ) -> str:

        if not image_paths:
            raise ValueError("No hay imágenes")

        if shutil.which("ffmpeg") is None:
            raise RuntimeError("FFmpeg no está instalado")

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        temp_dir = output_file.parent / "frames"
        temp_dir.mkdir(exist_ok=True)

        prepared_images = []

        # =====================
        # PREPARAR IMÁGENES
        # =====================
        for i, img_path in enumerate(image_paths):

            out_path = temp_dir / f"img_{i}.jpg"

            with Image.open(img_path) as img:
                img = img.convert("L")  # blanco y negro
                img = ImageOps.fit(img, (720, 1280))
                img.save(out_path, "JPEG", quality=95)

            prepared_images.append(str(out_path))

        # =====================
        # CREAR INPUTS
        # =====================
        inputs = []
        for img in prepared_images:
            inputs += ["-loop", "1", "-t", str(seconds_per_image), "-i", img]

        # =====================
        # TEXTO
        # =====================
        filters = []

        for i in range(len(prepared_images)):

            text = ""
            if i < len(phrases) and phrases[i]:
                safe = phrases[i].replace(":", "").replace("'", "")
                text = (
                    f",drawtext=text='{safe}':"
                    f"fontcolor=white:fontsize=40:"
                    f"x=(w-text_w)/2:y=h-200"
                )

            filters.append(
                f"[{i}:v]scale=720:1280,format=yuv420p{text}[v{i}]"
            )

        # =====================
        # TRANSICIONES
        # =====================
        if len(prepared_images) == 1:
            final = "[v0]"
        else:
            offset = seconds_per_image - 1

            for i in range(1, len(prepared_images)):
                a = "[v0]" if i == 1 else f"[x{i-1}]"
                b = f"[v{i}]"
                out = f"[x{i}]"

                filters.append(
                    f"{a}{b}xfade=transition=fade:duration=1:offset={offset}{out}"
                )

                offset += seconds_per_image - 1

            final = f"[x{len(prepared_images)-1}]"

        filter_complex = ";".join(filters)

        # =====================
        # COMANDO FFMPEG
        # =====================
        cmd = [
            "ffmpeg",
            "-y",
            *inputs,
            "-filter_complex",
            filter_complex,
            "-map",
            final,
            "-pix_fmt",
            "yuv420p",
            str(output_file),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(result.stderr)

        if not output_file.exists():
            raise RuntimeError("No se creó el vídeo")

        return str(output_file)
