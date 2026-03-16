import os
import uuid
import html
import sqlite3
import asyncio
import urllib.parse
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, JSONResponse

APP_NAME = "ETERNA"
PRICE_EUR = 79

BASE_DIR = Path(__file__).resolve().parent
STORAGE = BASE_DIR / "storage"
DB = BASE_DIR / "eterna.db"

STORAGE.mkdir(exist_ok=True)

FFMPEG = os.getenv("FFMPEG_BIN", "ffmpeg")

MAX_FOTOS = 6
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_VIDEO_MSG_BYTES = 40 * 1024 * 1024
MAX_REACTION_BYTES = 120 * 1024 * 1024

ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_VIDEO_EXT = {".mp4", ".mov", ".webm"}

app = FastAPI(title="ETERNA")


# =========================
# DATABASE
# =========================

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    c = db()
    c.execute("""
    CREATE TABLE IF NOT EXISTS eternas(
        id TEXT PRIMARY KEY,
        nombre TEXT,
        email TEXT,
        frase1 TEXT,
        frase2 TEXT,
        frase3 TEXT,
        destinatario TEXT,
        telefono TEXT,
        pagado INTEGER DEFAULT 0,
        created_at TEXT
    )
    """)
    c.commit()
    c.close()


@app.on_event("startup")
def start():
    init_db()


# =========================
# HELPERS
# =========================

def safe_filename(name: str) -> str:
    base = os.path.basename(name or "archivo")
    base = base.replace(" ", "_")
    return "".join(c for c in base if c.isalnum() or c in "._-") or "archivo"


def normalize_phone(phone: str) -> str:
    allowed = "+0123456789"
    return "".join(c for c in phone if c in allowed)


async def save_file(upload: UploadFile, path: Path, max_bytes: int):
    total = 0
    with path.open("wb") as f:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise HTTPException(413, "Archivo demasiado grande")
            f.write(chunk)
    await upload.close()


async def run(cmd):
    proc = await asyncio.create_subprocess_exec(*cmd)
    await proc.communicate()


def page(title: str, body: str):
    return HTMLResponse(f"""
    <html>
    <head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>

    body {{
        background:#0d0d0d;
        color:white;
        font-family:Arial;
        max-width:600px;
        margin:auto;
        padding:20px;
    }}

    input,textarea,button {{
        width:100%;
        padding:14px;
        margin-top:10px;
        border-radius:10px;
        border:none;
    }}

    button {{
        background:white;
        color:black;
        font-weight:bold;
    }}

    video {{
        width:100%;
        margin-top:20px;
        border-radius:12px;
    }}

    .cam {{
        position:fixed;
        bottom:10px;
        right:10px;
        width:90px;
        border-radius:10px;
    }}

    </style>
    </head>

    <body>

    {body}

    </body>
    </html>
    """)


# =========================
# VIDEO GENERATOR
# =========================

async def generar_video(imagenes: List[Path], salida: Path):

    fps = 30
    duracion = 6

    lista = STORAGE / f"{uuid.uuid4().hex}.txt"

    with open(lista,"w") as f:
        for img in imagenes:
            f.write(f"file '{img}'\n")
            f.write(f"duration {duracion}\n")
        f.write(f"file '{imagenes[-1]}'\n")

    filtro = (
        "scale=720:1280:force_original_aspect_ratio=decrease,"
        "pad=720:1280:(ow-iw)/2:(oh-ih)/2,"
        "zoompan=z='min(zoom+0.0006,1.07)':d=180:s=720x1280:fps=30"
    )

    cmd=[
        FFMPEG,
        "-y",
        "-f","concat",
        "-safe","0",
        "-i",str(lista),
        "-vf",filtro,
        "-pix_fmt","yuv420p",
        "-preset","veryfast",
        "-movflags","+faststart",
        str(salida)
    ]

    await run(cmd)

    lista.unlink(missing_ok=True)


async def unir_video(recuerdo: Path, mensaje: Path, salida: Path):

    lista = STORAGE / f"{uuid.uuid4().hex}_concat.txt"

    with open(lista,"w") as f:
        f.write(f"file '{recuerdo}'\n")
        f.write(f"file '{mensaje}'\n")

    cmd=[
        FFMPEG,
        "-y",
        "-f","concat",
        "-safe","0",
        "-i",str(lista),
        "-c","copy",
        str(salida)
    ]

    await run(cmd)

    lista.unlink(missing_ok=True)


# =========================
# HOME
# =========================

