from fastapi import FastAPI, UploadFile, File, Form
from typing import List
import os
import uuid
from pathlib import Path

from video_engine import generate_eterna_video

app = FastAPI()

STORAGE = "storage"
os.makedirs(STORAGE, exist_ok=True)


# ---------------------------------------------------------
# HOME
# ---------------------------------------------------------

@app.get("/")
def home():
    return {"status": "ETERNA backend alive"}


# ---------------------------------------------------------
# CREAR ETERNA
# ---------------------------------------------------------

@app.post("/crear-eterna")
async def crear_eterna(
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

    eterna_id = str(uuid.uuid4())

    folder = Path(STORAGE) / eterna_id
    folder.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------
    # GUARDAR FRASES
    # -----------------------------------------

    frases = [frase1.strip(), frase2.strip(), frase3.strip()]

    with open(folder / "frases.txt", "w", encoding="utf-8") as f:
        for frase in frases:
            f.write(frase + "\n")

    # -----------------------------------------
    # GUARDAR DATOS
    # -----------------------------------------

    with open(folder / "datos.txt", "w", encoding="utf-8") as f:
        f.write(f"nombre={nombre}\n")
        f.write(f"email={email}\n")

    # -----------------------------------------
    # GUARDAR FOTOS
    # -----------------------------------------

    fotos = [foto1, foto2, foto3, foto4, foto5, foto6]
    image_paths = []

    for i, foto in enumerate(fotos, start=1):

        extension = Path(foto.filename).suffix.lower()

        if extension not in [".jpg", ".jpeg", ".png", ".webp"]:
            extension = ".jpg"

        img_path = folder / f"foto_{i}{extension}"

        contenido = await foto.read()

        with open(img_path, "wb") as f:
            f.write(contenido)

        image_paths.append(str(img_path))

    # -----------------------------------------
    # GENERAR VIDEO
    # -----------------------------------------

    video_path = folder / "video.mp4"

    generate_eterna_video(
        image_paths=image_paths,
        frases=frases,
        output_path=str(video_path),
        music_path="assets/music.mp3",
        intro_text="Hay momentos que merecen quedarse para siempre",
        outro_text="ETERNA",
        end_message="Para siempre",
    )

    # -----------------------------------------
    # RESPUESTA
    # -----------------------------------------

    return {
        "ok": True,
        "eterna_id": eterna_id,
        "video": f"/storage/{eterna_id}/video.mp4"
    }
