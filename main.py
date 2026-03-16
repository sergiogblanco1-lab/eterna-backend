import os
import uuid
import html
import shutil
import sqlite3
import asyncio
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse

# =========================================================
# CONFIG
# =========================================================

APP_NAME = "ETERNA"

BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"
TEMP_DIR = BASE_DIR / "temp"

FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")
API_KEY = os.getenv("ETERNA_API_KEY", "eterna-secret")

MAX_FOTOS = 6
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_REACTION_BYTES = 120 * 1024 * 1024

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_REACTION_EXTENSIONS = {".webm", ".mp4", ".mov"}

STORAGE_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)

DB_PATH = BASE_DIR / "eterna.db"

app = FastAPI(title="ETERNA Backend")


# =========================================================
# DATABASE
# =========================================================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    db = get_db()

    db.execute("""
    CREATE TABLE IF NOT EXISTS eternas (
        eterna_id TEXT PRIMARY KEY,
        nombre TEXT,
        email TEXT,
        frase1 TEXT,
        frase2 TEXT,
        frase3 TEXT,
        created_at TEXT
    )
    """)

    db.commit()
    db.close()


@app.on_event("startup")
def startup():
    init_db()


# =========================================================
# HELPERS
# =========================================================

def safe_text(text: str) -> str:
    return html.escape((text or "").strip())


def safe_filename(name: str) -> str:
    name = os.path.basename(name)
    name = name.replace(" ", "_")
    name = "".join(c for c in name if c.isalnum() or c in "._-")
    return name


async def save_file_limited(upload: UploadFile, path: Path, max_bytes: int):

    size = 0

    with path.open("wb") as buffer:

        while True:
            chunk = await upload.read(1024 * 1024)

            if not chunk:
                break

            size += len(chunk)

            if size > max_bytes:
                raise HTTPException(413, "Archivo demasiado grande")

            buffer.write(chunk)

    await upload.close()


async def run_ffmpeg(cmd):

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise RuntimeError(stderr.decode())


def html_page(title, body):

    return HTMLResponse(f"""
    <html>
    <head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    <style>

    body {{
        font-family: sans-serif;
        background:#0d0d0d;
        color:white;
        padding:30px;
        max-width:700px;
        margin:auto;
    }}

    input,textarea,button {{
        width:100%;
        padding:14px;
        margin-top:10px;
        border-radius:10px;
        border:1px solid #333;
        background:#111;
        color:white;
    }}

    button {{
        background:white;
        color:black;
        font-weight:bold;
    }}

    video {{
        width:100%;
        border-radius:12px;
        margin-top:20px;
    }}

    </style>
    </head>

    <body>

    {body}

    </body>
    </html>
    """)


async def require_api_key(x_api_key: Optional[str]):

    if x_api_key != API_KEY:
        raise HTTPException(401, "API KEY inválida")


# =========================================================
# VIDEO GENERATION
# =========================================================

async def generate_video(images: List[Path], output: Path):

    concat = TEMP_DIR / f"{uuid.uuid4().hex}.txt"

    with concat.open("w") as f:

        for img in images:
            f.write(f"file '{img}'\n")
            f.write("duration 2\n")

        f.write(f"file '{images[-1]}'\n")

    cmd = [
        FFMPEG_BIN,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat),
        "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2",
        "-pix_fmt", "yuv420p",
        str(output)
    ]

    await run_ffmpeg(cmd)

    concat.unlink(missing_ok=True)


# =========================================================
# HOME
# =========================================================

@app.get("/", response_class=HTMLResponse)
def home():

    return html_page("ETERNA", """
    <h1>ETERNA</h1>

    <p>Convierte 6 fotos en un recuerdo eterno.</p>

    <a href="/crear">
        <button>Crear mi ETERNA</button>
    </a>
    """)


# =========================================================
# CREATE FORM
# =========================================================

@app.get("/crear", response_class=HTMLResponse)
def crear_form():

    return html_page("Crear", """
    <h2>Nueva ETERNA</h2>

    <form action="/crear-eterna" method="post" enctype="multipart/form-data">

    <input name="nombre" placeholder="Tu nombre" required>

    <input name="email" placeholder="Email" required>

    <textarea name="frase1" placeholder="Frase 1"></textarea>
    <textarea name="frase2" placeholder="Frase 2"></textarea>
    <textarea name="frase3" placeholder="Frase 3"></textarea>

    <input type="file" name="fotos" multiple required>

    <button>Crear</button>

    </form>
    """)


