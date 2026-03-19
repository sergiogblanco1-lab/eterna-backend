import shutil
import subprocess
from pathlib import Path
from typing import List

from PIL import Image, ImageOps, ImageFilter, ImageEnhance, ImageDraw, ImageFont


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
            img = ImageOps.exif_transpose(img)

            img = img.convert("L")
            img = ImageEnhance.Contrast(img).enhance(1.18)
            img = img.convert("RGB")

            bg = ImageOps.fit(
                img.copy(),
                size,
                method=Image.Resampling.LANCZOS
            )
            bg = bg.filter(ImageFilter.GaussianBlur(radius=18))

            fg = ImageOps.contain(
                img,
                size,
                method=Image.Resampling.LANCZOS
            )

            canvas = bg.copy()
            x = (target_w - fg.width) // 2
            y = (target_h - fg.height) // 2
            canvas.paste(fg, (x, y))

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            canvas.save(output_path, format="JPEG", quality=95)

    def _create_eterna_frame(self, path: str, text: str = "ETERNA") -> None:
        img = Image.new("RGB", (720, 1280), color="black")
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 70)
        except:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        x = (720 - text_w) // 2
        y = (1280 - text_h) // 2

        draw.text((x, y), text, fill="white", font=font)

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        img.save(path, "JPEG", quality=95)

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
        seconds_per_image: float = 5.0,
        transition_duration: float = 1.0
    ) -> str:
        if not image_paths:
            raise ValueError("No hay imágenes para generar el vídeo.")

        if shutil.which("ffmpeg") is None:
            raise RuntimeError("FFmpeg no está instalado.")

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        work_dir = output_file.parent

        intro_path = str(work_dir / "intro.jpg")
        outro_path = str(work_dir / "outro.jpg")

        self._create_eterna_frame(intro_path)
        self._create_eterna_frame(outro_path)

        prepared_images: List[str] = [intro_path]

        for i, img_path in enumerate(image_paths, start=1):
            prepared = str(work_dir / f"prepared_{i}.jpg")
            self._prepare_image_for_video(img_path, prepared)
            prepared_images.append(prepared)

        prepared_images.append(outro_path)

        total_inputs = []
        for img in prepared_images:
            total_inputs.extend(["-loop", "1", "-t", str(seconds_per_image), "-i", img])

        filter_parts = []

        photo_count = len(image_paths)

        phrase_map = {}
        if photo_count >= 1 and len(phrases) > 0:
            phrase_map[1] = phrases[0]

        if photo_count >= 3 and len(phrases) > 1:
            phrase_map[round(photo_count / 2)] = phrases[1]

        if photo_count >= 2 and len(phrases) > 2:
            phrase_map[photo_count] = phrases[2]

        for i in range(len(prepared_images)):
            label = f"v{i}"
            draw = ""

            if 1 <= i <= photo_count and i in phrase_map:
                phrase = self._escape_drawtext(phrase_map[i])
                fade_out_start = max(seconds_per_image - 0.8, 0.8)

                draw = (
                    f",drawtext=text='{phrase}':"
                    f"fontcolor=white:"
                    f"fontsize=40:"
                    f"x=(w-text_w)/2:"
                    f"y=h-260:"
                    f"box=1:"
                    f"boxcolor=black@0.42:"
                    f"boxborderw=26:"
                    f"alpha='if(lt(t,0.6),t/0.6,if(lt(t,{fade_out_start}),1,({seconds_per_image}-t)/0.8))'"
                )

            filter_parts.append(
                f"[{i}:v]"
                f"scale=720:1280,"
                f"zoompan=z='min(zoom+0.0008,1.08)':"
                f"d={int(seconds_per_image * fps)}:"
                f"x='iw/2-(iw/zoom/2)':"
                f"y='ih/2-(ih/zoom/2)':"
                f"fps={fps},"
                f"setsar=1,"
                f"format=yuv420p"
                f"{draw}"
                f"[{label}]"
            )

        offset = seconds_per_image - (transition_duration * 0.8)

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

        print(result.stderr)

        if result.returncode != 0:
            raise RuntimeError(result.stderr)

        return str(output_file)
