from fastapi import FastAPI, UploadFile, File, Form
from typing import List, Optional
import os
import uuid
from pathlib import Path

app = FastAPI()

STORAGE = "storage"
os.makedirs(STORAGE, exist_ok=True)


@app.get("/")
def home():
    return {"status": "ETERNA OK"}


def limpiar_texto(valor: Optional[str]) -> str:
    if valor is None:
        return ""
    return valor.strip()


def extension_segura(filename: str) -> str:
    ext = Path(filename).suffix.lower()

    extensiones_validas = [".jpg", ".jpeg", ".png", ".webp"]

    if ext in extensiones_validas:
        return ext

    return ".jpg"


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
    try:
        # Limpiar datos
        nombre = limpiar_texto(nombre)
        email = limpiar_texto(email)
        telefono = limpiar_texto(telefono)
        nombre_destinatario = limpiar_texto(nombre_destinatario)
        telefono_destinatario = limpiar_texto(telefono_destinatario)
        frase1 = limpiar_texto(frase1)
        frase2 = limpiar_texto(frase2)
        frase3 = limpiar_texto(frase3)

        # Validación básica
        if len(fotos) == 0:
            return {
                "status": "error",
                "detalle": "No se recibieron fotos"
            }

        if len(fotos) > 6:
            return {
                "status": "error",
                "detalle": "Solo se permiten hasta 6 fotos"
            }

        eterna_id = str(uuid.uuid4())
        carpeta = os.path.join(STORAGE, eterna_id)
        os.makedirs(carpeta, exist_ok=True)

        # Guardar datos del pedido
        with open(os.path.join(carpeta, "data.txt"), "w", encoding="utf-8") as f:
            f.write(f"nombre: {nombre}\n")
            f.write(f"email: {email}\n")
            f.write(f"telefono: {telefono}\n")
            f.write(f"destinatario: {nombre_destinatario}\n")
            f.write(f"telefono_dest: {telefono_destinatario}\n")
            f.write(f"frase1: {frase1}\n")
            f.write(f"frase2: {frase2}\n")
            f.write(f"frase3: {frase3}\n")

        fotos_guardadas = []

        # Guardar fotos
        for i, foto in enumerate(fotos):
            if not foto.filename:
                continue

            contenido = await foto.read()

            if not contenido:
                continue

            ext = extension_segura(foto.filename)
            nombre_archivo = f"foto{i+1}{ext}"
            ruta_foto = os.path.join(carpeta, nombre_archivo)

            with open(ruta_foto, "wb") as f:
                f.write(contenido)

            fotos_guardadas.append(nombre_archivo)

        if len(fotos_guardadas) == 0:
            return {
                "status": "error",
                "detalle": "Las fotos llegaron vacías o no válidas"
            }

        # Aquí luego meteremos Stripe de verdad
        payment_url = f"/pagar/{eterna_id}"

        return {
            "status": "ok",
            "eterna_id": eterna_id,
            "fotos_recibidas": len(fotos_guardadas),
            "fotos_guardadas": fotos_guardadas,
            "payment_url": payment_url
        }

    except Exception as e:
        return {
            "status": "error",
            "detalle": str(e)
        }
