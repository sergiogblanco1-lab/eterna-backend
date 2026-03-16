import os
import uuid
import html
import json
import time
import shutil
import sqlite3
import asyncio
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Header
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse

# =========================================================
# CONFIG
# =========================================================

APP_NAME = "ETERNA"
BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"
TEMP_DIR = BASE_DIR / "temp"
DB_PATH = BASE_DIR / "eterna.db"

FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")
API_KEY = os.getenv("ETERNA_API_KEY", "cambiar-esta-api-key")
MAX_FOTOS = 6

MAX_IMAGE_BYTES = 5 * 1024 * 1024         # 5 MB por foto
MAX_REACTION_BYTES = 120 * 1024 * 1024    # 120 MB reacción

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_REACTION_EXTENSIONS = {".webm", ".mp4", ".mov"}

STORAGE_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)

app = FastAPI(
    title="ETERNA Backend",
    description="Backend de ETERNA: creación de recuerdos emocionales, vídeo principal y vídeo de reacción.",
    version="1.0.0",
)

# =========================================================
# DATABASE
# =========================================================

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS eternas (
        eterna_id TEXT PRIMARY KEY,
        nombre TEXT NOT NULL,
        email TEXT NOT NULL,
        frase1 TEXT,
        frase2 TEXT,
        frase3 TEXT,
        permiso_envio INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        video_status TEXT NOT NULL,
        reaction_status TEXT NOT NULL DEFAULT 'pending'
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS reactions (
        reaction_id TEXT PRIMARY KEY,
        eterna_id TEXT NOT NULL,
        consentimiento INTEGER NOT NULL DEFAULT 0,
        raw_path TEXT,
        converted_path TEXT,
        final_path TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (eterna_id) REFERENCES eternas (eterna_id)
    )
    """)

    conn.commit()
    conn.close()


@app.on_event("startup")
def startup_event():
    init_db()


# =========================================================
# HELPERS
# =========================================================

def now_iso() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def safe_text(value: str) -> str:
    return (value or "").strip()


def sanitize_html_text(value: str) -> str:
    return html.escape(safe_text(value), quote=True)


def safe_filename(name: str) -> str:
    base = os.path.basename(name or "archivo")
    base = base.replace(" ", "_")
    cleaned = "".join(c for c in base if c.isalnum() or c in "._-")
    cleaned = cleaned.strip("._-")
    return cleaned or "archivo"


def ensure_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def escape_drawtext(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("%", "\\%")
        .replace(",", "\\,")
        .replace("[", "\\[")
        .replace("]", "\\]")
    )


async def run_ffmpeg_async(command: List[str]) -> None:
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise RuntimeError(
            f"FFmpeg falló.\nSTDOUT:\n{stdout.decode(errors='ignore')}\nSTDERR:\n{stderr.decode(errors='ignore')}"
        )


async def save_upload_file_limited(upload: UploadFile, destination: Path, max_bytes: int) -> int:
    total = 0
    with destination.open("wb") as buffer:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                buffer.close()
                destination.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"Archivo demasiado grande. Máximo permitido: {max_bytes // (1024 * 1024)} MB"
                )
            buffer.write(chunk)
    await upload.close()
    return total


def save_frases_json(frases: List[str], folder: Path) -> None:
    data = {
        "frase1": frases[0],
        "frase2": frases[1],
        "frase3": frases[2],
    }
    with (folder / "frases.json").open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_concat_list(image_paths: List[Path], list_path: Path, seconds_per_image: int = 2) -> None:
    with list_path.open("w", encoding="utf-8") as f:
        for img in image_paths:
            f.write(f"file '{img.as_posix()}'\n")
            f.write(f"duration {seconds_per_image}\n")
        f.write(f"file '{image_paths[-1].as_posix()}'\n")


def html_page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="es">
        <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1" />
            <title>{html.escape(title)} | {APP_NAME}</title>
            <style>
                * {{
                    box-sizing: border-box;
                }}
                body {{
                    margin: 0;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                    background: #0d0d0d;
                    color: #f5f5f5;
                    line-height: 1.5;
                }}
                .wrap {{
                    max-width: 760px;
                    margin: 0 auto;
                    padding: 28px 18px 40px;
                }}
                .card {{
                    background: #171717;
                    border: 1px solid #2a2a2a;
                    border-radius: 20px;
                    padding: 20px;
                    box-shadow: 0 10px 30px rgba(0,0,0,.25);
                }}
                h1, h2, h3 {{
                    margin-top: 0;
                }}
                label {{
                    display: block;
                    margin-top: 8px;
                    margin-bottom: 6px;
                    font-weight: 600;
                }}
                input, textarea, button {{
                    width: 100%;
                    border-radius: 12px;
                    border: 1px solid #333;
                    background: #111;
                    color: #fff;
                    padding: 14px;
                    margin-top: 4px;
                    margin-bottom: 16px;
                    font-size: 16px;
                }}
                textarea {{
                    min-height: 90px;
                    resize: vertical;
                }}
                button {{
                    background: #fff;
                    color: #111;
                    font-weight: 700;
                    cursor: pointer;
                }}
                button:hover {{
                    opacity: .96;
                }}
                button:disabled {{
                    opacity: .55;
                    cursor: not-allowed;
                }}
                .muted {{
                    color: #b8b8b8;
                    font-size: 14px;
                }}
                .ok {{
                    color: #7ee787;
                }}
                .err {{
                    color: #ff7b72;
                }}
                a {{
                    color: #fff;
                    text-decoration: none;
                }}
                video {{
                    width: 100%;
                    border-radius: 16px;
                    background: #000;
                }}
                .row {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 14px;
                }}
                .pill {{
                    display: inline-block;
                    padding: 6px 10px;
                    border-radius: 999px;
                    background: #222;
                    border: 1px solid #333;
                    font-size: 13px;
                    margin-bottom: 14px;
                }}
                .space {{
                    height: 12px;
                }}
                .checkline {{
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    margin-bottom: 16px;
                }}
                .checkline input {{
                    width: auto;
                    margin: 0;
                }}
                .code {{
                    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
                    background: #111;
                    border: 1px solid #333;
                    border-radius: 10px;
                    padding: 10px;
                    overflow-x: auto;
                }}
                @media (max-width: 640px) {{
                    .row {{
                        grid-template-columns: 1fr;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="wrap">
                {body}
            </div>
        </body>
        </html>
        """
    )


