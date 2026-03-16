from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os
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


@app.post("/crear-eterna")
async def crear_eterna_api(
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
    return await _procesar_eterna(
        nombre, email, frase1, frase2, frase3,
        foto1, foto2, foto3, foto4, foto5, foto6,
        devolver_html=False,
    )


@app.post("/crear-eterna-web", response_class=HTMLResponse)
async def crear_eterna_web(
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
    return await _procesar_eterna(
        nombre, email, frase1, frase2, frase3,
        foto1, foto2, foto3, foto4, foto5, foto6,
        devolver_html=True,
    )


async def _procesar_eterna(
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
    devolver_html=False,
):
    eterna_id = str(uuid.uuid4())
    folder = STORAGE / eterna_id
    folder.mkdir(parents=True, exist_ok=True)

    frases = [frase1.strip(), frase2.strip(), frase3.strip()]

    with open(folder / "frases.txt", "w", encoding="utf-8") as f:
        for frase in frases:
            f.write(frase + "\\n")

    with open(folder / "datos.txt", "w", encoding="utf-8") as f:
        f.write(f"nombre={nombre}\\n")
        f.write(f"email={email}\\n")

    fotos = [foto1, foto2, foto3, foto4, foto5, foto6]
    image_paths = []

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

        image_paths.append(str(img_path))

    video_path = folder / "video.mp4"
    music_path = str(ASSETS / "music.mp3")

    try:
        generate_eterna_video(
            image_paths=image_paths,
            frases=frases,
            output_path=str(video_path),
            music_path=music_path,
            intro_text="Hay momentos que merecen quedarse para siempre",
            outro_text="ETERNA",
            end_message="Para siempre",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se pudo generar el vídeo: {str(e)}")

    video_url = f"/storage/{eterna_id}/video.mp4"

    if not devolver_html:
        return {
            "ok": True,
            "eterna_id": eterna_id,
            "video": video_url,
        }

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
