import os
import uuid
from pathlib import Path
from typing import List

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="ETERNA backend")

# =========================
# STORAGE
# =========================

BASE_DIR = Path(__file__).resolve().parent
STORAGE = BASE_DIR / "storage"

STORAGE.mkdir(exist_ok=True)

# Servir archivos (videos, imágenes)
app.mount("/media", StaticFiles(directory=str(STORAGE)), name="media")


# =========================
# HOME
# =========================

@app.get("/")
def home():
    return {"status": "ETERNA backend alive"}


# =========================
# CREAR ETERNA
# =========================

@app.post("/crear-eterna")
async def crear_eterna(
    customer_name: str = Form(...),
    customer_email: str = Form(...),
    frase1: str = Form(...),
    frase2: str = Form(...),
    frase3: str = Form(...),
    fotos: List[UploadFile] = File(...)
):

    eterna_id = str(uuid.uuid4())
    folder = STORAGE / eterna_id
    folder.mkdir(parents=True, exist_ok=True)

    # Guardar frases
    frases = [frase1, frase2, frase3]
    with open(folder / "frases.txt", "w", encoding="utf-8") as f:
        for frase in frases:
            f.write(frase + "\n")

    # Guardar imágenes
    saved_files = []

    for i, foto in enumerate(fotos):
        filename = f"foto{i+1}.jpg"
        file_path = folder / filename

        content = await foto.read()
        with open(file_path, "wb") as f:
            f.write(content)

        saved_files.append(filename)

    # ⚠️ Simulación de video (por ahora)
    video_path = folder / "video.mp4"

    # Crear archivo vacío de video (placeholder)
    with open(video_path, "wb") as f:
        f.write(b"")

    video_url = f"https://eterna-v2-lab.onrender.com/media/{eterna_id}/video.mp4"

    return {
        "status": "ok",
        "eterna_id": eterna_id,
        "fotos_recibidas": len(fotos),
        "fotos_guardadas": saved_files,
        "video_url": video_url,
        "link": f"https://eterna-test.carrd.co/?id={eterna_id}"
    }


# =========================
# OBTENER ETERNA (VIDEO)
# =========================

@app.get("/eterna/{eterna_id}")
def get_eterna(eterna_id: str):

    video_url = f"https://eterna-v2-lab.onrender.com/media/{eterna_id}/video.mp4"

    return {
        "video_url": video_url
    }