async def require_api_key(x_api_key: Optional[str]) -> None:
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="API key inválida o ausente.")


# =========================================================
# VIDEO PRINCIPAL
# =========================================================

def build_text_overlay_filter(frases: List[str]) -> str:
    cleaned = [escape_drawtext(f) for f in frases if safe_text(f)]
    if not cleaned:
        return "fps=25,format=yuv420p,scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2"

    base = "fps=25,format=yuv420p,scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2"
    overlays = []

    positions = [940, 1010, 1080]
    for idx, frase in enumerate(cleaned[:3]):
        overlays.append(
            f"drawtext=text='{frase}':fontcolor=white:fontsize=28:box=1:boxcolor=black@0.35:"
            f"x=(w-text_w)/2:y={positions[idx]}"
        )

    return ",".join([base] + overlays)


async def generate_video_from_images(image_paths: List[Path], output_video: Path, frases: List[str]) -> None:
    if not image_paths:
        raise ValueError("No hay imágenes para generar el vídeo.")

    concat_file = TEMP_DIR / f"concat_{uuid.uuid4().hex}.txt"

    try:
        build_concat_list(image_paths, concat_file, seconds_per_image=2)

        vf = build_text_overlay_filter(frases)

        command = [
            FFMPEG_BIN,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-vf", vf,
            "-movflags", "+faststart",
            str(output_video),
        ]
        await run_ffmpeg_async(command)

        if not output_video.exists():
            raise RuntimeError("FFmpeg terminó pero no se creó video.mp4")

    finally:
        concat_file.unlink(missing_ok=True)


# =========================================================
# REACTION VIDEO BRANDING
# =========================================================

async def create_color_clip(output_path: Path, text_lines: List[str], duration: int = 3, size: str = "720x1280") -> None:
    safe_lines = [escape_drawtext(line) for line in text_lines if safe_text(line)]

    if not safe_lines:
        safe_lines = ["ETERNA"]

    filters = []
    base_y = 430
    step = 90

    for i, line in enumerate(safe_lines):
        y_value = base_y + (i * step)
        filters.append(
            f"drawtext=text='{line}':fontcolor=white:fontsize=42:x=(w-text_w)/2:y={y_value}"
        )

    vf = ",".join(filters)

    command = [
        FFMPEG_BIN,
        "-y",
        "-f", "lavfi",
        "-i", f"color=c=black:s={size}:d={duration}",
        "-vf", vf,
        "-r", "25",
        "-pix_fmt", "yuv420p",
        str(output_path),
    ]
    await run_ffmpeg_async(command)


async def convert_video_to_mp4(input_path: Path, output_path: Path) -> None:
    command = [
        FFMPEG_BIN,
        "-y",
        "-i", str(input_path),
        "-c:v", "libx264",
        "-c:a", "aac",
        "-movflags", "+faststart",
        str(output_path),
    ]
    await run_ffmpeg_async(command)


