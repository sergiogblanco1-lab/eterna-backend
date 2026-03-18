from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import uuid
from pathlib import Path

app = FastAPI(title="ETERNA backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

STORAGE = Path("storage")
STORAGE.mkdir(parents=True, exist_ok=True)


def limpiar_texto(valor: Optional[str]) -> str:
    if valor is None:
        return ""
    return valor.strip()


def extension_segura(nombre_archivo: str) -> str:
    ext = Path(nombre_archivo).suffix.lower()
    validas = [".jpg", ".jpeg", ".png", ".webp"]
    if ext in validas:
        return ext
    return ".jpg"


@app.get("/")
def home():
    return {
        "status": "ETERNA OK",
        "version": "v4_reaccion"
    }


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
    fotos: List[UploadFile] = File(...)
):
    try:
        nombre = limpiar_texto(nombre)
        email = limpiar_texto(email)
        telefono = limpiar_texto(telefono)
        nombre_destinatario = limpiar_texto(nombre_destinatario)
        telefono_destinatario = limpiar_texto(telefono_destinatario)
        frase1 = limpiar_texto(frase1)
        frase2 = limpiar_texto(frase2)
        frase3 = limpiar_texto(frase3)

        if len(fotos) == 0:
            return {"status": "error", "detalle": "Debes subir al menos 1 foto"}

        if len(fotos) > 6:
            return {"status": "error", "detalle": "Máximo 6 fotos"}

        eterna_id = str(uuid.uuid4())
        carpeta = STORAGE / eterna_id
        carpeta.mkdir(parents=True, exist_ok=True)

        with open(carpeta / "data.txt", "w", encoding="utf-8") as f:
            f.write(f"nombre: {nombre}\n")
            f.write(f"email: {email}\n")
            f.write(f"telefono: {telefono}\n")
            f.write(f"destinatario: {nombre_destinatario}\n")
            f.write(f"telefono_dest: {telefono_destinatario}\n")
            f.write(f"frase1: {frase1}\n")
            f.write(f"frase2: {frase2}\n")
            f.write(f"frase3: {frase3}\n")

        for i, foto in enumerate(fotos):
            contenido = await foto.read()
            if not contenido:
                continue

            ext = extension_segura(foto.filename or "")
            with open(carpeta / f"foto{i+1}{ext}", "wb") as f:
                f.write(contenido)

        link_destinatario = f"https://eterna-test.carrd.co/?id={eterna_id}"

        return {
            "status": "ok",
            "eterna_id": eterna_id,
            "link": link_destinatario
        }

    except Exception as e:
        return {"status": "error", "detalle": str(e)}


@app.post("/subir-reaccion")
async def subir_reaccion(
    eterna_id: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        eterna_id = limpiar_texto(eterna_id)

        if not eterna_id:
            return {"status": "error", "detalle": "Falta eterna_id"}

        carpeta = STORAGE / eterna_id
        carpeta.mkdir(parents=True, exist_ok=True)

        contenido = await file.read()

        if not contenido:
            return {"status": "error", "detalle": "Archivo vacío"}

        ruta = carpeta / "reaccion.webm"
        with open(ruta, "wb") as f:
            f.write(contenido)

        return {
            "status": "ok",
            "eterna_id": eterna_id,
            "archivo": "reaccion.webm"
        }

    except Exception as e:
        return {"status": "error", "detalle": str(e)}
