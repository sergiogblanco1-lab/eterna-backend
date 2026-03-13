from fastapi import FastAPI, UploadFile, File, Form
from typing import List
import uvicorn
import os

app = FastAPI()


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
    return {
        "ok": True,
        "message": "Tu ETERNA ha sido recibida",
        "nombre": nombre,
        "email": email,
        "frases": [frase1, frase2, frase3],
        "numero_fotos": len(fotos)
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
