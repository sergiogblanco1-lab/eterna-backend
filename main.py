import os
import uuid
import html
import sqlite3
import asyncio
import urllib.parse
from pathlib import Path
from typing import List

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, JSONResponse

APP_NAME = "ETERNA"
PRICE_EUR = 79

BASE_DIR = Path(__file__).resolve().parent
STORAGE = BASE_DIR / "storage"
DB_PATH = BASE_DIR / "eterna.db"

STORAGE.mkdir(exist_ok=True)

FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")

MAX_FOTOS = 6
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_REACTION_BYTES = 120 * 1024 * 1024

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_REACTION_EXTENSIONS = {".webm", ".mp4", ".mov"}

app = FastAPI(title="ETERNA")


# =====================================================
# DB
# =====================================================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS eternas(
        eterna_id TEXT PRIMARY KEY,
        nombre TEXT,
        email TEXT,
        frase1 TEXT,
        frase2 TEXT,
        frase3 TEXT,
        destinatario_nombre TEXT,
        destinatario_telefono TEXT,
        pagado INTEGER DEFAULT 0,
        created_at TEXT
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

def safe_text(value: str) -> str:
    return html.escape((value or "").strip())


def raw_text(value: str) -> str:
    return (value or "").strip()


def safe_filename(name: str) -> str:
    base = os.path.basename(name or "archivo")
    base = base.replace(" ", "_")
    cleaned = "".join(c for c in base if c.isalnum() or c in "._-")
    return cleaned or "archivo"


def normalize_phone(phone: str) -> str:
    phone = raw_text(phone)
    allowed = "+0123456789"
    return "".join(ch for ch in phone if ch in allowed)


async def save_file_limited(upload: UploadFile, path: Path, max_bytes: int):
    total = 0

    with path.open("wb") as buffer:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break

            total += len(chunk)
            if total > max_bytes:
                buffer.close()
                path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Archivo demasiado grande")

            buffer.write(chunk)

    await upload.close()


async def run_ffmpeg_async(cmd: List[str]):
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise RuntimeError(
            f"FFmpeg falló.\n"
            f"STDOUT:\n{stdout.decode(errors='ignore')}\n"
            f"STDERR:\n{stderr.decode(errors='ignore')}"
        )


def page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(f"""
    <!doctype html>
    <html lang="es">
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>{html.escape(title)} | {APP_NAME}</title>
        <style>
            * {{
                box-sizing: border-box;
            }}
            body {{
                margin: 0;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background: #0d0d0d;
                color: white;
                max-width: 760px;
                margin-inline: auto;
                padding: 24px 16px 40px;
                line-height: 1.5;
            }}
            .card {{
                background: #171717;
                border: 1px solid #2b2b2b;
                border-radius: 18px;
                padding: 20px;
                box-shadow: 0 10px 30px rgba(0,0,0,.20);
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
            h1, h2, h3, p {{
                margin-top: 0;
            }}
            input, textarea, button {{
                width: 100%;
                padding: 14px;
                margin-top: 8px;
                margin-bottom: 16px;
                border-radius: 12px;
                border: 1px solid #333;
                background: #111;
                color: white;
                font-size: 16px;
            }}
            textarea {{
                min-height: 90px;
                resize: vertical;
            }}
            button {{
                background: white;
                color: black;
                font-weight: 700;
                cursor: pointer;
            }}
            button:hover {{
                opacity: .96;
            }}
            .secondary {{
                background: #1f1f1f;
                color: white;
                border: 1px solid #333;
            }}
            video {{
                width: 100%;
                margin-top: 14px;
                border-radius: 14px;
                background: black;
            }}
            .muted {{
                color: #b8b8b8;
                font-size: 14px;
            }}
            .row {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 12px;
            }}
            .small-cam {{
                position: fixed;
                right: 14px;
                bottom: 14px;
                width: 92px;
                height: 132px;
                object-fit: cover;
                border-radius: 12px;
                border: 1px solid rgba(255,255,255,.15);
                box-shadow: 0 10px 24px rgba(0,0,0,.35);
                background: #000;
                z-index: 9999;
            }}
            a {{
                color: white;
                text-decoration: none;
            }}
            .price {{
                font-size: 28px;
                font-weight: 800;
                margin: 6px 0 16px;
            }}
            @media (max-width: 640px) {{
                .row {{
                    grid-template-columns: 1fr;
                }}
            }}
        </style>
    </head>
    <body>
        {body}
    </body>
    </html>
    """)