async def concat_videos(video_paths: List[Path], output_path: Path) -> None:
    concat_file = TEMP_DIR / f"concat_video_{uuid.uuid4().hex}.txt"
    try:
        with concat_file.open("w", encoding="utf-8") as f:
            for video in video_paths:
                f.write(f"file '{video.as_posix()}'\n")

        command = [
            FFMPEG_BIN,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c:v", "libx264",
            "-c:a", "aac",
            "-movflags", "+faststart",
            str(output_path),
        ]
        await run_ffmpeg_async(command)

    finally:
        concat_file.unlink(missing_ok=True)


async def build_branded_reaction_video(reaction_input: Path, output_final: Path) -> None:
    intro_path = TEMP_DIR / f"intro_{uuid.uuid4().hex}.mp4"
    reaction_mp4 = TEMP_DIR / f"reaction_{uuid.uuid4().hex}.mp4"
    outro_path = TEMP_DIR / f"outro_{uuid.uuid4().hex}.mp4"

    try:
        await create_color_clip(
            intro_path,
            text_lines=[
                "ETERNA",
                "Un momento que queda para siempre",
            ],
            duration=3,
        )

        await convert_video_to_mp4(reaction_input, reaction_mp4)

        await create_color_clip(
            outro_path,
            text_lines=[
                "Gracias por este momento",
                "ETERNA",
            ],
            duration=3,
        )

        await concat_videos(
            [intro_path, reaction_mp4, outro_path],
            output_final,
        )

    finally:
        intro_path.unlink(missing_ok=True)
        reaction_mp4.unlink(missing_ok=True)
        outro_path.unlink(missing_ok=True)


# =========================================================
# DATABASE HELPERS
# =========================================================

def db_create_eterna(
    eterna_id: str,
    nombre: str,
    email: str,
    frase1: str,
    frase2: str,
    frase3: str,
    permiso_envio: int,
    video_status: str,
) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO eternas (
            eterna_id, nombre, email, frase1, frase2, frase3,
            permiso_envio, created_at, video_status, reaction_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        eterna_id, nombre, email, frase1, frase2, frase3,
        permiso_envio, now_iso(), video_status, "pending"
    ))
    conn.commit()
    conn.close()


def db_update_eterna_status(eterna_id: str, video_status: Optional[str] = None, reaction_status: Optional[str] = None) -> None:
    conn = get_db()
    cur = conn.cursor()

    if video_status is not None:
        cur.execute("UPDATE eternas SET video_status=? WHERE eterna_id=?", (video_status, eterna_id))

    if reaction_status is not None:
        cur.execute("UPDATE eternas SET reaction_status=? WHERE eterna_id=?", (reaction_status, eterna_id))

    conn.commit()
    conn.close()


def db_insert_reaction(
    eterna_id: str,
    consentimiento: int,
    raw_path: str,
    converted_path: str,
    final_path: str,
) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO reactions (
            reaction_id, eterna_id, consentimiento,
            raw_path, converted_path, final_path, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        uuid.uuid4().hex,
        eterna_id,
        consentimiento,
        raw_path,
        converted_path,
        final_path,
        now_iso(),
    ))
    conn.commit()
    conn.close()


