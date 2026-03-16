from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uuid
from pathlib import Path

from video_engine import generate_eterna_video

app = FastAPI(title="ETERNA Backend")

BASE_DIR = Path(__file__).resolve().parent
STORAGE = BASE_DIR / "storage"
ASSETS = BASE_DIR / "assets"

STORAGE.mkdir(exist_ok=True)
ASSETS.mkdir(exist_ok=True)

app.mount("/storage", StaticFiles(directory=str(STORAGE)), name="storage")


# =========================================================
# HOME
# =========================================================

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>ETERNA</title>
        <style>
            * { box-sizing: border-box; }
            body {
                margin: 0;
                font-family: Arial, sans-serif;
                background: #0b0b0f;
                color: white;
                padding: 24px;
            }
            .wrap {
                max-width: 680px;
                margin: 0 auto;
            }
            h1 {
                font-size: 42px;
                margin-bottom: 6px;
                letter-spacing: 2px;
            }
            p {
                color: #cfcfd6;
                line-height: 1.5;
            }
            .card {
                background: #15151c;
                border: 1px solid #2a2a34;
                border-radius: 18px;
                padding: 22px;
                margin-top: 22px;
            }
            label {
                display: block;
                margin-top: 16px;
                margin-bottom: 8px;
                font-weight: bold;
            }
            input, button {
                width: 100%;
                padding: 14px;
                border-radius: 12px;
                border: 1px solid #30303a;
                background: #101016;
                color: white;
                font-size: 16px;
            }
            input[type="file"] {
                padding: 10px;
                background: #101016;
            }
            button {
                margin-top: 22px;
                background: white;
                color: black;
                font-weight: bold;
                cursor: pointer;
            }
            button:hover {
                opacity: 0.92;
            }
            .mini {
                font-size: 14px;
                color: #9b9baa;
                margin-top: 10px;
            }
            .footer {
                margin-top: 28px;
                color: #8b8b97;
                font-size: 14px;
                text-align: center;
            }
        </style>
    </head>
    <body>
        <div class="wrap">
            <h1>ETERNA</h1>
            <p>Convierte 6 fotos y 3 frases en un recuerdo emocional.</p>

            <div class="card">
                <form action="/crear-eterna-web" method="post" enctype="multipart/form-data">
                    <label>Nombre</label>
                    <input type="text" name="nombre" required>

                    <label>Email</label>
                    <input type="email" name="email" required>

                    <label>Frase 1</label>
                    <input type="text" name="frase1" required>

                    <label>Frase 2</label>
                    <input type="text" name="frase2" required>

                    <label>Frase 3</label>
                    <input type="text" name="frase3" required>

                    <label>Foto 1</label>
                    <input type="file" name="foto1" accept=".jpg,.jpeg,.png,.webp" required>

                    <label>Foto 2</label>
                    <input type="file" name="foto2" accept=".jpg,.jpeg,.png,.webp" required>

                    <label>Foto 3</label>
                    <input type="file" name="foto3" accept=".jpg,.jpeg,.png,.webp" required>

                    <label>Foto 4</label>
                    <input type="file" name="foto4" accept=".jpg,.jpeg,.png,.webp" required>

                    <label>Foto 5</label>
                    <input type="file" name="foto5" accept=".jpg,.jpeg,.png,.webp" required>

                    <label>Foto 6</label>
                    <input type="file" name="foto6" accept=".jpg,.jpeg,.png,.webp" required>

                    <button type="submit">Crear mi ETERNA</button>
                    <div class="mini">Usa fotos JPG si puedes. Irán más rápido.</div>
                </form>
            </div>

            <div class="footer">
                Hay momentos que merecen quedarse para siempre.
            </div>
        </div>
    </body>
    </html>
    """


@app.get("/healthz")
def healthz():
    return {"ok": True}


# =========================================================
# GENERACIÓN EN SEGUNDO PLANO
# =========================================================

def generar_video_background(folder_str: str, frases: list[str]) -> None:
    folder = Path(folder_str)
    image_paths = []

    for path in sorted(folder.glob("foto_*")):
        image_paths.append(str(path))

    video_path = folder / "video.mp4"
    music_path = str(ASSETS / "music.mp3")
    status_path = folder / "status.txt"

    try:
        status_path.write_text("processing", encoding="utf-8")

        generate_eterna_video(
            image_paths=image_paths,
            frases=frases,
            output_path=str(video_path),
            music_path=music_path if Path(music_path).exists() else None,
            intro_text="Hay momentos que merecen quedarse para siempre",
            outro_text="ETERNA",
            end_message="Para siempre",
        )

        status_path.write_text("done", encoding="utf-8")

    except Exception as e:
        status_path.write_text("error", encoding="utf-8")
        (folder / "error.txt").write_text(str(e), encoding="utf-8")


# =========================================================
# PROCESAR FORMULARIO
# =========================================================

async def guardar_eterna(
    nombre,
    email,
    frase1,
    frase2,
    frase3,
    foto1,
    foto2,
    foto3,
    foto4,
    foto5,
    foto6,
):
    eterna_id = str(uuid.uuid4())
    folder = STORAGE / eterna_id
    folder.mkdir(parents=True, exist_ok=True)

    frases = [frase1.strip(), frase2.strip(), frase3.strip()]

    (folder / "status.txt").write_text("queued", encoding="utf-8")

    with open(folder / "frases.txt", "w", encoding="utf-8") as f:
        for frase in frases:
            f.write(frase + "\\n")

    with open(folder / "datos.txt", "w", encoding="utf-8") as f:
        f.write(f"nombre={nombre}\\n")
        f.write(f"email={email}\\n")

    fotos = [foto1, foto2, foto3, foto4, foto5, foto6]

    for i, foto in enumerate(fotos, start=1):
        extension = Path(foto.filename).suffix.lower() if foto.filename else ".jpg"
        if extension not in [".jpg", ".jpeg", ".png", ".webp"]:
            extension = ".jpg"

        img_path = folder / f"foto_{i}{extension}"

        contenido = await foto.read()
        if not contenido:
            raise HTTPException(status_code=400, detail=f"La foto {i} está vacía.")

        with open(img_path, "wb") as f:
            f.write(contenido)

    return eterna_id, folder, frases


# =========================================================
# API
# =========================================================

@app.post("/crear-eterna")
async def crear_eterna_api(
    background_tasks: BackgroundTasks,
    nombre: str = Form(...),
    email: str = Form(...),
    frase1: str = Form(...),
    frase2: str = Form(...),
    frase3: str = Form(...),
    foto1: UploadFile = File(...),
    foto2: UploadFile = File(...),
    foto3: UploadFile = File(...),
    foto4: UploadFile = File(...),
    foto5: UploadFile = File(...),
    foto6: UploadFile = File(...),
):
    eterna_id, folder, frases = await guardar_eterna(
        nombre, email, frase1, frase2, frase3,
        foto1, foto2, foto3, foto4, foto5, foto6
    )

    background_tasks.add_task(
        generar_video_background,
        str(folder),
        frases,
    )

    return JSONResponse({
        "ok": True,
        "eterna_id": eterna_id,
        "status": "queued",
        "check_url": f"/estado/{eterna_id}",
        "video_url": f"/storage/{eterna_id}/video.mp4"
    })


# =========================================================
# WEB
# =========================================================

@app.post("/crear-eterna-web", response_class=HTMLResponse)
async def crear_eterna_web(
    background_tasks: BackgroundTasks,
    nombre: str = Form(...),
    email: str = Form(...),
    frase1: str = Form(...),
    frase2: str = Form(...),
    frase3: str = Form(...),
    foto1: UploadFile = File(...),
    foto2: UploadFile = File(...),
    foto3: UploadFile = File(...),
    foto4: UploadFile = File(...),
    foto5: UploadFile = File(...),
    foto6: UploadFile = File(...),
):
    eterna_id, folder, frases = await guardar_eterna(
        nombre, email, frase1, frase2, frase3,
        foto1, foto2, foto3, foto4, foto5, foto6
    )

    background_tasks.add_task(
        generar_video_background,
        str(folder),
        frases,
    )

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Preparando tu ETERNA</title>
        <style>
            body {{
                margin: 0;
                font-family: Arial, sans-serif;
                background: #000;
                color: white;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }}
            .wrap {{
                max-width: 420px;
                width: 100%;
                text-align: center;
            }}
            h1 {{
                font-size: 30px;
                margin-bottom: 10px;
            }}
            p {{
                color: #cfcfd6;
            }}
            .spinner {{
                width: 34px;
                height: 34px;
                border: 4px solid #333;
                border-top: 4px solid #fff;
                border-radius: 50%;
                margin: 24px auto;
                animation: spin 1s linear infinite;
            }}
            @keyframes spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
            }}
            .box {{
                background: #121218;
                border: 1px solid #2b2b38;
                border-radius: 18px;
                padding: 24px;
            }}
            .small {{
                color: #9ea0ad;
                font-size: 14px;
                margin-top: 14px;
            }}
            a {{
                color: white;
            }}
        </style>
    </head>
    <body>
        <div class="wrap">
            <div class="box">
                <h1>Estamos creando tu ETERNA...</h1>
                <p>Esto puede tardar un poco. Cuando esté lista aparecerá automáticamente.</p>
                <div class="spinner"></div>
                <div class="small">No cierres esta página.</div>
            </div>
        </div>

        <script>
            const eternaId = "{eterna_id}";
            const estadoUrl = "/estado/" + eternaId;
            const videoUrl = "/ver/" + eternaId;

            async function revisarEstado() {{
                try {{
                    const res = await fetch(estadoUrl);
                    const data = await res.json();

                    if (data.status === "done") {{
                        window.location.href = videoUrl;
                        return;
                    }}

                    if (data.status === "error") {{
                        document.body.innerHTML = `
                            <div style="font-family:Arial;background:#000;color:white;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px;">
                                <div style="max-width:420px;width:100%;text-align:center;background:#121218;border:1px solid #2b2b38;border-radius:18px;padding:24px;">
                                    <h1>Error al crear la ETERNA</h1>
                                    <p>Ha ocurrido un problema generando el vídeo.</p>
                                    <p><a href="/">Volver</a></p>
                                </div>
                            </div>
                        `;
                        return;
                    }}

                    setTimeout(revisarEstado, 3000);
                }} catch (e) {{
                    setTimeout(revisarEstado, 3000);
                }}
            }}

            setTimeout(revisarEstado, 3000);
        </script>
    </body>
    </html>
    """


