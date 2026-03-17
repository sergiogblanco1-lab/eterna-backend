import os
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional


VIDEO_WIDTH = 720
VIDEO_HEIGHT = 1280
FPS = 24
SECONDS_PER_PHOTO = 5.5
FADE_DURATION = 0.8


def _run_command(command: List[str], cwd: Optional[str] = None) -> None:
    result = subprocess.run(command, capture_output=True, text=True, cwd=cwd)

    if result.returncode != 0:
        raise RuntimeError(
            "FFmpeg falló.\n\n"
            f"STDOUT:\n{result.stdout}\n\n"
            f"STDERR:\n{result.stderr}"
        )


def _normalize_paths(image_paths: List[str]) -> List[str]:
    clean = []

    for p in image_paths:
        if p and os.path.exists(p):
            clean.append(str(Path(p)))

    return clean


def _escape_drawtext(text: str) -> str:
    if not text:
        return ""
    return (
        text.replace("\\", r"\\")
        .replace(":", r"\:")
        .replace("'", r"\'")
        .replace(",", r"\,")
        .replace("[", r"\[")
        .replace("]", r"\]")
        .replace("%", r"\%")
    )


def _build_clip_filter(text: str, total_frames: int) -> str:
    safe_text = _escape_drawtext(text)

    zoom_filter = (
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},"
        f"zoompan=z='min(zoom+0.0006,1.12)':"
        f"d={total_frames}:"
        f"x='iw/2-(iw/zoom/2)':"
        f"y='ih/2-(ih/zoom/2)':"
        f"s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={FPS}"
    )

    fade_out_start = max(0.0, SECONDS_PER_PHOTO - FADE_DURATION)

    filters = [
        zoom_filter,
        "format=yuv420p",
        f"fade=t=in:st=0:d={FADE_DURATION}",
        f"fade=t=out:st={fade_out_start}:d={FADE_DURATION}",
    ]

    if safe_text:
        filters.append(
            "drawtext="
            f"text='{safe_text}':"
            "fontcolor=white:"
            "fontsize=42:"
            "x=(w-text_w)/2:"
            "y=h-160:"
            "box=1:"
            "boxcolor=black@0.35:"
            "boxborderw=20"
        )

    return ",".join(filters)


def _create_end_card(
    temp_dir: Path,
    end_message: str,
) -> str:
    end_name = "end_card.mp4"
    end_path = temp_dir / end_name
    safe_text = _escape_drawtext(end_message or "Hay momentos que merecen quedarse para siempre")

    filter_complex = (
        f"color=c=black:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:d=4,"
        "format=yuv420p,"
        f"fade=t=in:st=0:d=1,"
        f"fade=t=out:st=3:d=1,"
        "drawtext="
        f"text='{safe_text}':"
        "fontcolor=white:"
        "fontsize=44:"
        "x=(w-text_w)/2:"
        "y=(h-text_h)/2"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", filter_complex,
        "-r", str(FPS),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "26",
        str(end_path),
    ]

    _run_command(cmd)
    return end_name


def generate_eterna_video(
    image_paths: List[str],
    frases: List[str],
    output_path: str,
    music_path: Optional[str] = None,
    intro_text: str = "",
    outro_text: str = "",
    end_message: str = "",
) -> str:
    image_paths = _normalize_paths(image_paths)

    if not image_paths:
        raise ValueError("No hay imágenes válidas para crear el vídeo.")

    output_parent = Path(output_path).parent
    output_parent.mkdir(parents=True, exist_ok=True)

    temp_dir = output_parent / "temp_video"

    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)

    temp_dir.mkdir(parents=True, exist_ok=True)

    clip_names: List[str] = []
    total_frames = int(FPS * SECONDS_PER_PHOTO)

    try:
        for i, image_path in enumerate(image_paths, start=1):
            clip_name = f"clip_{i}.mp4"
            clip_path = temp_dir / clip_name

            phrase_text = frases[i - 1] if i - 1 < len(frases) else ""
            vf_filter = _build_clip_filter(phrase_text, total_frames)

            cmd = [
                "ffmpeg",
                "-y",
                "-loop", "1",
                "-t", str(SECONDS_PER_PHOTO),
                "-i", image_path,
                "-vf", vf_filter,
                "-r", str(FPS),
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "24",
                "-pix_fmt", "yuv420p",
                str(clip_path),
            ]

            _run_command(cmd)
            clip_names.append(clip_name)

        end_card_name = _create_end_card(
            temp_dir=temp_dir,
            end_message=end_message or "Hay momentos que merecen quedarse para siempre",
        )
        clip_names.append(end_card_name)

        concat_file = temp_dir / "concat.txt"
        with open(concat_file, "w", encoding="utf-8") as f:
            for clip_name in clip_names:
                f.write(f"file '{clip_name}'\n")

        base_video = temp_dir / "base.mp4"

        _run_command(
            [
                "ffmpeg",
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", "concat.txt",
                "-c", "copy",
                "base.mp4",
            ],
            cwd=str(temp_dir),
        )

        if music_path and os.path.exists(music_path):
            _run_command(
                [
                    "ffmpeg",
                    "-y",
                    "-i", str(base_video),
                    "-stream_loop", "-1",
                    "-i", music_path,
                    "-map", "0:v:0",
                    "-map", "1:a:0",
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-shortest",
                    output_path,
                ]
            )
        else:
            shutil.copyfile(str(base_video), output_path)

    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

    return output_path


def create_video(
    image_paths: List[str],
    frases: List[str],
    output_path: str,
    music_path: Optional[str] = None,
    intro_text: str = "",
    outro_text: str = "",
    end_message: str = "",
) -> str:
    return generate_eterna_video(
        image_paths=image_paths,
        frases=frases,
        output_path=output_path,
        music_path=music_path,
        intro_text=intro_text,
        outro_text=outro_text,
        end_message=end_message,
    )


def generate_video(
    image_paths: List[str],
    frases: List[str],
    output_path: str,
    music_path: Optional[str] = None,
    intro_text: str = "",
    outro_text: str = "",
    end_message: str = "",
) -> str:
    return generate_eterna_video(
        image_paths=image_paths,
        frases=frases,
        output_path=output_path,
        music_path=music_path,
        intro_text=intro_text,
        outro_text=outro_text,
        end_message=end_message,
    )


def build_video_from_images(
    image_paths: List[str],
    frases: List[str],
    output_path: str,
    music_path: Optional[str] = None,
    intro_text: str = "",
    outro_text: str = "",
    end_message: str = "",
) -> str:
    return generate_eterna_video(
        image_paths=image_paths,
        frases=frases,
        output_path=output_path,
        music_path=music_path,
        intro_text=intro_text,
        outro_text=outro_text,
        end_message=end_message,
    )


class VideoEngine:
    def generate_video(
        self,
        order_id: str,
        photos: List[str],
        phrases: List[str],
        output_path: str,
        music_path: Optional[str] = None,
        intro_text: str = "",
        outro_text: str = "",
        end_message: str = "",
        sender_video_path: Optional[str] = None,
    ) -> str:
        return generate_eterna_video(
            image_paths=photos,
            frases=phrases,
            output_path=output_path,
            music_path=music_path,
            intro_text=intro_text,
            outro_text=outro_text,
            end_message=end_message or "Hay momentos que merecen quedarse para siempre",
        )