def db_get_eterna(eterna_id: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM eternas WHERE eterna_id = ?", (eterna_id,))
    row = cur.fetchone()
    conn.close()
    return row


# =========================================================
# ROUTES
# =========================================================

@app.get("/", response_class=HTMLResponse)
def home():
    return html_page(
        "ETERNA",
        """
        <div class="card">
            <div class="pill">ETERNA</div>
            <h1>Hay momentos que merecen quedarse para siempre.</h1>
            <p>Crea una ETERNA con 6 fotos y 3 frases.</p>
            <p class="muted">
                Primero se crea el recuerdo. Después se comparte.
                Y solo si la persona da permiso, se puede grabar la reacción.
            </p>
            <a href="/crear"><button>Crear mi ETERNA</button></a>
        </div>
        """
    )


@app.get("/healthz")
def healthz():
    ffmpeg_ok = shutil.which(FFMPEG_BIN) is not None
    return {
        "status": "ok",
        "app": APP_NAME,
        "storage_exists": STORAGE_DIR.exists(),
        "temp_exists": TEMP_DIR.exists(),
        "ffmpeg_available": ffmpeg_ok,
        "db_exists": DB_PATH.exists(),
    }


@app.get("/crear", response_class=HTMLResponse)
def crear_form():
    return html_page(
        "Crear ETERNA",
        """
        <div class="card">
            <div class="pill">Crear ETERNA</div>
            <h1>Sube 6 fotos y escribe 3 frases</h1>

            <p class="muted">
                Esta página usa protección por API key al enviar.
                En producción, el frontend debe mandar la cabecera <strong>X-API-Key</strong>.
            </p>

            <form id="eternaForm">
                <label>Tu nombre</label>
                <input type="text" name="nombre" placeholder="Ej: Sergio" required />

                <label>Tu email</label>
                <input type="email" name="email" placeholder="Ej: tu@email.com" required />

                <label>Frase 1</label>
                <textarea name="frase1" placeholder="Ej: Gracias por todo." required></textarea>

                <label>Frase 2</label>
                <textarea name="frase2" placeholder="Ej: Siempre estaré contigo." required></textarea>

                <label>Frase 3</label>
                <textarea name="frase3" placeholder="Ej: Este recuerdo es para ti." required></textarea>

                <label>6 fotos (máx. 5 MB cada una)</label>
                <input type="file" name="fotos" accept=".jpg,.jpeg,.png,.webp" multiple required />

                <div class="checkline">
                    <input type="checkbox" name="permiso_envio" value="si" required />
                    <span>Confirmo que tengo permiso para enviar este recuerdo.</span>
                </div>

                <label>API key</label>
                <input type="password" name="api_key" placeholder="Tu API key" required />

                <button type="submit">Crear mi ETERNA</button>
            </form>

            <p id="status" class="muted"></p>

            <script>
                const form = document.getElementById('eternaForm');
                const status = document.getElementById('status');

                form.addEventListener('submit', async (e) => {
                    e.preventDefault();

                    const fotos = form.querySelector('input[name="fotos"]').files;
                    if (fotos.length !== 6) {
                        status.textContent = "Debes subir exactamente 6 fotos.";
                        return;
                    }

                    const formData = new FormData();
                    formData.append("nombre", form.nombre.value);
                    formData.append("email", form.email.value);
                    formData.append("frase1", form.frase1.value);
                    formData.append("frase2", form.frase2.value);
                    formData.append("frase3", form.frase3.value);
                    formData.append("permiso_envio", form.permiso_envio.checked ? "si" : "no");

                    for (const file of fotos) {
                        formData.append("fotos", file);
                    }

                    status.textContent = "Creando ETERNA...";

                    try {
                        const response = await fetch("/crear-eterna", {
                            method: "POST",
                            headers: {
                                "X-API-Key": form.api_key.value
                            },
                            body: formData
                        });

                        const text = await response.text();
                        document.open();
                        document.write(text);
                        document.close();
                    } catch (err) {
                        status.textContent = "Error creando ETERNA: " + err.message;
                    }
                });
            </script>
        </div>
        """
    )


@app.post("/crear-eterna", response_class=HTMLResponse)
async def crear_eterna(
    nombre: str = Form(...),
    email: str = Form(...),
    frase1: str = Form(...),
    frase2: str = Form(...),
    frase3: str = Form(...),
    permiso_envio: str = Form(...),
    fotos: List[UploadFile] = File(...),
    x_api_key: Optional[str] = Header(None),
):
    await require_api_key(x_api_key)

    nombre_raw = safe_text(nombre)
    email_raw = safe_text(email)
    frase1_raw = safe_text(frase1)
    frase2_raw = safe_text(frase2)
    frase3_raw = safe_text(frase3)

    nombre = sanitize_html_text(nombre_raw)
    email = sanitize_html_text(email_raw)
    frases = [
        sanitize_html_text(frase1_raw),
        sanitize_html_text(frase2_raw),
        sanitize_html_text(frase3_raw),
    ]

    if permiso_envio.lower() != "si":
        raise HTTPException(status_code=400, detail="Debes confirmar el permiso de envío.")

    if not nombre_raw:
        raise HTTPException(status_code=400, detail="El nombre es obligatorio.")

    if not email_raw:
        raise HTTPException(status_code=400, detail="El email es obligatorio.")

    if len(fotos) != MAX_FOTOS:
        raise HTTPException(status_code=400, detail=f"Debes subir exactamente {MAX_FOTOS} fotos.")

    eterna_id = uuid.uuid4().hex
    folder = STORAGE_DIR / eterna_id
    images_folder = folder / "imagenes"
    ensure_folder(images_folder)

    image_paths: List[Path] = []

    try:
        for idx, foto in enumerate(fotos, start=1):
            original_name = safe_filename(foto.filename or f"foto_{idx}.jpg")
            ext = Path(original_name).suffix.lower()

            if ext not in ALLOWED_IMAGE_EXT
