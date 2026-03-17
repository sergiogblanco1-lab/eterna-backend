import os
import uuid
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Customer, Recipient, EternaOrder
from schemas import HealthResponse
from storage_service import StorageService
from video_engine import VideoEngine


app = FastAPI(title="ETERNA backend")

Base.metadata.create_all(bind=engine)

storage = StorageService()
video_engine = VideoEngine()


@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ETERNA</title>
        <style>
            body {
                background: #0b0b0b;
                color: white;
                font-family: Arial, sans-serif;
                max-width: 760px;
                margin: 0 auto;
                padding: 30px 20px;
            }
            h1 {
                margin-bottom: 8px;
            }
            p {
                color: #cccccc;
                margin-bottom: 24px;
            }
            form {
                display: flex;
                flex-direction: column;
                gap: 12px;
            }
            input, textarea, button {
                padding: 14px;
                border-radius: 10px;
                border: 1px solid #333;
                font-size: 16px;
            }
            input, textarea {
                background: #171717;
                color: white;
            }
            textarea {
                min-height: 90px;
                resize: vertical;
            }
            button {
                background: #e7c27d;
                color: black;
                border: none;
                font-weight: bold;
                cursor: pointer;
            }
            .box {
                background: #111;
                padding: 20px;
                border-radius: 16px;
                border: 1px solid #222;
            }
            .note {
                font-size: 14px;
                color: #aaa;
            }
        </style>
    </head>
    <body>
        <h1>ETERNA</h1>
        <p>Hay momentos que merecen quedarse para siempre.</p>

        <div class="box">
            <!-- 👇 CAMBIO CLAVE AQUÍ -->
            <form action="/crear-eterna" method="post" enctype="multipart/form-data" novalidate>

                <input name="nombre" placeholder="Tu nombre" required>
                <input name="email" placeholder="Tu email" required>
                <input name="telefono_regalante" placeholder="Tu teléfono" required>

                <input name="nombre_destinatario" placeholder="Nombre destinatario" required>
                <input name="telefono_destinatario" placeholder="Teléfono destinatario" required>

                <textarea name="frase1" placeholder="Frase 1" required></textarea>
                <textarea name="frase2" placeholder="Frase 2" required></textarea>
                <textarea name="frase3" placeholder="Frase 3" required></textarea>

                <label>Sube 6 fotos</label>
                <input name="foto1" type="file" accept="image/*" required>
                <input name="foto2" type="file" accept="image/*" required>
                <input name="foto3" type="file" accept="image/*" required>
                <input name="foto4" type="file" accept="image/*" required>
                <input name="foto5" type="file" accept="image/*" required>
                <input name="foto6" type="file" accept="image/*" required>

                <div class="note">Selecciona una imagen en cada campo.</div>

                <button type="submit">Crear mi ETERNA</button>
            </form>
        </div>
    </body>
    </html>
    """


@app.get("/health", response_model=HealthResponse)
def health():
    return {"status": "ok"}


@app.post("/crear-eterna", response_class=HTMLResponse)
async def crear_eterna(request: Request, db: Session = Depends(get_db)):
    form = await request.form()

    nombre = form.get("nombre")
    email = form.get("email")

    if not nombre or not email:
        return "<h1>Error: faltan datos</h1>"

    return "<h1>FORMULARIO FUNCIONA 🔥</h1>"


@app.get("/video/{order_id}")
def get_video(order_id: str, db: Session = Depends(get_db)):
    raise HTTPException(status_code=404, detail="No implementado aún")
