from fastapi import FastAPI, UploadFile, File, Form
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
    foto1: UploadFile = File(...),
    foto2: UploadFile = File(...),
    foto3: UploadFile = File(...),
    foto4: UploadFile = File(...),
    foto5: UploadFile = File(...),
    foto6: UploadFile = File(...)
):
    eterna_id = str(uuid.uuid4())
    folder = os.path.join(STORAGE, eterna_id)
    os.makedirs(folder, exist_ok=True)

    frases = [frase1, frase2, frase3]

    with open(os.path.join(folder, "frases.txt"), "w", encoding="utf-8") as f:
        for frase in frases:
            f.write(frase + "\n")

    fotos = [foto1, foto2, foto3, foto4, foto5, foto6]

    for i, foto in enumerate(fotos, start=1):
        contenido = await foto.read()
        nombre_archivo = foto.filename or f"foto{i}.jpg"
        ruta = os.path.join(folder, nombre_archivo)

        with open(ruta, "wb") as f:
            f.write(contenido)

    return {
        "ok": True,
        "eterna_id": eterna_id,
        "video": video_path,
        "message": "Tu ETERNA ha sido guardada",
        "numero_fotos": 6
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
