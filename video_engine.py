import os
import uuid
from typing import List

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from video_engine import VideoEngine

app = FastAPI(title="ETERNA Backend")

STORAGE = "storage"
os.makedirs(STORAGE, exist_ok=True)

video_engine = VideoEngine()


@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ETERNA</title>
        <style>
            body {
                background: #0b0b0b;
                color: white;
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                text-align: center;
                padding: 20px;
            }
            .box {
                max-width: 700px;
            }
            h1 {
                font-size: 42px;
                margin-bottom: 10px;
            }
            p {
                font-size: 18px;
                color: #cccccc;
            }
            a {
                color: white;
            }
        </style>
    </head>
    <body>
        <div class="box">
            <h1>ETERNA backend activo</h1>
            <p>La API está funcionando.</p>
            <p>Prueba la documentación en <a href="/docs">/docs</a></p>
        </div>
    </body>
    </html>
    """


@app.post("/crear-eterna")
async def crear_eterna(
    nombre: str = Form(...),
    email: str = Form(...),
    telefono_regalante: str = Form(""),
    nombre_destinatario: str = Form(""),
    telefono_destinatario: str = Form(""),
    frase1: str = Form(...),
    frase2: str = Form(...),
    frase3: str = Form(...),
    fotos: List[UploadFile] = File(...)
):
    if len(fotos) < 1:
        raise HTTPException(status_code=400, detail="Debes subir al menos una foto")

    eterna_id = str(uuid.uuid4())
    folder = os.path.join(STORAGE, eterna_id)
    os.makedirs(folder, exist_ok=True)

    frases = [frase1, frase2, frase3]
    imagenes = []

    with open(os.path.join(folder, "datos.txt"), "w", encoding="utf-8") as f:
        f.write(f"nombre={nombre}\n")
        f.write(f"email={email}\n")
        f.write(f"telefono_regalante={telefono_regalante}\n")
        f.write(f"nombre_destinatario={nombre_destinatario}\n")
        f.write(f"telefono_destinatario={telefono_destinatario}\n")

    with open(os.path.join(folder, "frases.txt"), "w", encoding="utf-8") as f:
        for frase in frases:
            f.write(frase + "\n")

    for i, foto in enumerate(fotos, start=1):
        extension = os.path.splitext(foto.filename)[1].lower()
        if extension not in [".jpg", ".jpeg", ".png", ".webp"]:
            extension = ".jpg"

        ruta = os.path.join(folder, f"foto{i}{extension}")

        contenido = await foto.read()
        with open(ruta, "wb") as f:
            f.write(contenido)

        imagenes.append(ruta)

    video_path = os.path.join(folder, "video.mp4")

    try:
        video_engine.generar_video_eterna(
            imagenes=imagenes,
            frases=frases,
            output=video_path
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando vídeo: {str(e)}")

    if not os.path.exists(video_path):
        raise HTTPException(status_code=500, detail="El vídeo no se generó")

    return {
        "ok": True,
        "eterna_id": eterna_id,
        "nombre": nombre,
        "email": email,
        "telefono_regalante": telefono_regalante,
        "nombre_destinatario": nombre_destinatario,
        "telefono_destinatario": telefono_destinatario,
        "frases": frases,
        "total_fotos": len(imagenes),
        "video_url": f"/video/{eterna_id}",
        "preview_url": f"/preview/{eterna_id}",
        "message": "ETERNA creada correctamente"
    }


@app.get("/video/{eterna_id}")
def ver_video(eterna_id: str):
    video_path = os.path.join(STORAGE, eterna_id, "video.mp4")

    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Vídeo no encontrado")

    return FileResponse(video_path, media_type="video/mp4", filename="video.mp4")


@app.get("/preview/{eterna_id}", response_class=HTMLResponse)
def preview_video(eterna_id: str):
    video_path = os.path.join(STORAGE, eterna_id, "video.mp4")

    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Vídeo no encontrado")

    video_url = f"/video/{eterna_id}"

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Preview ETERNA</title>
        <style>
            body {{
                margin: 0;
                background: black;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                color: white;
                font-family: Arial, sans-serif;
                flex-direction: column;
                padding: 20px;
            }}
            video {{
                width: 100%;
                max-width: 420px;
                border-radius: 18px;
                box-shadow: 0 0 30px rgba(255,255,255,0.08);
            }}
            h1 {{
                margin-bottom: 20px;
                font-size: 24px;
            }}
        </style>
    </head>
    <body>
        <h1>Tu ETERNA</h1>
        <video controls autoplay playsinline>
            <source src="{video_url}" type="video/mp4">
            Tu navegador no soporta vídeo.
        </video>
    </body>
    </html>
    """
