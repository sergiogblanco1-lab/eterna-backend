from fastapi import FastAPI
import uvicorn
import os

app = FastAPI()

@app.get("/")
def home():
    return {"status": "ETERNA backend alive"}

@app.get("/crear-eterna")
def crear_eterna():
    return {
    "ok": True,
    "message": "Tu ETERNA ha comenzado a crearse",
    "next_step": "Subir 6 fotos y escribir 3 frases"
}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
