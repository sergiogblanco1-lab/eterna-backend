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

```
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

lista_imagenes = os.path.join(folder, "imagenes.txt")

with open(lista_imagenes, "w") as f:
    for img in imagenes:
        f.write(f"file '{img}'\n")
        f.write("duration 3\n")

comando = [
    "ffmpeg",
    "-y",
    "-f", "concat",
    "-safe", "0",
    "-i", lista_imagenes,
    "-vf", "scale=1080:1920,format=yuv420p",
    "-pix_fmt", "yuv420p",
    video_path
]

subprocess.run(comando)

return {
    "ok": True,
    "eterna_id": eterna_id,
    "video": f"https://eterna-backend-0six.onrender.com/storage/{eterna_id}/video.mp4",
    "mensaje": "Tu ETERNA ha sido creada"
}
```
