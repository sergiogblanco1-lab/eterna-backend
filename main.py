from fastapi import FastAPI, Request, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import uuid
import os
from pathlib import Path
from typing import List

from video_engine import VideoEngine


# 🔥 ESTO ES LO QUE RENDER NECESITA
app = FastAPI()

# =========================
# CONFIG
# =========================
BASE_DIR = Path(__file__).resolve().parent
STORAGE = BASE_DIR / "storage"
STORAGE.mkdir(parents=True, exist_ok=True)

# SERVIR MEDIA
app.mount("/media", StaticFiles(directory=str(STORAGE)), name="media")

video_engine = VideoEngine()


# =========================
# ENDPOINT PRINCIPAL
# =========================
@app.post("/crear-eterna")
async def crear_eterna(request: Request):

    try:
        form = await request.form()

        frase1 = (form.get("frase1") or "").strip()
        frase2 = (form.get("frase2") or "").strip()
        frase3 = (form.get("frase3") or "").strip()

        frases = [frase1, frase2, frase3]

        fotos: List[UploadFile] = []

        for _, value in form.multi_items():
            if isinstance(value, UploadFile):
                if value.filename and value.content_type.startswith("image"):
                    fotos.append(value)

        if not fotos:
            raise HTTPException(status_code=400, detail="No se recibieron fotos")

        eterna_id = str(uuid.uuid4())
        folder = STORAGE / eterna_id
        folder.mkdir(parents=True, exist_ok=True)

        image_paths = []

        for i, foto in enumerate(fotos[:6], start=1):
            path = folder / f"foto{i}.jpg"

            with open(path, "wb") as f:
                f.write(await foto.read())

            image_paths.append(str(path))

        video_path = folder / "video.mp4"

        video_engine.generate_video(
            image_paths=image_paths,
            phrases=frases,
            output_path=str(video_path)
        )

        print("VIDEO PATH:", video_path)
        print("EXISTE:", os.path.exists(video_path))

        if not video_path.exists():
            raise HTTPException(status_code=500, detail="No se creó el vídeo")

        video_url = f"{request.base_url}media/{eterna_id}/video.mp4"

        return JSONResponse({
            "status": "ok",
            "eterna_id": eterna_id,
            "video_url": video_url
        })

    except Exception as e:
        print("ERROR:", str(e))
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": str(e)}
        )


# =========================
# HEALTH CHECK
# =========================
@app.get("/")
def home():
    return {"status": "ETERNA backend live"}
