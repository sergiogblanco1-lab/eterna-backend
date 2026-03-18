from fastapi import FastAPI, UploadFile, File, Form
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

    # DATOS REGALANTE
    nombre: str = Form(...),
    email: str = Form(...),
    telefono: str = Form(...),

    # DESTINATARIO
    nombre_destinatario: str = Form(...),
    telefono_destinatario: str = Form(...),

    # MENSAJE
    frase1: str = Form(...),
    frase2: str = Form(...),
    frase3: str = Form(...),

    # FOTOS
    foto1: UploadFile = File(...),
    foto2: UploadFile = File(...),
    foto3: UploadFile = File(...),
    foto4: UploadFile = File(...),
    foto5: UploadFile = File(...),
    foto6: UploadFile = File(...),
):
    eterna_id = str(uuid.uuid4())
    carpeta = os.path.join(STORAGE, eterna_id)
    os.makedirs(carpeta, exist_ok=True)

    # GUARDAR INFO
    with open(os.path.join(carpeta, "data.txt"), "w") as f:
        f.write(f"NOMBRE: {nombre}\n")
        f.write(f"EMAIL: {email}\n")
        f.write(f"TEL REGALANTE: {telefono}\n")
        f.write(f"NOMBRE DEST: {nombre_destinatario}\n")
        f.write(f"TEL DEST: {telefono_destinatario}\n")
        f.write(f"FRASES:\n{frase1}\n{frase2}\n{frase3}\n")

    # GUARDAR FOTOS
    fotos = [foto1, foto2, foto3, foto4, foto5, foto6]

    for i, foto in enumerate(fotos):
        contenido = await foto.read()
        ruta = os.path.join(carpeta, f"foto{i+1}.jpg")

        with open(ruta, "wb") as f:
            f.write(contenido)

    return {
        "status": "ok",
        "eterna_id": eterna_id
    }
