import os
import uuid
import subprocess
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles


app = FastAPI(title="ETERNA backend")

BASE_DIR = Path(__file__).resolve().parent
STORAGE = BASE_DIR / "media"
STORAGE.mkdir(parents=True, exist_ok=True)

app.mount("/media", StaticFiles(directory=str(STORAGE)), name="media")


@app.get("/")
def home():
    return {"status": "ETERNA backend activo"}


@app.post("/crear-eterna")
async def crear_eterna(request: Request):
    try:
        form = await request.form()

        eterna_id = str(uuid.uuid4())
        carpeta = STORAGE / eterna_id
        carpeta.mkdir(parents=True, exist_ok=True)

        datos = {}
        fotos_guardadas = []

        for key, value in form.multi_items():
            if hasattr(value, "filename") and value.filename:
                contenido = await value.read()
                content_type = getattr(value, "content_type", "") or ""

                if content_type.startswith("image/"):
                    nombre_archivo = f"foto{len(fotos_guardadas) + 1}.jpg"
                    ruta_archivo = carpeta / nombre_archivo

                    with open(ruta_archivo, "wb") as f:
                        f.write(contenido)

                    fotos_guardadas.append(str(ruta_archivo))
            else:
                datos[key] = str(value)

        if len(fotos_guardadas) == 0:
            return JSONResponse(
                status_code=400,
                content={"detail": "No se recibieron fotos."}
            )

        data_path = carpeta / "data.txt"
        with open(data_path, "w", encoding="utf-8") as f:
            for k, v in datos.items():
                f.write(f"{k}: {v}\n")

        video_path = carpeta / "video.mp4"

        cmd = [
            "ffmpeg",
            "-f", "lavfi",
            "-i", "color=c=black:s=720x1280:d=5",
            "-vf",
            "drawtext=text='ETERNA':fontcolor=white:fontsize=60:x=(w-text_w)/2:y=(h-text_h)/2",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-y",
            str(video_path)
        ]

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        print("=== FFMPEG STDOUT ===")
        print(result.stdout)
        print("=== FFMPEG STDERR ===")
        print(result.stderr)

        if result.returncode != 0:
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Error generando video",
                    "detalle": result.stderr
                }
            )

        if not video_path.exists():
            return JSONResponse(
                status_code=500,
                content={"error": "video no generado"}
            )

        video_url = f"{request.base_url}media/{eterna_id}/video.mp4"

        return JSONResponse({
            "status": "ok",
            "eterna_id": eterna_id,
            "fotos": len(fotos_guardadas),
            "video_url": video_url
        })

    except Exception as e:
        print("=== ERROR GENERAL ===")
        print(str(e))
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )
