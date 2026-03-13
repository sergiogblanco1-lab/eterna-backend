from fastapi import FastAPI, UploadFile, File, Form
from typing import List
import uvicorn
import os
import uuid

app = FastAPI()

STORAGE = "eterna-storage"
os.makedirs(STORAGE, exist_ok=True)


@app.get("/")
def home():
    return {"status": "ETERNA backend alive"}


@app.post("/crear-eterna")
async def crear_eterna(
    nombre: str = Form(...),
    email: str = Form(...),
    frase1: str = Form(...),
    frase2: str = Form(...),
    frase3: str = Form(...),
    fotos: List[UploadFile] = File(...)
):

    eterna_id = str(uuid.uuid4())
    folder = os.path.join(STORAGE, eterna_id)
    os.makedirs(folder, exist_ok=True)

    frases = [frase1, frase2, frase3]

    with open(os.path.join(folder, "frases.txt"), "w") as f:
        for frase in frases:
            f.write(frase + "\n")

    for foto in fotos:
        contenido = await foto.read()
        with open(os.path.join(folder, foto.filename), "wb") as f:
            f.write(contenido)

    return {
        "ok": True,
        "eterna_id": eterna_id,
        "message": "Tu ETERNA ha sido guardada"
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
