from fastapi import FastAPI, UploadFile, File, Form
from typing import List
import os
import uuid
import subprocess

app = FastAPI()

STORAGE = "storage"
os.makedirs(STORAGE, exist_ok=True)


@app.get("/")
def home():
    return {"status": "ETERNA backend alive"}


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
        folder = os.path.join(STORAGE, eterna_id)
        os.makedirs(folder, exist_ok=True)

        # Guardar frases
        frases = [frase1, frase2, frase3]
        with open(os.path.join(folder, "frases.txt"), "w") as f:
            for frase in frases:
                f.write(frase + "\n")

        # Guardar imágenes
        imagenes = []
        for i, foto in enumerate(fotos):
            contenido = await foto.read()
            ruta = os.path.join(folder, f"img_{i}.jpg")
            with open(ruta, "wb") as f:
                f.write(contenido)
            imagenes.append(ruta)

        # Crear lista para ffmpeg
        lista_path = os.path.join(folder, "lista.txt")
        with open(lista_path, "w") as f:
            for img in imagenes:
                f.write(f"file '{img}'\n")
                f.write("duration 3\n")

        output_video = os.path.join(folder, "video.mp4")

        # Generar vídeo
        subprocess.run([
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", lista_path,
            "-vf", "scale=720:1280,format=yuv420p",
            "-r", "30",
            output_video
        ])

        return {
            "status": "ok",
            "eterna_id": eterna_id,
            "video_url": f"/media/{eterna_id}/video.mp4"
        }

    except Exception as e:
        return {"error": str(e)}