# =========================================================
# ESTADO
# =========================================================

@app.get("/estado/{eterna_id}")
def estado_eterna(eterna_id: str):
    folder = STORAGE / eterna_id
    status_path = folder / "status.txt"
    error_path = folder / "error.txt"
    video_path = folder / "video.mp4"

    if not folder.exists():
        raise HTTPException(status_code=404, detail="ETERNA no encontrada")

    status = "queued"
    if status_path.exists():
        status = status_path.read_text(encoding="utf-8").strip()

    response = {
        "eterna_id": eterna_id,
        "status": status,
        "video_url": f"/storage/{eterna_id}/video.mp4" if video_path.exists() else None
    }

    if error_path.exists():
        response["error"] = error_path.read_text(encoding="utf-8")

    return response


# =========================================================
# VER VIDEO
# =========================================================

@app.get("/ver/{eterna_id}", response_class=HTMLResponse)
def ver_eterna(eterna_id: str):
    video_url = f"/storage/{eterna_id}/video.mp4"

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Tu ETERNA</title>
        <style>
            body {{
                margin: 0;
                font-family: Arial, sans-serif;
                background: #000;
                color: white;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                padding: 20px;
            }}
            .wrap {{
                max-width: 420px;
                width: 100%;
                text-align: center;
            }}
            h1 {{
                font-size: 32px;
                margin-bottom: 8px;
            }}
            p {{
                color: #cfcfd6;
                margin-bottom: 22px;
            }}
            video {{
                width: 100%;
                border-radius: 18px;
                background: black;
                box-shadow: 0 0 30px rgba(255,255,255,0.08);
            }}
            a {{
                color: white;
            }}
        </style>
    </head>
    <body>
        <div class="wrap">
            <h1>Tu ETERNA está lista</h1>
            <p>Hay momentos que merecen quedarse para siempre.</p>
            <video controls autoplay playsinline>
                <source src="{video_url}" type="video/mp4">
            </video>
            <p style="margin-top:18px;">
                <a href="{video_url}" target="_blank">Abrir vídeo directamente</a>
            </p>
        </div>
    </body>
    </html>
    """
