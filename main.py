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
        "version": "v3_flujo_unificado"
    }


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
            return {
                "status": "error",
                "detalle": "Debes subir al menos 1 foto"
            }

        if len(fotos) > 6:
            return {
                "status": "error",
                "detalle": "Máximo 6 fotos"
            }

        eterna_id = str(uuid.uuid4())
        carpeta = STORAGE / eterna_id
        carpeta.mkdir(parents=True, exist_ok=True)

        # guardar datos
        with open(carpeta / "data.txt", "w", encoding="utf-8") as f:
            f.write(f"nombre: {nombre}\n")
            f.write(f"email: {email}\n")
            f.write(f"telefono: {telefono}\n")
            f.write(f"destinatario: {nombre_destinatario}\n")
            f.write(f"telefono_dest: {telefono_destinatario}\n")
            f.write(f"frase1: {frase1}\n")
            f.write(f"frase2: {frase2}\n")
            f.write(f"frase3: {frase3}\n")

        # guardar estado
        with open(carpeta / "status.txt", "w", encoding="utf-8") as f:
            f.write("estado: creada\n")
            f.write("reaccion: no_grabada\n")
            f.write("video: no_generado\n")

        # guardar fotos
        fotos_guardadas = []

        for i, foto in enumerate(fotos):
            if not foto.filename:
                continue

            contenido = await foto.read()
            if not contenido:
                continue

            ext = extension_segura(foto.filename)
            nombre_archivo = f"foto{i+1}{ext}"
            ruta = carpeta / nombre_archivo

            with open(ruta, "wb") as f:
                f.write(contenido)

            fotos_guardadas.append(nombre_archivo)

        if len(fotos_guardadas) == 0:
            return {
                "status": "error",
                "detalle": "No se pudieron guardar las fotos"
            }

        # CAMBIA ESTA URL CUANDO TENGAS LA PÁGINA FINAL DEL DESTINATARIO
        link_destinatario = f"https://eterna-test.carrd.co/?id={eterna_id}"

        return {
            "status": "ok",
            "eterna_id": eterna_id,
            "fotos_recibidas": len(fotos_guardadas),
            "fotos_guardadas": fotos_guardadas,
            "link": link_destinatario
        }

    except Exception as e:
        return {
            "status": "error",
            "detalle": str(e)
        }


# =========================
# SUBIR REACCIÓN
# =========================
@app.post("/subir-reaccion")
async def subir_reaccion(
    eterna_id: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        eterna_id = limpiar_texto(eterna_id)

        if not eterna_id:
            return {
                "status": "error",
                "detalle": "Falta eterna_id"
            }

        carpeta = STORAGE / eterna_id
        carpeta.mkdir(parents=True, exist_ok=True)

        ruta = carpeta / "reaccion.webm"
        contenido = await file.read()

        if not contenido:
            return {
                "status": "error",
                "detalle": "Archivo vacío"
            }

        with open(ruta, "wb") as f:
            f.write(contenido)

        with open(carpeta / "status.txt", "w", encoding="utf-8") as f:
            f.write("estado: reaccion_recibida\n")
            f.write("reaccion: grabada\n")
            f.write("video: no_generado\n")

        return {
            "status": "ok",
            "eterna_id": eterna_id,
            "archivo": "reaccion.webm"
        }

    except Exception as e:
        return {
            "status": "error",
            "detalle": str(e)
        }
