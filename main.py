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
    nombre: str = Form(...),
    email: str = Form(...),
    telefono: str = Form(...),
    nombre_destinatario: str = Form(...),
    telefono_destinatario: str = Form(...),
    frase1: str = Form(...),
    frase2: str = Form(...),
    frase3: str = Form(...),
    foto1: UploadFile = File(...),
    foto2: UploadFile = File(...),
    foto3: UploadFile = File(...),
    foto4: UploadFile = File(...),
    foto5: UploadFile = File(...),
    foto6: UploadFile = File(...),
):
    eterna_id = str(uuid.uuid4())
    carpeta = os.path.join(STORAGE, eterna_id)
    os.makedirs(carpeta