def cleanup_folder(folder: Path):
    if not folder.exists():
        return

    for child in folder.rglob("*"):
        if child.is_file():
            child.unlink(missing_ok=True)

    for child in sorted(folder.rglob("*"), reverse=True):
        if child.is_dir():
            child.rmdir()

    folder.rmdir()


def get_eterna_row(eterna_id: str):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM eternas WHERE eterna_id = ?",
        (eterna_id,)
    ).fetchone()
    conn.close()
    return row


def build_absolute_link(request: Request, eterna_id: str) -> str:
    return str(request.base_url).rstrip("/") + f"/ver/{eterna_id}"


def build_whatsapp_link(phone: str, absolute_link: str) -> str:
    mensaje = (
        "He creado algo para ti.\n\n"
        "Ábrelo cuando tengas un momento tranquilo ❤️\n\n"
        f"{absolute_link}"
    )
    encoded = urllib.parse.quote(mensaje)
    return f"https://wa.me/{phone}?text={encoded}"


# =====================================================
# VIDEO
# =====================================================

async def generar_video(imagenes: List[Path], salida: Path):
    """
    Recuerdo:
    - 6 fotos
    - zoom lento
    - fade entre fotos
    - vertical móvil
    - duración aprox 40s
    """

    if len(imagenes) != 6:
        raise ValueError("Deben llegar exactamente 6 imágenes.")

    fps = 30
    duracion_foto = 7.0
    transicion = 1.0
    ancho = 720
    alto = 1280

    input_args = []
    filters = []

    for i, img in enumerate(imagenes):
        input_args.extend([
            "-loop", "1",
            "-t", str(duracion_foto),
            "-i", str(img)
        ])

        filters.append(
            f"[{i}:v]"
            f"scale={ancho}:{alto}:force_original_aspect_ratio=increase,"
            f"crop={ancho}:{alto},"
            f"zoompan="
            f"z='min(zoom+0.0007,1.08)':"
            f"d={int(duracion_foto * fps)}:"
            f"s={ancho}x{alto}:"
            f"fps={fps},"
            f"setsar=1,"
            f"format=yuv420p"
            f"[v{i}]"
        )

    current = "v0"
    offset = duracion_foto - transicion

    for i in range(1, len(imagenes)):
        out = f"x{i}"
        filters.append(
            f"[{current}][v{i}]"
            f"xfade=transition=fade:duration={transicion}:offset={offset}"
            f"[{out}]"
        )
        current = out
        offset += duracion_foto - transicion

    filter_complex = ";".join(filters)

    cmd = [
        FFMPEG_BIN,
        "-y",
        *input_args,
        "-filter_complex", filter_complex,
        "-map", f"[{current}]",
        "-r", str(fps),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "20",
        "-profile:v", "main",
        "-level", "3.1",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(salida)
    ]

    await run_ffmpeg_async(cmd)


# =====================================================
# ROUTES
# =====================================================

@app.get("/", response_class=HTMLResponse)
def home():
    return page("ETERNA", """
    <div class="card">
        <div class="pill">ETERNA</div>
        <h1>Hay momentos que merecen quedarse para siempre.</h1>
        <p>Convierte 6 fotos y 3 frases en un recuerdo emocional.</p>
        <a href="/crear-eterna">
            <button>Crear mi ETERNA</button>
        </a>
    </div>
    """)


@app.get("/healthz")
def healthz():
    return {
        "status": "ok",
        "app": APP_NAME,
        "storage_exists": STORAGE.exists(),
        "db_exists": DB_PATH.exists(),
        "ffmpeg_bin": FFMPEG_BIN,
    }


@app.get("/crear-eterna", response_class=HTMLResponse)
def crear_form():
    return page("Crear ETERNA", """
    <div class="card">
        <div class="pill">Crear ETERNA</div>
        <h2>Sube 6 fotos y escribe 3 frases</h2>

        <form action="/crear-eterna" method="post" enctype="multipart/form-data">
            <input name="nombre" placeholder="Tu nombre" required />
            <input name="email" placeholder="Tu email" required />

            <input name="destinatario_nombre" placeholder="Nombre de quien lo recibirá" required />
            <input name="destinatario_telefono" placeholder="Teléfono de quien lo recibirá (+34...)" required />

            <textarea name="frase1" placeholder="Frase 1"></textarea>
            <textarea name="frase2" placeholder="Frase 2"></textarea>
            <textarea name="frase3" placeholder="Frase 3"></textarea>

            <input type="file" name="fotos" accept=".jpg,.jpeg,.png,.webp" multiple required />

            <button>Crear mi ETERNA</button>
        </form>

        <p class="muted">Usa exactamente 6 fotos.</p>
    </div>
    """)


