import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Optional


# =========================================================
# ETERNA VIDEO ENGINE — VERSION MEJORADA
# =========================================================

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 30

INTRO_SECONDS = 3.2
OUTRO_SECONDS = 4.0
PHOTO_SECONDS = 4.2
FADE_DURATION = 0.8
TEXT_FADE = 0.7

MUSIC_VOLUME = 0.18
AUDIO_FADE_IN = 1.5
AUDIO_FADE_OUT = 2.0

DEFAULT_INTRO_TEXT = "Hay momentos que merecen quedarse para siempre"
DEFAULT_OUTRO_TEXT = "ETERNA"
DEFAULT_END_MESSAGE = "Para siempre"

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
]


# =========================================================
# HELPERS
# =========================================================

def _find_font_file() -> Optional[str]:
    for font_path in FONT_CANDIDATES:
        if os.path.exists(font_path):
            return font_path
    return None


def _escape_drawtext(text: str) -> str:
    if text is None:
        return ""
    text = str(text)
    text = text.replace("\\", r"\\")
    text = text.replace(":", r"\:")
    text = text.replace("'", r"\'")
    text = text.replace("%", r"\%")
    text = text.replace(",", r"\,")
    text = text.replace("[", r"\[")
    text = text.replace("]", r"\]")
    return text


