from fastapi import FastAPI, UploadFile, File, Form
from typing import List, Optional
import uuid

from storage_service import StorageService

app = FastAPI(title="ETERNA backend")

storage = StorageService()


def limpiar_texto(valor: Optional[str]) -> str:
    if valor is None:
        return ""
    return valor.strip()


@app.get("/")
def home():
    return {
        "status": "ETERNA OK",
        "version": "v1_sin_video_sin_stripe"
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
        carpeta = storage.crear_carpeta_eterna(eterna_id)

        storage.guardar_datos(
            carpeta=carpeta,
            datos={
                "nombre": nombre,
                "email": email,
                "telefono": telefono,
                "destinatario": nombre_destinatario,
                "telefono_dest": telefono_destinatario,
                "frase1": frase1,
                "frase2": frase2,
                "frase3": frase3,
            }
        )

        storage.guardar_estado_inicial(carpeta)

        fotos_guardadas = await storage.guardar_fotos(carpeta, fotos)

        if len(fotos_guardadas) == 0:
            return {
                "status": "error",
                "detalle": "Las fotos no son válidas o llegaron vacías"
            }

        payment_url = f"/pagar/{eterna_id}"

        return {
            "status": "ok",
            "eterna_id": eterna_id,
            "fotos_recibidas": len(fotos_guardadas),
            "fotos_guardadas": fotos_guardadas,
            "payment_url": payment_url,
            "video_generado": False
        }

    except Exception as e:
        return {
            "status": "error",
            "detalle": str(e)
        }