@app.post("/crear-eterna", response_class=HTMLResponse)
async def crear_eterna(
    nombre: str = Form(...),
    email: str = Form(...),
    destinatario_nombre: str = Form(...),
    destinatario_telefono: str = Form(...),
    frase1: str = Form(""),
    frase2: str = Form(""),
    frase3: str = Form(""),
    fotos: List[UploadFile] = File(...)
):
    if len(fotos) != MAX_FOTOS:
        raise HTTPException(status_code=400, detail="Debes subir exactamente 6 fotos")

    telefono = normalize_phone(destinatario_telefono)
    if len(telefono.replace("+", "")) < 8:
        raise HTTPException(status_code=400, detail="Teléfono no válido")

    eterna_id = uuid.uuid4().hex
    folder = STORAGE / eterna_id
    images_folder = folder / "imagenes"
    images_folder.mkdir(parents=True, exist_ok=True)

    image_paths: List[Path] = []

    try:
        for idx, foto in enumerate(fotos):
            original_name = safe_filename(foto.filename or f"foto_{idx}.jpg")
            ext = Path(original_name).suffix.lower()

            if ext not in ALLOWED_IMAGE_EXTENSIONS:
                raise HTTPException(status_code=400, detail=f"Formato no permitido: {original_name}")

            dest = images_folder / f"img{idx}{ext}"
            await save_file_limited(foto, dest, MAX_IMAGE_BYTES)
            image_paths.append(dest)

        video_path = folder / "video.mp4"
        await generar_video(image_paths, video_path)

        conn = get_db()
        conn.execute(
            "INSERT INTO eternas VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))",
            (
                eterna_id,
                safe_text(nombre),
                safe_text(email),
                safe_text(frase1),
                safe_text(frase2),
                safe_text(frase3),
                safe_text(destinatario_nombre),
                telefono,
                0,
            )
        )
        conn.commit()
        conn.close()

        return RedirectResponse(url=f"/checkout/{eterna_id}", status_code=303)

    except Exception:
        cleanup_folder(folder)
        raise


@app.get("/checkout/{eterna_id}", response_class=HTMLResponse)
def checkout(eterna_id: str):
    row = get_eterna_row(eterna_id)
    if row is None:
        raise HTTPException(status_code=404, detail="ETERNA no encontrada")

    if row["pagado"] == 1:
        return RedirectResponse(url=f"/enviar/{eterna_id}", status_code=303)

    return page("Desbloquear ETERNA", f"""
    <div class="card">
        <div class="pill">Pago</div>
        <h2>Tu ETERNA está lista</h2>
        <p>
            Para enviarla a <strong>{row["destinatario_nombre"]}</strong>
            y recibir su reacción, desbloquéala.
        </p>

        <div class="price">{PRICE_EUR}€</div>

        <video controls playsinline preload="metadata">
            <source src="/video/{eterna_id}" type="video/mp4">
        </video>

        <p class="muted">
            Este botón simula el pago para dejar el flujo funcionando.
            Después lo cambiamos por Stripe real.
        </p>

        <form action="/pagar/{eterna_id}" method="post">
            <button>Desbloquear ETERNA · {PRICE_EUR}€</button>
        </form>
    </div>
    """)


@app.post("/pagar/{eterna_id}")
def pagar_eterna(eterna_id: str):
    row = get_eterna_row(eterna_id)
    if row is None:
        raise HTTPException(status_code=404, detail="ETERNA no encontrada")

    conn = get_db()
    conn.execute(
        "UPDATE eternas SET pagado = 1 WHERE eterna_id = ?",
        (eterna_id,)
    )
    conn.commit()
    conn.close()

    return RedirectResponse(url=f"/enviar/{eterna_id}", status_code=303)


@app.get("/enviar/{eterna_id}", response_class=HTMLResponse)
def enviar_page(eterna_id: str, request: Request):
    row = get_eterna_row(eterna_id)
    if row is None:
        raise HTTPException(status_code=404, detail="ETERNA no encontrada")

    if row["pagado"] != 1:
        return RedirectResponse(url=f"/checkout/{eterna_id}", status_code=303)

    absolute_link = build_absolute_link(request, eterna_id)
    wa_link = build_whatsapp_link(row["destinatario_telefono"], absolute_link)

    return page("Enviar ETERNA", f"""
    <div class="card">
        <div class="pill">Enviar</div>
        <h2>Tu ETERNA ya está desbloqueada</h2>
        <p>
            Envíala ahora a <strong>{row["destinatario_nombre"]}</strong>.
        </p>

        <div class="row">
            <a href="{wa_link}" target="_blank" rel="noopener noreferrer">
                <button>Enviar por WhatsApp</button>
            </a>

            <a href="/copiar-enlace/{eterna_id}">
                <button class="secondary">Copiar enlace</button>
            </a>
        </div>

        <p class="muted">
            El recuerdo se abrirá desde el enlace y después la persona podrá grabar su reacción.
        </p>
    </div>
    """)


