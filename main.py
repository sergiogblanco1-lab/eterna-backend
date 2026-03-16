from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from typing import List
import os
import uuid
import subprocess
import shutil
from pathlib import Path

app = FastAPI(title="ETERNA Backend")

# =========================================================
# CONFIGURACIÓN
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
STORAGE = BASE_DIR / "storage"
ASSETS = BASE_DIR / "assets"

STORAGE.mkdir(exist_ok=True)
ASSETS.mkdir(exist_ok=True)

PUBLIC_BASE_URL = os.getenv(
    "PUBLIC_BASE_URL",
    "https://eterna-backend-0six.onrender.com"
)

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
SECONDS_PER_PHOTO = 4
FADE_DURATION = 0.8

FONT_FILE_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
]

# Hace pública la carpeta storage
app.mount("/storage", StaticFiles(directory=str(STORAGE)), name="storage")


# =========================================================
# FUNCIONES AYUDA
# =========================================================

def find_font_file():
    for path in FONT_FILE_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


def ffmpeg_escape_text(text: str) -> str:
    if text is None:
        return ""
    text = text.replace("\\", r"\\")
    text = text.replace(":", r"\:")
    text = text.replace("'", r"\'")
    text = text.replace("%", r"\%")
    text = text.replace(",", r"\,")
    text = text.replace("[", r"\[")
    text = text.replace("]", r"\]")
    return text


def save_upload_file(upload: UploadFile, destination: Path) -> None:
    with destination.open("wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)


def run_command(command: List[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Error de FFmpeg.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


def build_drawtext_filter(
    input_label: str,
    text: str,
    start: float,
    end: float,
    output_label: str,
    font_file: str | None,
) -> str:
    safe_text = ffmpeg_escape_text(text)
    font_part = f"fontfile='{font_file}':" if font_file else ""

    return (
        f"{input_label}drawtext="
        f"{font_part}"
        f"text='{safe_text}':"
        f"fontcolor=white:"
        f"fontsize=64:"
        f"line_spacing=12:"
        f"box=1:"
        f"boxcolor=black@0.35:"
        f"boxborderw=30:"
        f"x=(w-text_w)/2:"
        f"y=h*0.78:"
        f"alpha='if(lt(t,{start}),0,"
        f"if(lt(t,{start + 0.6}),(t-{start})/0.6,"
        f"if(lt(t,{end - 0.6}),1,"
        f"if(lt(t,{end}),({end}-t)/0.6,0))))':"
        f"enable='between(t,{start},{end})'"
        f"{output_label}"
    )


def generate_cinematic_video(
    image_paths: List[Path],
    frases: List[str],
    output_path: Path,
    music_path: Path | None = None,
) -> None:
    if not image_paths:
        raise ValueError("No hay imágenes para generar el vídeo.")

    font_file = find_font_file()
    num_images = len(image_paths)
    total_duration = num_images * SECONDS_PER_PHOTO

    command: List[str] = ["ffmpeg", "-y"]

    # Entradas de fotos
    for img_path in image_paths:
        command += [
            "-loop", "1",
            "-t", str(SECONDS_PER_PHOTO),
            "-i", str(img_path)
        ]

    has_music = music_path is not None and music_path.exists()
    if has_music:
        command += [
            "-stream_loop", "-1",
            "-i", str(music_path)
        ]

    filter_parts: List[str] = []

    # Preparamos cada foto
    for i in range(num_images):
        part = (
            f"[{i}:v]"
            f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},"
            f"setsar=1,"
            f"format=yuv420p,"
            f"fade=t=in:st=0:d={FADE_DURATION},"
            f"fade=t=out:st={SECONDS_PER_PHOTO - FADE_DURATION}:d={FADE_DURATION}"
            f"[v{i}]"
        )
        filter_parts.append(part)

    # Unimos todos los clips
    concat_inputs = "".join([f"[v{i}]" for i in range(num_images)])
    filter_parts.append(f"{concat_inputs}concat=n={num_images}:v=1:a=0[base]")

    # Tiempos de frases
    if total_duration >= 12:
        frase_windows = [
            (1.0, min(6.0, total_duration - 1.0)),
            (max(total_duration / 2 - 2.5, 2.0), min(total_duration / 2 + 2.5, total_duration - 2.0)),
            (max(total_duration - 6.0, 2.0), max(total_duration - 1.0, 3.0)),
        ]
    else:
        frase_windows = [
            (0.8, 2.8),
            (3.2, 5.2),
            (5.6, max(total_duration - 0.6, 6.2)),
        ]

    current_label = "[base]"
    for idx, frase in enumerate(frases):
        next_label = f"[txt{idx}]"
        start, end = frase_windows[idx]
        filter_parts.append(
            build_drawtext_filter(
                input_label=current_label,
                text=frase,
                start=start,
                end=end,
                output_label=next_label,
                font_file=font_file,
            )
        )
        current_label = next_label

    final_video_label = current_label
    filter_complex = ";".join(filter_parts)

    command += ["-filter_complex", filter_complex]
    command += ["-map", final_video_label]

    if has_music:
        audio_input_index = num_images
        command += [
            "-map", f"{audio_input_index}:a",
            "-af", "volume=0.18",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
        ]

    command += [
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-movflags", "+faststart",
        str(output_path)
    ]

    run_command(command)


# =========================================================
# RUTAS
# =========================================================

@app.get("/")
def home():
    return {"status": "ETERNA backend alive"}


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/crear-eterna")
async def crear_eterna(
    nombre: str = Form(...),
    email: str = Form(...),
    frase1: str = Form(...),
    frase2: str = Form(...),
    frase3: str = Form(...),
    fotos: List[UploadFile] = File(...)
):
    if len(fotos) < 1:
        raise HTTPException(status_code=400, detail="Debes subir al menos 1 foto.")
    if len(frases := [frase1.strip(), frase2.strip(), frase3.strip()]) != 3:
        raise HTTPException(status_code=400, detail="Necesitas 3 frases.")

    eterna_id = str(uuid.uuid4())
    folder = STORAGE / eterna_id
    folder.mkdir(parents=True, exist_ok=True)

    with (folder / "datos.txt").open("w", encoding="utf-8") as f:
        f.write(f"nombre={nombre}\n")
        f.write(f"email={email}\n")

    with (folder / "frases.txt").open("w", encoding="utf-8") as f:
        for frase in frases:
            f.write(frase + "\n")

    image_paths: List[Path] = []

    for i, foto in enumerate(fotos):
        extension = Path(foto.filename).suffix.lower() if foto.filename else ".jpg"
        if extension not in [".jpg", ".jpeg", ".png", ".webp"]:
            extension = ".jpg"

        img_path = folder / f"foto_{i+1}{extension}"
        save_upload_file(foto, img_path)
        image_paths.append(img_path)

    video_path = folder / "video.mp4"
    music_path = ASSETS / "music.mp3"

    try:
        generate_cinematic_video(
            image_paths=image_paths,
            frases=frases,
            output_path=video_path,
            music_path=music_path if music_path.exists() else None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se pudo generar el vídeo: {str(e)}")

    return {
        "ok": True,
        "eterna_id": eterna_id,
        "video": f"{PUBLIC_BASE_URL}/storage/{eterna_id}/video.mp4",
        "mensaje": "Tu ETERNA cinematográfica ha sido creada"
    }