@app.get("/",response_class=HTMLResponse)
def home():
    return page("ETERNA", """

    <h1>ETERNA</h1>

    <p>Convierte 6 fotos en un recuerdo emocional.</p>

    <a href="/crear">
    <button>Crear mi ETERNA</button>
    </a>

    """)


# =========================
# FORM
# =========================

@app.get("/crear",response_class=HTMLResponse)
def crear():
    return page("Crear","""

    <h2>Nueva ETERNA</h2>

    <form action="/crear" method="post" enctype="multipart/form-data">

    <input name="nombre" placeholder="Tu nombre" required>

    <input name="email" placeholder="Tu email" required>

    <input name="destinatario" placeholder="Nombre destinatario" required>

    <input name="telefono" placeholder="Teléfono destinatario" required>

    <textarea name="frase1" placeholder="Frase 1"></textarea>
    <textarea name="frase2" placeholder="Frase 2"></textarea>
    <textarea name="frase3" placeholder="Frase 3"></textarea>

    <label>Mensaje de vídeo (máx 20s)</label>
    <input type="file" name="mensaje">

    <input type="file" name="fotos" multiple required>

    <button>Crear recuerdo</button>

    </form>

    """)


# =========================
# CREATE
# =========================

@app.post("/crear")
async def crear_post(
    nombre:str=Form(...),
    email:str=Form(...),
    destinatario:str=Form(...),
    telefono:str=Form(...),
    frase1:str=Form(""),
    frase2:str=Form(""),
    frase3:str=Form(""),
    fotos:List[UploadFile]=File(...),
    mensaje:UploadFile|None=File(None)
):

    if len(fotos)!=6:
        raise HTTPException(400,"Sube 6 fotos")

    eterna_id=uuid.uuid4().hex

    folder=STORAGE/eterna_id
    folder.mkdir()

    imagenes=[]

    for i,f in enumerate(fotos):

        path=folder/f"img{i}.jpg"

        with open(path,"wb") as buffer:
            buffer.write(await f.read())

        imagenes.append(path)

    recuerdo=folder/"recuerdo.mp4"

    await generar_video(imagenes,recuerdo)

    final=folder/"video.mp4"

    if mensaje:

        msg_path=folder/"mensaje.mp4"

        with open(msg_path,"wb") as b:
            b.write(await mensaje.read())

        await unir_video(recuerdo,msg_path,final)

    else:

        final=recuerdo

    conn=db()

    conn.execute(
        "INSERT INTO eternas VALUES(?,?,?,?,?,?,?,?,?,datetime('now'))",
        (eterna_id,nombre,email,frase1,frase2,frase3,destinatario,telefono,0)
    )

    conn.commit()
    conn.close()

    return RedirectResponse(f"/checkout/{eterna_id}",303)


# =========================
# CHECKOUT
# =========================

@app.get("/checkout/{id}",response_class=HTMLResponse)
def checkout(id):

    return page("Pago",f"""

    <h2>Tu ETERNA está lista</h2>

    <video controls>
    <source src="/video/{id}">
    </video>

    <h2>{PRICE_EUR}€</h2>

    <form action="/pagar/{id}" method="post">
    <button>Desbloquear ETERNA</button>
    </form>

    """)


# =========================
# PAY
# =========================

@app.post("/pagar/{id}")
def pagar(id):

    conn=db()

    conn.execute("UPDATE eternas SET pagado=1 WHERE id=?",(id,))

    conn.commit()
    conn.close()

    return RedirectResponse(f"/enviar/{id}",303)


# =========================
# SEND
# =========================

@app.get("/enviar/{id}",response_class=HTMLResponse)
def enviar(id):

    link=f"/ver/{id}"

    return page("Enviar",f"""

    <h2>Enviar ETERNA</h2>

    <a href="{link}">
    <button>Ver enlace</button>
    </a>

    """)


# =========================
# WATCH VIDEO
# =========================

@app.get("/ver/{id}",response_class=HTMLResponse)
def ver(id):

    return page("Recuerdo",f"""

    <h2>Este momento fue creado para ti</h2>

    <video controls>
    <source src="/video/{id}">
    </video>

    <a href="/reaccion/{id}">
    <button>Grabar reacción</button>
    </a>

    """)


@app.get("/video/{id}")
def video(id):

    path=STORAGE/id/"video.mp4"

    if not path.exists():
        raise HTTPException(404)

    return FileResponse(path,media_type="video/mp4")
