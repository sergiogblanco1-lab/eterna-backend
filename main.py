from fastapi import FastAPI, UploadFile, File, Form
from typing import Optional
import os
import uuid

app = FastAPI()

STORAGE = "storage"
os.makedirs(STORAGE, exist_ok=True)


@app.get("/")
def home():
    return {"status": "ETERNA OK"}


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
    foto1: Optional[UploadFile] = File(None),
    foto2: Optional[UploadFile] = File(None),
    foto3: Optional[UploadFile] = File(None),
    foto4: Optional[UploadFile] = File(None),
    foto5: Optional[UploadFile] = File(None),
    foto6: Optional[UploadFile] = File(None),
):
    try:
        eterna_id = str(uuid.uuid4())
        carpeta = os.path.join(STORAGE, eterna_id)
        os.makedirs(carpeta, exist_ok=True)

        # Guardar datos
        with open(os.path.join(carpeta, "data.txt"), "w") as f:
            f.write(f"nombre: {nombre}\n")
            f.write(f"email: {email}\n")
            f.write(f"telefono: {telefono}\n")
            f.write(f"destinatario: {nombre_destinatario}\n")
            f.write(f"telefono_dest: {telefono_destinatario}\n")
            f.write(f"frase1: {frase1}\n")
            f.write(f"frase2: {frase2}\n")
            f.write(f"frase3: {frase3}\n")

        fotos = [foto1, foto2, foto3, foto4, foto5, foto6]

        for i, foto in enumerate(fotos):
            if foto:
                contenido = await foto.read()
                with open(os.path.join(carpeta, f"foto{i+1}.jpg"), "wb") as f:
                    f.write(contenido)

        return {
            "status": "ok",
            "eterna_id": eterna_id
        }

    except Exception as e:
        return {
            "status": "error",
            "detalle": str(e)
        }
