import uuid
import traceback
from pathlib import Path
from typing import List

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from video_engine_v2 import VideoEngine


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


@app.get("/")
def home():
    return {"status": "ETERNA backend activo"}


@app.post("/crear-eterna")
async def crear_eterna(
    nombre: str = Form(...),
    email: str = Form(...),
    frase1: str = Form(...),
    frase2: str = Form(...),
    frase3: str = Form(...),
    fotos: List[UploadFile] = File(...)
):
    try:
        eterna_id = str(uuid.uuid4())
        carpeta = STORAGE_DIR / eterna_id
        carpeta.mkdir(parents=True, exist_ok=True)

        frases = [frase1, frase2, frase3]

        # Guardar imágenes
        rutas_imagenes = []
        for i, foto in enumerate(fotos):
            contenido = await foto.read()
            ruta = carpeta / f"img_{i}.jpg"
            with open(ruta, "wb") as f:
                f.write(contenido)
            rutas_imagenes.append(str(ruta))

        # Ruta de salida
        salida_video = carpeta / "video.mp4"

        # Generar vídeo
        video_engine.generar_video(
            imagenes=rutas_imagenes,
            salida=str(salida_video),
            frases=frases
        )

        return {
            "ok": True,
            "eterna_id": eterna_id,
            "video_url": f"/video/{eterna_id}"
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/video/{eterna_id}")
def obtener_video(eterna_id: str):
    ruta = STORAGE_DIR / eterna_id / "video.mp4"

    if not ruta.exists():
        raise HTTPException(status_code=404, detail="Video no encontrado")

    return JSONResponse({
        "video_path": str(ruta)
    })
