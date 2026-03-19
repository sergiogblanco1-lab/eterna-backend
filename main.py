import os
import uuid
from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

STORAGE = "media"
os.makedirs(STORAGE, exist_ok=True)

app.mount("/media", StaticFiles(directory=STORAGE), name="media")


@app.get("/")
def home():
    return {"status": "ETERNA backend activo"}


@app.post("/crear-eterna")
async def crear_eterna(request: Request):

    form = await request.form()

    eterna_id = str(uuid.uuid4())
    carpeta = os.path.join(STORAGE, eterna_id)
    os.makedirs(carpeta, exist_ok=True)

    # =====================
    # DATOS
    # =====================
    datos = {}
    fotos = []

    for key in form:
        value = form[key]

        # detectar fotos automáticamente
        if hasattr(value, "filename"):
            contenido = await value.read()
            ruta = os.path.join(carpeta, value.filename)

            with open(ruta, "wb") as f:
                f.write(contenido)

            fotos.append(ruta)

        else:
            datos[key] = value

    if len(fotos) == 0:
        return JSONResponse({"detail": "No se recibieron fotos"}, status_code=400)

    # =====================
    # GUARDAR DATOS
    # =====================
    with open(os.path.join(carpeta, "data.txt"), "w") as f:
        for k, v in datos.items():
            f.write(f"{k}: {v}\n")

    # =====================
    # VIDEO PLACEHOLDER
    # =====================
    video_path = os.path.join(carpeta, "video.mp4")

    os.system(
        f'ffmpeg -f lavfi -i color=c=black:s=720x1280:d=5 '
        f'-vf "drawtext=text=\'ETERNA\':fontcolor=white:fontsize=60:x=(w-text_w)/2:y=(h-text_h)/2" '
        f'-y {video_path}'
    )

    video_url = f"https://eterna-v2-lab.onrender.com/media/{eterna_id}/video.mp4"

    return {
        "status": "ok",
        "eterna_id": eterna_id,
        "fotos": len(fotos),
        "video_url": video_url
    }
