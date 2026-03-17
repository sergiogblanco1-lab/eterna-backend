import uuid
from pathlib import Path
from typing import List, Annotated

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse

from video_engine import VideoEngine


app = FastAPI(title="ETERNA backend")

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
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ETERNA</title>
        <style>
            body {
                margin: 0;
                background: #0b0b0b;
                color: white;
                font-family: Arial, sans-serif;
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                text-align: center;
                padding: 24px;
            }
            .box {
                max-width: 760px;
            }
            h1 {
                font-size: 42px;
                margin-bottom: 10px;
                letter-spacing: 2px;
            }
            p {
                opacity: 0.88;
                font-size: 18px;
                line-height: 1.6;
            }
            .small {
                margin-top: 18px;
                font-size: 14px;
                opacity: 0.65;
            }
        </style>
    </head>
    <body>
        <div class="box">
            <h1>ETERNA</h1>
            <p>Backend online funcionando.</p>
            <p>Este servicio recibe fotos y frases, crea la ETERNA y genera el vídeo emocional.</p>
            <p class="small">Prueba el endpoint POST /crear-eterna</p>
        </div>
    </body>
    </html>
    """


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/crear-eterna")
async def crear_eterna(
    nombre: Annotated[str, Form(...)],
    email: Annotated[str, Form(...)],
    telefono_regalante: Annotated[str, Form(...)],
    nombre_destinatario: Annotated[str, Form(...)],
    telefono_destinatario: Annotated[str, Form(...)],
    frase1: Annotated[str, Form(...)],
    frase2: Annotated[str, Form(...)],
    frase3: Annotated[str, Form(...)],
    fotos: Annotated[List[UploadFile], File(...)],
):
    if len(fotos) < 2:
        raise HTTPException(status_code=400, detail="Debes subir al menos 2 fotos.")

    eterna_id = str(uuid.uuid4())
    folder = STORAGE_DIR / eterna_id
    folder.mkdir(parents=True, exist_ok=True)

    frases = [frase1, frase2, frase3]

    try:
        rutas_imagenes = []

        for idx, foto in enumerate(fotos):
            extension = Path(foto.filename or "").suffix.lower()
            if extension not in [".jpg", ".jpeg", ".png", ".webp"]:
                extension = ".jpg"

            ruta = folder / f"foto_{idx + 1}{extension}"

            contenido = await foto.read()
            if not contenido:
                raise HTTPException(status_code=400, detail=f"La foto {idx + 1} está vacía.")

            with open(ruta, "wb") as f:
                f.write(contenido)

            rutas_imagenes.append(str(ruta))

        with open(folder / "frases.txt", "w", encoding="utf-8") as f:
            for frase in frases:
                f.write((frase or "").strip() + "\n")

        with open(folder / "datos.txt", "w", encoding="utf-8") as f:
            f.write(f"nombre: {nombre}\n")
            f.write(f"email: {email}\n")
            f.write(f"telefono_regalante: {telefono_regalante}\n")
            f.write(f"nombre_destinatario: {nombre_destinatario}\n")
            f.write(f"telefono_destinatario: {telefono_destinatario}\n")

        ruta_video = str(folder / "video.mp4")

        video_engine.generar_video(
            imagenes=rutas_imagenes,
            salida=ruta_video,
            frases=frases,
            music_path=None,
            image_duration=5.5,
            transition_duration=1.0,
            width=720,
            height=1280,
            fps=30,
        )

        return JSONResponse(
            {
                "ok": True,
                "eterna_id": eterna_id,
                "nombre": nombre,
                "email": email,
                "telefono_regalante": telefono_regalante,
                "nombre_destinatario": nombre_destinatario,
                "telefono_destinatario": telefono_destinatario,
                "frases": frases,
                "total_fotos": len(rutas_imagenes),
                "video_url": f"/video/{eterna_id}",
                "preview_url": f"/preview/{eterna_id}",
                "message": "ETERNA creada correctamente",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/video/{eterna_id}")
def ver_video(eterna_id: str):
    ruta = STORAGE_DIR / eterna_id / "video.mp4"
    if not ruta.exists():
        raise HTTPException(status_code=404, detail="Vídeo no encontrado.")
    return FileResponse(str(ruta), media_type="video/mp4", filename="video.mp4")


@app.get("/preview/{eterna_id}", response_class=HTMLResponse)
def preview_video(eterna_id: str):
    ruta = STORAGE_DIR / eterna_id / "video.mp4"
    if not ruta.exists():
        raise HTTPException(status_code=404, detail="Vídeo no encontrado.")

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
                background: #000;
                color: white;
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
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
                font-size: 22px;
                letter-spacing: 1px;
            }}
        </style>
    </head>
    <body>
        <h1>Tu ETERNA</h1>
        <video controls autoplay playsinline>
            <source src="/video/{eterna_id}" type="video/mp4">
            Tu navegador no puede reproducir este vídeo.
        </video>
    </body>
    </html>
    """
