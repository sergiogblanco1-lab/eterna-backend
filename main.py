from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import RedirectResponse
from typing import List, Optional
import uuid
import os
from pathlib import Path

app = FastAPI()

STORAGE = "storage"
os.makedirs(STORAGE, exist_ok=True)


@app.get("/")
def home():
    return {"status": "ETERNA OK"}


# =========================
# CREAR ETERNA
# =========================
@app.post("/crear-eterna")
async def crear_eterna(
    nombre: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    telefono: Optional[str] = Form(None),
    nombre_destinatario: Optional[str] = Form(None),
    telefono_destinatario: Optional[str] = Form(None),
    frase1: Optional[str] = Form(None),
    frase2: Optional[str] = Form(None),
    frase3: Optional[str] = Form(None),
    fotos: List[UploadFile] = File([])
):
    eterna_id = str(uuid.uuid4())

    carpeta = Path(f"{STORAGE}/{eterna_id}")
    carpeta.mkdir(parents=True, exist_ok=True)

    # guardar datos
    with open(carpeta / "data.txt", "w") as f:
        f.write(f"nombre: {nombre}\n")
        f.write(f"email: {email}\n")
        f.write(f"telefono: {telefono}\n")
        f.write(f"destinatario: {nombre_destinatario}\n")
        f.write(f"telefono_dest: {telefono_destinatario}\n")
        f.write(f"frase1: {frase1}\n")
        f.write(f"frase2: {frase2}\n")
        f.write(f"frase3: {frase3}\n")

    # guardar fotos
    for i, foto in enumerate(fotos):
        contenido = await foto.read()
        with open(carpeta / f"foto{i+1}.jpg", "wb") as f:
            f.write(contenido)

    # link para el destinatario
    link = f"https://eterna-play.carrd.co/?id={eterna_id}"

    return {
        "status": "ok",
        "eterna_id": eterna_id,
        "link": link
    }


# =========================
# SUBIR REACCIÓN
# =========================
@app.post("/subir-reaccion")
async def subir_reaccion(
    eterna_id: str = Form(...),
    file: UploadFile = File(...)
):
    carpeta = Path(f"{STORAGE}/{eterna_id}")
    carpeta.mkdir(parents=True, exist_ok=True)

    ruta = carpeta / "reaccion.webm"

    contenido = await file.read()

    with open(ruta, "wb") as f:
        f.write(contenido)

    return {"status": "ok"}