def _run_command(command: List[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            "FFmpeg falló.\n\n"
            f"STDOUT:\n{result.stdout}\n\n"
            f"STDERR:\n{result.stderr}"
        )


def _ensure_parent(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _normalize_paths(image_paths: List[str]) -> List[str]:
    clean = []
    for p in image_paths:
        if p and os.path.exists(p):
            clean.append(str(Path(p)))
    return clean


def _safe_frases(frases: List[str]) -> List[str]:
    out = []
    for frase in frases[:3]:
        frase = str(frase or "").strip()
        if not frase:
            frase = " "
        out.append(frase)
    while len(out) < 3:
        out.append(" ")
    return out


def _audio_filter(total_duration: float) -> str:
    fade_out_start = max(total_duration - AUDIO_FADE_OUT, 0)
    return (
        f"volume={MUSIC_VOLUME},"
        f"afade=t=in:st=0:d={AUDIO_FADE_IN},"
        f"afade=t=out:st={fade_out_start}:d={AUDIO_FADE_OUT}"
    )


def _build_zoompan_filter(duration: float, motion_type: str) -> str:
    frames = int(duration * FPS)

    if motion_type == "zoom_in":
        zoom_expr = "min(zoom+0.0009,1.18)"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"
    elif motion_type == "zoom_out":
        zoom_expr = "if(eq(on,1),1.18,max(zoom-0.0009,1.0))"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"
    elif motion_type == "pan_left":
        zoom_expr = "1.10"
        x_expr = "max(iw/2-(iw/zoom/2)-on*0.6,0)"
        y_expr = "ih/2-(ih/zoom/2)"
    else:  # pan_right
        zoom_expr = "1.10"
        x_expr = "min(iw/2-(iw/zoom/2)+on*0.6, iw-iw/zoom)"
        y_expr = "ih/2-(ih/zoom/2)"

    return (
        f"scale=1400:2400:force_original_aspect_ratio=increase,"
        f"zoompan="
        f"z='{zoom_expr}':"
        f"x='{x_expr}':"
        f"y='{y_expr}':"
        f"d={frames}:"
        f"s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:"
        f"fps={FPS},"
        f"format=yuv420p"
    )


def _build_clip_filter(duration: float, motion_type: str) -> str:
    return (
        f"{_build_zoompan_filter(duration, motion_type)},"
        f"fade=t=in:st=0:d={FADE_DURATION},"
        f"fade=t=out:st={duration - FADE_DURATION}:d={FADE_DURATION}"
    )


def _build_drawtext(
    input_label: str,
    output_label: str,
    text: str,
    start: float,
    end: float,
    font_file: Optional[str],
    fontsize: int = 64,
    y_expr: str = "h*0.78",
    box_opacity: float = 0.26,
    borderw: int = 28,
) -> str:
    safe_text = _escape_drawtext(text)
    font_part = f"fontfile='{font_file}':" if font_file else ""

    fade_in_end = start + TEXT_FADE
    fade_out_start = max(end - TEXT_FADE, start)

    alpha_expr = (
        f"if(lt(t,{start}),0,"
        f"if(lt(t,{fade_in_end}),(t-{start})/{TEXT_FADE},"
        f"if(lt(t,{fade_out_start}),1,"
        f"if(lt(t,{end}),({end}-t)/{TEXT_FADE},0))))"
    )

    return (
        f"{input_label}drawtext="
        f"{font_part}"
        f"text='{safe_text}':"
        f"fontcolor=white:"
        f"fontsize={fontsize}:"
        f"line_spacing=12:"
        f"box=1:"
        f"boxcolor=black@{box_opacity}:"
        f"boxborderw={borderw}:"
        f"x=(w-text_w)/2:"
        f"y={y_expr}:"
        f"alpha='{alpha_expr}':"
        f"enable='between(t,{start},{end})'"
        f"{output_label}"
    )


def _build_text_timeline(total_duration: float, frases: List[str]):
    frases = _safe_frases(frases)

    first_start = INTRO_SECONDS + 0.9
    first_end = first_start + 3.2

    middle_start = total_duration / 2 - 2.0
    middle_end = middle_start + 3.7

    final_start = max(total_duration - OUTRO_SECONDS - 3.2, middle_end + 0.8)
    final_end = min(final_start + 3.0, total_duration - 1.1)

    return [
        (frases[0], first_start, first_end),
        (frases[1], middle_start, middle_end),
        (frases[2], final_start, final_end),
    ]


def _create_text_screen(
    output_path: str,
    text: str,
    seconds: float,
    font_file: Optional[str],
    fontsize: int,
    secondary_text: Optional[str] = None,
) -> None:
    safe_text = _escape_drawtext(text)
    font_part = f"fontfile='{font_file}':" if font_file else ""

    base = (
        f"color=c=black:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:d={seconds},"
        f"format=yuv420p,"
        f"drawtext="
        f"{font_part}"
        f"text='{safe_text}':"
        f"fontcolor=white:"
        f"fontsize={fontsize}:"
        f"line_spacing=14:"
        f"x=(w-text_w)/2:"
        f"y=(h-text_h)/2-40:"
        f"alpha='if(lt(t,0.4),0,"
        f"if(lt(t,1.4),(t-0.4)/1.0,"
        f"if(lt(t,{seconds - 1.0}),1,"
        f"if(lt(t,{seconds}),({seconds}-t)/1.0,0))))'"
    )

    if secondary_text:
        safe_secondary = _escape_drawtext(secondary_text)
        base += (
            f",drawtext="
            f"{font_part}"
            f"text='{safe_secondary}':"
            f"fontcolor=white:"
            f"fontsize=42:"
            f"x=(w-text_w)/2:"
            f"y=(h-text_h)/2+95:"
            f"alpha='if(lt(t,1.0),0,"
            f"if(lt(t,2.0),(t-1.0)/1.0,"
            f"if(lt(t,{seconds - 0.8}),0.75,"
            f"if(lt(t,{seconds}),(({seconds}-t)/0.8)*0.75,0))))'"
        )

    _run_command([
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", base,
        "-r", str(FPS),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output_path
    ])


# =========================================================
# CORE
# =========================================================

def generate_eterna_video(
    image_paths: List[str],
    frases: List[str],
    output_path: str,
    music_path: Optional[str] = None,
    intro_text: str = DEFAULT_INTRO_TEXT,
    outro_text: str = DEFAULT_OUTRO_TEXT,
    end_message: str = DEFAULT_END_MESSAGE,
) -> str:
    image_paths = _normalize_paths(image_paths)

    if not image_paths:
        raise ValueError("No hay imágenes válidas para crear el vídeo.")

    frases = _safe_frases(frases)
    _ensure_parent(output_path)

    font_file = _find_font_file()
    has_music = bool(music_path and os.path.exists(music_path))

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)

        # -------------------------------------------------
        # 1) Crear clips individuales por foto
        # -------------------------------------------------
        photo_clips = []
        motion_cycle = ["zoom_in", "pan_left", "zoom_out", "pan_right"]

        for i, image_path in enumerate(image_paths):
            clip_path = temp_dir_path / f"clip_{i+1}.mp4"
            motion_type = motion_cycle[i % len(motion_cycle)]

            cmd = [
                "ffmpeg",
                "-y",
                "-loop", "1",
                "-t", str(PHOTO_SECONDS),
                "-i", image_path,
                "-vf", _build_clip_filter(PHOTO_SECONDS, motion_type),
                "-r", str(FPS),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                str(clip_path)
            ]

            _run_command(cmd)
            photo_clips.append(str(clip_path))

        # -------------------------------------------------
        # 2) Crear intro y outro
        # -------------------------------------------------
        intro_path = temp_dir_path / "intro.mp4"
        outro_path = temp_dir_path / "outro.mp4"

        _create_text_screen(
            output_path=str(intro_path),
            text=intro_text,
            seconds=INTRO_SECONDS,
            font_file=font_file,
            fontsize=54,
            secondary_text=None,
        )

        _create_text_screen(
            output_path=str(outro_path),
            text=outro_text,
            seconds=OUTRO_SECONDS,
            font_file=font_file,
            fontsize=72,
            secondary_text=end_message,
        )

        # -------------------------------------------------
        # 3) Concatenar intro + fotos + outro
        # -------------------------------------------------
        concat_list_path = temp_dir_path / "concat.txt"
        ordered_clips = [str(intro_path)] + photo_clips + [str(outro_path)]

        with open(concat_list_path, "w", encoding="utf-8") as f:
            for clip in ordered_clips:
                safe_clip = clip.replace("\\", "/").replace("'", r"'\''")
                f.write(f"file '{safe_clip}'\n")

        base_video_path = temp_dir_path / "base_video.mp4"

        _run_command([
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list_path),
            "-c", "copy",
            str(base_video_path)
        ])

        # -------------------------------------------------
        # 4) Añadir frases encima del vídeo
        # -------------------------------------------------
        total_duration = INTRO_SECONDS + len(photo_clips) * PHOTO_SECONDS + OUTRO_SECONDS
        timeline = _build_text_timeline(total_duration, frases)

        filter_parts = []
        current_label = "[0:v]"

        for idx, (texto, start, end) in enumerate(timeline):
            next_label = f"[txt{idx}]"
            filter_parts.append(
                _build_drawtext(
                    input_label=current_label,
                    output_label=next_label,
                    text=texto,
                    start=start,
                    end=end,
                    font_file=font_file,
                    fontsize=66 if idx < 2 else 72,
                    y_expr="h*0.78" if idx < 2 else "h*0.72",
                    box_opacity=0.24 if idx < 2 else 0.20,
                    borderw=26 if idx < 2 else 22,
                )
            )
            current_label = next_label

        final_video_no_audio = temp_dir_path / "video_no_audio.mp4"

        _run_command([
            "ffmpeg",
            "-y",
            "-i", str(base_video_path),
            "-filter_complex", ";".join(filter_parts),
            "-map", current_label,
            "-r", str(FPS),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(final_video_no_audio)
        ])

        # -------------------------------------------------
        # 5) Añadir música si existe
        # -------------------------------------------------
        if has_music:
            _run_command([
                "ffmpeg",
                "-y",
                "-i", str(final_video_no_audio),
                "-stream_loop", "-1",
                "-i", music_path,
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-af", _audio_filter(total_duration),
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                output_path
            ])
        else:
            shutil.copyfile(str(final_video_no_audio), output_path)

    return output_path


# =========================================================
# WRAPPERS COMPATIBLES
# =========================================================

def create_video(
    image_paths: List[str],
    frases: List[str],
    output_path: str,
    music_path: Optional[str] = None,
    intro_text: str = DEFAULT_INTRO_TEXT,
    outro_text: str = DEFAULT_OUTRO_TEXT,
    end_message: str = DEFAULT_END_MESSAGE,
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
    intro_text: str = DEFAULT_INTRO_TEXT,
    outro_text: str = DEFAULT_OUTRO_TEXT,
    end_message: str = DEFAULT_END_MESSAGE,
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
    intro_text: str = DEFAULT_INTRO_TEXT,
    outro_text: str = DEFAULT_OUTRO_TEXT,
    end_message: str = DEFAULT_END_MESSAGE,
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
