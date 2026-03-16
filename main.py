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

    eterna_id = str(uuid.uuid4())
    folder = os.path.join(STORAGE, eterna_id)

    os.makedirs(folder, exist_ok=True)

    frases = [frase1, frase2, frase3]

    with open(os.path.join(folder, "frases.txt"), "w") as f:
        for frase in frases:
            f.write(frase + "\n")

    imagenes = []

    for i, foto in enumerate(fotos):

        contenido = await foto.read()

        ruta = os.path.join(folder, f"foto{i}.jpg")

        with open(ruta, "wb") as f:
            f.write(contenido)

        imagenes.append(ruta)

    video_path = os.path.join(folder, "video.mp4")

    generar_video(imagenes, video_path)

    return {
        "status": "eterna creada",
        "eterna_id": eterna_id,
        "video": video_path
    }


def generar_video(imagenes, salida):

    lista_archivo = "lista.txt"

    with open(lista_archivo, "w") as f:
        for img in imagenes:
            f.write(f"file '{img}'\n")
            f.write("duration 2\n")

    comando = [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", lista_archivo,
        "-vsync", "vfr",
        "-pix_fmt", "yuv420p",
        salida
    ]

    subprocess.run(comando)
