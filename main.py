import os
import uuid
import shutil
import sqlite3
import asyncio
from pathlib import Path
from typing import List

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse

# =====================================================
# CONFIG
# =====================================================

BASE_DIR = Path(__file__).resolve().parent

STORAGE = BASE_DIR / "storage"
TEMP = BASE_DIR / "temp"

STORAGE.mkdir(exist_ok=True)
TEMP.mkdir(exist_ok=True)

DB = BASE_DIR / "eterna.db"

FFMPEG = "ffmpeg"

MAX_FOTOS = 6

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

app = FastAPI(title="ETERNA")


# =====================================================
# DATABASE
# =====================================================

def init_db():

    conn = sqlite3.connect(DB)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS eternas(
        eterna_id TEXT PRIMARY KEY,
        nombre TEXT,
        email TEXT,
        frase1 TEXT,
        frase2 TEXT,
        frase3 TEXT
    )
    """)

    conn.commit()
    conn.close()


@app.on_event("startup")
def startup():
    init_db()


# =====================================================
# HELPERS
# =====================================================

def safe_filename(name):

    name = os.path.basename(name)

    name = name.replace(" ", "_")

    return "".join(c for c in name if c.isalnum() or c in "._-")


async def save_file(upload: UploadFile, path: Path):

    with path.open("wb") as buffer:

        while True:

            chunk = await upload.read(1024 * 1024)

            if not chunk:
                break

            buffer.write(chunk)

    await upload.close()


async def run_ffmpeg(cmd):

    process = await asyncio.create_subprocess_exec(*cmd)

    await process.communicate()


# =====================================================
# GENERADOR DE VIDEO ETERNA
# =====================================================

async def generar_video(imagenes, salida):

    fps = 30
    duracion_foto = 4.0
    transicion = 1.0

    ancho = 720
    alto = 1280

    inputs = []
    filtros = []

    # INTRO NEGRA

    filtros.append(
        f"color=c=black:s={ancho}x{alto}:d=1[intro]"
    )

    # PREPARAR IMÁGENES

    for i, img in enumerate(imagenes):

        inputs.extend([
            "-loop", "1",
            "-t", str(duracion_foto),
            "-i", str(img)
        ])

        filtros.append(
            f"[{i}:v]"
            f"scale={ancho}:{alto}:force_original_aspect_ratio=increase,"
            f"crop={ancho}:{alto},"
            f"zoompan=z='min(zoom+0.0012,1.12)':"
            f"d={int(duracion_foto * fps)}:"
            f"s={ancho}x{alto}:"
            f"fps={fps},"
            f"setsar=1"
            f"[v{i}]"
        )

    # CROSSFADE ENTRE FOTOS

    last = "v0"
    offset = duracion_foto - transicion

    for i in range(1, len(imagenes)):

        nuevo = f"mix{i}"

        filtros.append(
            f"[{last}][v{i}]"
            f"xfade=transition=fade:"
            f"duration={transicion}:"
            f"offset={offset}"
            f"[{nuevo}]"
        )

        last = nuevo
        offset += duracion_foto - transicion

    # PANTALLA FINAL

    filtros.append(
        f"color=c=black:s={ancho}x{alto}:d=3[final];"
        f"[final]"
        f"drawtext=text='Hay momentos':"
        f"fontcolor=white:fontsize=48:x=(w-text_w)/2:y=(h/2)-80,"
        f"drawtext=text='que merecen quedarse para siempre':"
        f"fontcolor=white:fontsize=36:x=(w-text_w)/2:y=(h/2),"
        f"drawtext=text='ETERNA':"
        f"fontcolor=white:fontsize=42:x=(w-text_w)/2:y=(h/2)+120"
        f"[outro]"
    )

    filtros.append(
        f"[{last}][outro]concat=n=2:v=1:a=0[video]"
    )

    filter_complex = ";".join(filtros)

    cmd = [
        FFMPEG,
        "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[video]",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "20",
        "-preset", "medium",
        "-movflags", "+faststart",
        str(salida)
    ]

    await run_ffmpeg(cmd)


# =====================================================
# HOME
# =====================================================

@app.get("/", response_class=HTMLResponse)
def home():

    return HTMLResponse("""

    <h1>ETERNA</h1>

    <p>Convierte 6 fotos en un recuerdo eterno.</p>

    <a href="/crear">

    <button>Crear mi ETERNA</button>

    </a>

    """)


# =====================================================
# FORM
# =====================================================

@app.get("/crear", response_class=HTMLResponse)
def crear():

    return HTMLResponse("""

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