# =========================================================
# CREATE ETERNA
# =========================================================

@app.post("/crear-eterna", response_class=HTMLResponse)
async def crear_eterna(
        nombre: str = Form(...),
        email: str = Form(...),
        frase1: str = Form(""),
        frase2: str = Form(""),
        frase3: str = Form(""),
        fotos: List[UploadFile] = File(...)
):

    if len(fotos) != MAX_FOTOS:
        raise HTTPException(400, "Debes subir 6 fotos")

    eterna_id = uuid.uuid4().hex

    folder = STORAGE_DIR / eterna_id
    img_folder = folder / "imagenes"

    img_folder.mkdir(parents=True, exist_ok=True)

    paths = []

    for i, foto in enumerate(fotos):

        filename = safe_filename(foto.filename)

        ext = Path(filename).suffix.lower()

        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            raise HTTPException(400, "Formato imagen no permitido")

        dest = img_folder / f"img{i}{ext}"

        await save_file_limited(foto, dest, MAX_IMAGE_BYTES)

        paths.append(dest)

    video_path = folder / "video.mp4"

    await generate_video(paths, video_path)

    db = get_db()

    db.execute(
        "INSERT INTO eternas VALUES (?,?,?,?,?,?,datetime('now'))",
        (
            eterna_id,
            safe_text(nombre),
            safe_text(email),
            safe_text(frase1),
            safe_text(frase2),
            safe_text(frase3),
        )
    )

    db.commit()
    db.close()

    return html_page("ETERNA creada", f"""
    <h2>ETERNA creada</h2>

    <a href="/ver/{eterna_id}">
        <button>Ver vídeo</button>
    </a>

    <a href="/reaccion/{eterna_id}">
        <button>Grabar reacción</button>
    </a>
    """)


# =========================================================
# VIEW VIDEO
# =========================================================

@app.get("/ver/{eterna_id}", response_class=HTMLResponse)
def ver_video(eterna_id: str):

    return html_page("Ver vídeo", f"""

    <video controls>
        <source src="/video/{eterna_id}">
    </video>

    <a href="/reaccion/{eterna_id}">
        <button>Grabar reacción</button>
    </a>
    """)


@app.get("/video/{eterna_id}")
def video_file(eterna_id: str):

    path = STORAGE_DIR / eterna_id / "video.mp4"

    if not path.exists():
        raise HTTPException(404)

    return FileResponse(path)


# =========================================================
# REACTION PAGE
# =========================================================

@app.get("/reaccion/{eterna_id}", response_class=HTMLResponse)
def reaccion_page(eterna_id: str):

    return html_page("Reacción", f"""

    <h3>Grabar reacción</h3>

    <video controls>
        <source src="/video/{eterna_id}">
    </video>

    <video id="cam" autoplay muted style="display:none"></video>

    <button id="start">Grabar</button>
    <button id="stop" style="display:none">Enviar</button>

<script>

let recorder
let chunks = []

const cam = document.getElementById("cam")

document.getElementById("start").onclick = async () => {{

    const stream = await navigator.mediaDevices.getUserMedia({{video:true,audio:true}})

    cam.srcObject = stream
    cam.style.display="block"

    recorder = new MediaRecorder(stream)

    recorder.ondataavailable = e => chunks.push(e.data)

    recorder.onstop = async () => {{

        const blob = new Blob(chunks)

        const fd = new FormData()

        fd.append("video", blob)

        await fetch("/subir-reaccion/{eterna_id}",{{method:"POST",body:fd}})

        alert("Reacción enviada")

    }}

    recorder.start()

    start.style.display="none"
    stop.style.display="block"
}}

document.getElementById("stop").onclick = () => recorder.stop()

</script>
    """)


# =========================================================
# UPLOAD REACTION
# =========================================================

@app.post("/subir-reaccion/{eterna_id}")
async def subir_reaccion(
        eterna_id: str,
        video: UploadFile = File(...)
):

    folder = STORAGE_DIR / eterna_id / "reaccion"

    folder.mkdir(exist_ok=True)

    path = folder / "reaccion.webm"

    await save_file_limited(video, path, MAX_REACTION_BYTES)

    return {"status": "ok"}
