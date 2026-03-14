from fastapi import FastAPI, UploadFile, File, Form
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

        contenido = await foto.read()

        ruta = os.path.join(folder, f"foto{i}.jpg")

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
        "numero_fotos": 6
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 10000))

    uvicorn.run(app, host="0.0.0.0", port=port)