# =====================================================
# CREAR ETERNA
# =====================================================

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

    carpeta = STORAGE / eterna_id
    imgs = carpeta / "imagenes"

    imgs.mkdir(parents=True)

    paths = []

    for i, foto in enumerate(fotos):

        ext = Path(foto.filename).suffix.lower()

        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            raise HTTPException(400, "Formato imagen no permitido")

        dest = imgs / f"img{i}{ext}"

        await save_file(foto, dest)

        paths.append(dest)

    video = carpeta / "video.mp4"

    await generar_video(paths, video)

    db = sqlite3.connect(DB)

    db.execute(
        "INSERT INTO eternas VALUES (?,?,?,?,?,?)",
        (eterna_id, nombre, email, frase1, frase2, frase3)
    )

    db.commit()
    db.close()

    return HTMLResponse(f"""

    <h2>ETERNA creada</h2>

    <a href="/ver/{eterna_id}">

    <button>Ver vídeo</button>

    </a>

    <a href="/reaccion/{eterna_id}">

    <button>Grabar reacción</button>

    </a>

    """)


# =====================================================
# VER VIDEO
# =====================================================

@app.get("/ver/{eterna_id}", response_class=HTMLResponse)
def ver(eterna_id: str):

    return HTMLResponse(f"""

    <video controls width="100%">

    <source src="/video/{eterna_id}">

    </video>

    <a href="/reaccion/{eterna_id}">

    <button>Grabar reacción</button>

    </a>

    """)


@app.get("/video/{eterna_id}")
def video(eterna_id: str):

    path = STORAGE / eterna_id / "video.mp4"

    if not path.exists():
        raise HTTPException(404)

    return FileResponse(path)


# =====================================================
# GRABAR REACCION
# =====================================================

@app.get("/reaccion/{eterna_id}", response_class=HTMLResponse)
def reaccion(eterna_id: str):

    return HTMLResponse(f"""

    <video controls width="100%">

    <source src="/video/{eterna_id}">

    </video>

    <video id="cam" autoplay muted style="display:none"></video>

    <button id="start">Grabar</button>

    <button id="stop" style="display:none">Enviar</button>

<script>

let recorder
let chunks=[]

const cam=document.getElementById("cam")

start.onclick=async()=>{{

const stream=await navigator.mediaDevices.getUserMedia({{video:true,audio:true}})

cam.srcObject=stream
cam.style.display="block"

recorder=new MediaRecorder(stream)

recorder.ondataavailable=e=>chunks.push(e.data)

recorder.onstop=async()=>{{

const blob=new Blob(chunks)

const fd=new FormData()

fd.append("video",blob)

await fetch("/subir-reaccion/{eterna_id}",{{method:"POST",body:fd}})

alert("Reacción enviada")

}}

recorder.start()

start.style.display="none"
stop.style.display="block"

}}

stop.onclick=()=>recorder.stop()

</script>

    """)


# =====================================================
# SUBIR REACCION
# =====================================================

@app.post("/subir-reaccion/{eterna_id}")
async def subir_reaccion(
        eterna_id: str,
        video: UploadFile = File(...)
):

    carpeta = STORAGE / eterna_id / "reaccion"

    carpeta.mkdir(exist_ok=True)

    dest = carpeta / "reaccion.webm"

    await save_file(video, dest)

    return {"ok": True}