@app.get("/copiar-enlace/{eterna_id}", response_class=HTMLResponse)
def copiar_enlace_page(eterna_id: str, request: Request):
    row = get_eterna_row(eterna_id)
    if row is None:
        raise HTTPException(status_code=404, detail="ETERNA no encontrada")

    if row["pagado"] != 1:
        return RedirectResponse(url=f"/checkout/{eterna_id}", status_code=303)

    link = build_absolute_link(request, eterna_id)

    return page("Copiar enlace", f"""
    <div class="card">
        <div class="pill">Copiar enlace</div>
        <h2>Enlace listo</h2>

        <input id="eternaLink" value="{link}" readonly />

        <button onclick="navigator.clipboard.writeText(document.getElementById('eternaLink').value)">
            Copiar enlace
        </button>

        <a href="/enviar/{eterna_id}">
            <button class="secondary">Volver</button>
        </a>
    </div>
    """)


@app.get("/ver/{eterna_id}", response_class=HTMLResponse)
def ver_video(eterna_id: str):
    path = STORAGE / eterna_id / "video.mp4"
    row = get_eterna_row(eterna_id)

    if row is None:
        raise HTTPException(status_code=404, detail="ETERNA no encontrada")

    if not path.exists():
        raise HTTPException(status_code=404, detail="Vídeo no encontrado")

    return page("Ver recuerdo", f"""
    <div class="card">
        <div class="pill">ETERNA</div>
        <h2>Este momento fue creado para ti, {row["destinatario_nombre"]}</h2>
        <p class="muted">
            Mira el recuerdo con calma. Después podrás grabar tu reacción
            para enviársela a quien lo creó.
        </p>

        <video controls playsinline preload="metadata">
            <source src="/video/{eterna_id}" type="video/mp4">
        </video>

        <a href="/reaccion/{eterna_id}">
            <button>Grabar reacción</button>
        </a>
    </div>
    """)


@app.get("/video/{eterna_id}")
def video_file(eterna_id: str):
    path = STORAGE / eterna_id / "video.mp4"

    if not path.exists():
        raise HTTPException(status_code=404, detail="Vídeo no encontrado")

    return FileResponse(path, media_type="video/mp4", filename="video.mp4")


