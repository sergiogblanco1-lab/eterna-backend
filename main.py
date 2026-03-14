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

    for foto in fotos:
        contenido = await foto.read()
        ruta = os.path.join(folder, foto.filename)

        with open(ruta, "wb") as f:
            f.write(contenido)

        imagenes.append(ruta)

    lista_path = os.path.join(folder, "lista.txt")

    with open(lista_path, "w") as f:
        for img in imagenes:
            f.write(f"file '{img}'\n")
            f.write("duration 2\n")

    video_path = os.path.join(folder, "video.mp4")

    subprocess.run([
        "ffmpeg",
        "-f", "concat",
        "-safe", "0",
        "-i", lista_path,
        "-vsync", "vfr",
        "-pix_fmt", "yuv420p",
        video_path
    ])

    return {
        "ok": True,
        "eterna_id": eterna_id,
        "video": video_path,
        "message": "Tu ETERNA ha sido creada",
        "numero_fotos": len(fotos)
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
