from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from typing import List
import os
import uuid
import subprocess
import threading
import time

app = FastAPI()

STORAGE = "storage"
os.makedirs(STORAGE, exist_ok=True)


@app.get("/")
def home():
    return {"status": "ETERNA backend alive"}


def generar_video(folder, imagenes):

    lista = os.path.join(folder, "lista.txt")

    with open(lista, "w") as f:
        for img in imagenes:
            f.write(f"file '{img}'\n")
            f.write("duration 3\n")

    video = os.path.join(folder, "video.mp4")

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        lista,
        "-vf",
        "scale=720:1280",
        "-pix_fmt",
        "yuv420p",
        video
    ]

    subprocess.run(cmd)


@app.post("/crear-eterna")
async def crear_eterna(
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

        ruta = os.path.join(folder, f"{i}.jpg")

        with open(ruta, "wb") as f:
            f.write(contenido)

        imagenes.append(ruta)

    thread = threading.Thread(target=generar_video, args=(folder, imagenes))
    thread.start()

    return {"eterna_id": eterna_id}


@app.get("/estado/{eterna_id}")
def estado(eterna_id: str):

    video = os.path.join(STORAGE, eterna_id, "video.mp4")

    if os.path.exists(video):

        return {
            "status": "ready",
            "video": f"/ver/{eterna_id}"
        }

    return {"status": "processing"}


@app.get("/ver/{eterna_id}")
def ver(eterna_id: str):

    video = os.path.join(STORAGE, eterna_id, "video.mp4")

    return FileResponse(video, media_type="video/mp4")
