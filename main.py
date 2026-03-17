import uuid
from pathlib import Path
from typing import List

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from video_engine import VideoEngine

app = FastAPI(title="ETERNA backend limpio")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

video_engine = VideoEngine()


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
            body{
                margin:0;
                background:#0b0b0b;
                color:white;
                font-family:Arial, sans-serif;
                display:flex;
                align-items:center;
                justify-content:center;
                min-height:100vh;
                text-align:center;
                padding:20px;
            }
            h1{font-size:56px;margin:0 0 16px 0;}
            p{font-size:20px;opacity:.9;margin:8px 0;}
        </style>
    </head>
    <body>
        <div>
            <h1>ETERNA</h1>
            <p>Backend online funcionando.</p>
            <p>Este servicio recibe fotos y crea el vídeo emocional.</p>
            <p>Prueba el endpoint POST /crear-eterna</p>
        </div>
    </body>
    </html>
    """


@app.post("/crear-eterna")
async def crear_eterna(
    nombre: str = Form(...),
    email: str = Form(...),
    telefono_regalante: str = Form(...),
    nombre_destinatario: str = Form(...),
    telefono_destinatario: str = Form(...),
    frase1: str = Form(...),
    frase2: str = Form(...),
    frase3: str = Form(...),
    fotos: List[UploadFile] = File(...),
):
    if len(fotos) < 1:
        raise HTTPException(status_code=400, detail="Debes subir al menos 1 foto")

    eterna_id = str(uuid.uuid4())
    carpeta = STORAGE_DIR / eterna_id
    carpeta.mkdir(parents=True, exist_ok=True)

    rutas_imagenes = []

    for i, foto in enumerate(fotos):
        extension = Path(foto.filename).suffix.lower() or ".jpg"
        ruta = carpeta / f"foto_{i}{extension}"
        contenido = await foto.read()
        with open(ruta, "wb") as f:
            f.write(contenido)
        rutas_imagenes.append(str(ruta))

    salida_video = carpeta / "video.mp4"

    try:
        video_engine.generar_video(
            imagenes=rutas_imagenes,
            salida=str(salida_video),
            frases=[frase1, frase2, frase3],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando vídeo: {str(e)}")

    return {
        "ok": True,
        "eterna_id": eterna_id,
        "nombre": nombre,
        "email": email,
        "telefono_regalante": telefono_regalante,
        "nombre_destinatario": nombre_destinatario,
        "telefono_destinatario": telefono_destinatario,
        "frases": [frase1, frase2, frase3],
        "total_fotos": len(rutas_imagenes),
        "video_url": f"/video/{eterna_id}",
        "preview_url": f"/preview/{eterna_id}",
        "message": "ETERNA creada correctamente",
    }


@app.get("/video/{eterna_id}")
def ver_video(eterna_id: str):
    ruta = STORAGE_DIR / eterna_id / "video.mp4"
    if not ruta.exists():
        raise HTTPException(status_code=404, detail="Vídeo no encontrado.")
    return FileResponse(
        path=str(ruta),
        media_type="video/mp4",
        filename=f"{eterna_id}.mp4",
    )


@app.get("/preview/{eterna_id}", response_class=HTMLResponse)
def preview_video(eterna_id: str):
    ruta = STORAGE_DIR / eterna_id / "video.mp4"
    if not ruta.exists():
        raise HTTPException(status_code=404, detail="Vídeo no encontrado.")

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Preview ETERNA</title>
        <style>
            body {{
                margin: 0;
                background: #000;
                color: white;
                font-family: Arial, sans-serif;
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                flex-direction: column;
                gap: 20px;
                padding: 20px;
            }}
            video {{
                width: 100%;
                max-width: 420px;
                border-radius: 16px;
                box-shadow: 0 0 30px rgba(255,255,255,.12);
            }}
            a {{
                color: white;
                text-decoration: none;
                border: 1px solid rgba(255,255,255,.25);
                padding: 12px 18px;
                border-radius: 10px;
            }}
        </style>
    </head>
    <body>
        <h1>ETERNA</h1>
        <video controls autoplay playsinline>
            <source src="/video/{eterna_id}" type="video/mp4">
        </video>
        <a href="/video/{eterna_id}" download>Descargar vídeo</a>
    </body>
    </html>
    """