@app.get("/reaccion/{eterna_id}", response_class=HTMLResponse)
def reaccion_page(eterna_id: str):
    path = STORAGE / eterna_id / "video.mp4"

    if not path.exists():
        raise HTTPException(status_code=404, detail="Vídeo no encontrado")

    return page("Grabar reacción", f"""
    <div class="card">
        <div class="pill">Reacción</div>
        <h2>Este momento fue creado para ti</h2>
        <p>
            Mira el recuerdo y, cuando quieras, graba tu reacción
            para enviársela a quien lo creó.
        </p>

        <video id="recuerdo" controls playsinline preload="metadata">
            <source src="/video/{eterna_id}" type="video/mp4">
        </video>

        <p class="muted">
            La cámara se verá pequeña para no romper la emoción del vídeo.
        </p>

        <video id="cam" class="small-cam" autoplay muted playsinline style="display:none"></video>

        <button id="start">Grabar mi reacción</button>
        <button id="stop" style="display:none">Enviar reacción</button>

        <p id="estado" class="muted"></p>

        <script>
        let recorder;
        let chunks = [];
        let currentStream = null;

        const cam = document.getElementById("cam");
        const startBtn = document.getElementById("start");
        const stopBtn = document.getElementById("stop");
        const estado = document.getElementById("estado");

        startBtn.onclick = async () => {{
            try {{
                estado.textContent = "Pidiendo permiso para cámara y micrófono...";
                currentStream = await navigator.mediaDevices.getUserMedia({{ video: true, audio: true }});

                cam.srcObject = currentStream;
                cam.style.display = "block";
                chunks = [];

                let mimeType = "";
                if (MediaRecorder.isTypeSupported("video/webm;codecs=vp9,opus")) {{
                    mimeType = "video/webm;codecs=vp9,opus";
                }} else if (MediaRecorder.isTypeSupported("video/webm")) {{
                    mimeType = "video/webm";
                }} else if (MediaRecorder.isTypeSupported("video/mp4")) {{
                    mimeType = "video/mp4";
                }}

                recorder = mimeType ? new MediaRecorder(currentStream, {{ mimeType }}) : new MediaRecorder(currentStream);

                recorder.ondataavailable = (e) => {{
                    if (e.data && e.data.size > 0) {{
                        chunks.push(e.data);
                    }}
                }};

                recorder.onstop = async () => {{
                    try {{
                        estado.textContent = "Subiendo reacción...";
                        const finalMime = recorder.mimeType || "video/webm";
                        const ext = finalMime.includes("mp4") ? "mp4" : "webm";
                        const blob = new Blob(chunks, {{ type: finalMime }});

                        const fd = new FormData();
                        fd.append("video", blob, "reaccion." + ext);

                        const response = await fetch("/subir-reaccion/{eterna_id}", {{
                            method: "POST",
                            body: fd
                        }});

                        if (!response.ok) {{
                            const text = await response.text();
                            throw new Error(text || "No se pudo subir la reacción");
                        }}

                        estado.textContent = "Reacción enviada correctamente.";
                        alert("Reacción enviada");
                    }} catch (err) {{
                        estado.textContent = "Error al subir la reacción.";
                        alert("Error al subir la reacción");
                    }} finally {{
                        if (currentStream) {{
                            currentStream.getTracks().forEach(track => track.stop());
                        }}
                        cam.style.display = "none";
                        startBtn.style.display = "block";
                        stopBtn.style.display = "none";
                    }}
                }};

                recorder.start();
                estado.textContent = "Grabando reacción...";
                startBtn.style.display = "none";
                stopBtn.style.display = "block";
            }} catch (err) {{
                estado.textContent = "No se pudo acceder a cámara o micrófono.";
                alert("No se pudo acceder a cámara o micrófono");
            }}
        }};

        stopBtn.onclick = () => {{
            if (recorder) {{
                recorder.stop();
            }}
        }};
        </script>
    </div>
    """)


@app.post("/subir-reaccion/{eterna_id}")
async def subir_reaccion(
    eterna_id: str,
    video: UploadFile = File(...)
):
    folder = STORAGE / eterna_id

    if not folder.exists():
        raise HTTPException(status_code=404, detail="ETERNA no encontrada")

    ext = Path(video.filename or "reaccion.webm").suffix.lower()

    if ext not in ALLOWED_REACTION_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Formato de reacción no permitido")

    reaction_folder = folder / "reaccion"
    reaction_folder.mkdir(exist_ok=True)

    dest = reaction_folder / f"reaccion{ext}"
    await save_file_limited(video, dest, MAX_REACTION_BYTES)

    return JSONResponse({"ok": True})


@app.get("/ver-reaccion/{eterna_id}", response_class=HTMLResponse)
def ver_reaccion(eterna_id: str):
    reaction_folder = STORAGE / eterna_id / "reaccion"

    candidates = [
        reaction_folder / "reaccion.mp4",
        reaction_folder / "reaccion.webm",
        reaction_folder / "reaccion.mov",
    ]

    chosen = None
    mime = "video/webm"

    for item in candidates:
        if item.exists():
            chosen = item
            if item.suffix.lower() == ".mp4":
                mime = "video/mp4"
            elif item.suffix.lower() == ".mov":
                mime = "video/quicktime"
            break

    if chosen is None:
        raise HTTPException(status_code=404, detail="Reacción no encontrada")

    return page("Ver reacción", f"""
    <div class="card">
        <div class="pill">Reacción</div>
        <h2>Vídeo de reacción</h2>

        <video controls playsinline preload="metadata">
            <source src="/archivo-reaccion/{eterna_id}/{chosen.name}" type="{mime}">
        </video>
    </div>
    """)


@app.get("/archivo-reaccion/{eterna_id}/{filename}")
def archivo_reaccion(eterna_id: str, filename: str):
    safe_name = safe_filename(filename)
    path = STORAGE / eterna_id / "reaccion" / safe_name

    if not path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    media_type = "application/octet-stream"
    if path.suffix.lower() == ".mp4":
        media_type = "video/mp4"
    elif path.suffix.lower() == ".webm":
        media_type = "video/webm"
    elif path.suffix.lower() == ".mov":
        media_type = "video/quicktime"

    return FileResponse(path, media_type=media_type, filename=path.name)
