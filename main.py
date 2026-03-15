from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.staticfiles import StaticFiles
import os
import uuid
import subprocess

app = FastAPI()

# Carpeta donde se guardan las eternas
STORAGE = "storage"

# Crear la carpeta si no existe (IMPORTANTE)
os.makedirs(STORAGE, exist_ok=True)

# Permitir acceso a archivos desde internet
app.mount("/storage", StaticFiles(directory=STORAGE), name="storage")


@app.get("/")
def home():
    return {"status": "ETERNA backend alive"}


@app.post("/crear-eterna")
async def crear_eterna(
    request: Request,
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
    foto6: UploadFile = File(...)
):

    eterna_id = str(uuid.uuid4())
    folder = os.path.join(STORAGE, eterna_id)

    os.makedirs(folder, exist_ok=True)

    frases = [frase1, frase2, frase3]

    with open(os.path.join(folder, "frases.txt"), "w") as f:
        for frase in frases:
            f.write(frase + "\n")

    fotos = [foto1, foto2, foto3, foto4, foto5, foto6]
    imagenes = []

    for i, foto in enumerate(fotos, start=1):

        extension = os.path.splitext(foto.filename)[1]
        if extension == "":
            extension = ".jpg"

        nombre_archivo = f"foto{i}{extension}"
        ruta = os.path.join(folder, nombre_archivo)

        contenido = await foto.read()

        with open(ruta, "wb") as f:
            f.write(contenido)

        imagenes.append(ruta)

    # Crear lista para ffmpeg
    lista_path = os.path.join(folder, "lista.txt")

    with open(lista_path, "w") as f:
        for imagen in imagenes:
            f.write(f"file '{os.path.abspath(imagen)}'\n")
            f.write("duration 2\n")

        f.write(f"file '{os.path.abspath(imagenes[-1])}'\n")

    video_path = os.path.join(folder, "video.mp4")

    comando = [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", lista_path,
        "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2",
        "-pix_fmt", "yuv420p",
        "-r", "25",
        video_path
    ]

    subprocess.run(comando)

    base_url = str(request.base_url).rstrip("/")

    video_url = f"{base_url}/storage/{eterna_id}/video.mp4"

    return {
        "ok": True,
        "eterna_id": eterna_id,
        "video": video_url,
        "mensaje": "Tu ETERNA ha sido creada",
        "numero_fotos": len(imagenes)
    }
