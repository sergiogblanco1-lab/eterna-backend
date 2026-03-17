import uuid
import traceback
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
    <html>
    <body style="background:black;color:white;text-align:center;padding-top:100px;">
    <h1>ETERNA</h1>
    <p>Backend funcionando</p>
    </body>
    </html>
    """


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
    try:
        eterna_id = str(uuid.uuid4())
        folder = STORAGE_DIR / eterna_id
        folder.mkdir(parents=True, exist_ok=True)

        rutas = []

        for i, foto in enumerate(fotos):
            ruta = folder / f"foto_{i}.jpg"
            with open(ruta, "wb") as f:
                f.write(await foto.read())
            rutas.append(str(ruta))

        salida = str(folder / "video.mp4")

        video_engine.generar_video(
            imagenes=rutas,
            salida=salida
        )

        return {
            "ok": True,
            "video_url": f"/video/{eterna_id}"
        }

    except Exception:
        raise HTTPException(status_code=500, detail=traceback.format_exc())


@app.get("/video/{eterna_id}")
def ver_video(eterna_id: str):
    ruta = STORAGE_DIR / eterna_id / "video.mp4"
    if not ruta.exists():
        raise HTTPException(status_code=404, detail="No encontrado")
    return FileResponse(str(ruta), media_type="video/mp4")
