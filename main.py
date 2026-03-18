import os
import uuid
from pathlib import Path
from typing import List

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Customer, Recipient, EternaOrder
from schemas import HealthResponse, EternaCreateResponse
from storage_service import StorageService
from video_engine import VideoEngine


app = FastAPI(title="ETERNA backend")

Base.metadata.create_all(bind=engine)

storage = StorageService()
video_engine = VideoEngine()

# Asegura carpeta storage
Path("storage").mkdir(parents=True, exist_ok=True)

# Sirve archivos
app.mount("/media", StaticFiles(directory="storage"), name="media")


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", service="ETERNA backend")


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    base_url = str(request.base_url).rstrip("/")

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>ETERNA</title>
        <style>
            body {{
                margin: 0;
                font-family: Arial;
                background: #0b0b0b;
                color: white;
            }}
            .wrap {{
                max-width: 700px;
                margin: auto;
                padding: 30px;
            }}
            input, textarea {{
                width: 100%;
                margin-top: 10px;
                margin-bottom: 20px;
                padding: 12px;
                border-radius: 10px;
                border: 1px solid #333;
                background: #111;
                color: white;
            }}
            button {{
                width: 100%;
                padding: 15px;
                border-radius: 10px;
                border: none;
                background: white;
                color: black;
                font-weight: bold;
                cursor: pointer;
            }}
            .result {{
                margin-top: 20px;
                padding: 15px;
                background: #111;
                border-radius: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="wrap">
            <h1>ETERNA</h1>

            <form id="form">
                <input name="customer_name" placeholder="Tu nombre" required />
                <input name="customer_email" placeholder="Tu email" required />

                <input name="recipient_name" placeholder="Nombre destinatario" required />
                <input name="recipient_phone" placeholder="Teléfono (opcional)" />
                <input name="recipient_email" placeholder="Email (opcional)" />

                <textarea name="phrase1" placeholder="Frase 1" required></textarea>
                <textarea name="phrase2" placeholder="Frase 2" required></textarea>
                <textarea name="phrase3" placeholder="Frase 3" required></textarea>

                <input type="file" name="photos" multiple accept="image/*" required />

                <button>Crear mi ETERNA</button>
            </form>

            <div class="result" id="result"></div>
        </div>

        <script>
            const form = document.getElementById("form");
            const result = document.getElementById("result");

            form.onsubmit = async (e) => {{
                e.preventDefault();

                result.innerText = "Creando...";

                const data = new FormData(form);

                const files = form.querySelector('input[type="file"]').files;
                for (let i = 0; i < files.length; i++) {{
                    data.append("photos", files[i]);
                }}

                try {{
                    const res = await fetch("/crear-eterna", {{
                        method: "POST",
                        body: data
                    }});

                    const json = await res.json();

                    result.innerText = JSON.stringify(json, null, 2);
                }} catch {{
                    result.innerText = "Error inesperado al crear la ETERNA";
                }}
            }};
        </script>
    </body>
    </html>
    """


@app.post("/crear-eterna", response_model=EternaCreateResponse)
async def crear_eterna(
    request: Request,
    customer_name: str = Form(...),
    customer_email: str = Form(...),
    recipient_name: str = Form(...),
    recipient_phone: str = Form(""),
    recipient_email: str = Form(""),
    phrase1: str = Form(...),
    phrase2: str = Form(...),
    phrase3: str = Form(...),
    photos: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    # VALIDACIÓN CLARA (como Carrd)
    if len(photos) < 1:
        raise HTTPException(status_code=400, detail="Sube al menos 1 foto")

    if len(photos) > 6:
        raise HTTPException(status_code=400, detail="Máximo 6 fotos")

    eterna_id = str(uuid.uuid4())
    folder = storage.create_eterna_folder(eterna_id)

    phrases = [phrase1, phrase2, phrase3]
    storage.save_phrases(folder, phrases)

    # GUARDAR IMÁGENES
    saved_images = await storage.save_uploaded_images(folder, photos)

    # 🔴 VIDEO DESACTIVADO TEMPORALMENTE
    output_video_path = None

    # GUARDAR DB
    customer = Customer(name=customer_name, email=customer_email)
    db.add(customer)
    db.commit()
    db.refresh(customer)

    recipient = Recipient(
        name=recipient_name,
        phone=recipient_phone,
        email=recipient_email
    )
    db.add(recipient)
    db.commit()
    db.refresh(recipient)

    order = EternaOrder(
        eterna_id=eterna_id,
        customer_id=customer.id,
        recipient_id=recipient.id,
        phrase1=phrase1,
        phrase2=phrase2,
        phrase3=phrase3,
        image_count=len(saved_images),
        storage_folder=str(folder),
        video_path=None,
        status="created"
    )
    db.add(order)
    db.commit()

    return EternaCreateResponse(
        ok=True,
        eterna_id=eterna_id,
        message="ETERNA creada correctamente",
        video_url=None
    )


@app.get("/eterna/{eterna_id}")
def get_eterna(eterna_id: str, db: Session = Depends(get_db)):
    order = db.query(EternaOrder).filter(EternaOrder.eterna_id == eterna_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="No encontrada")

    return {
        "id": order.eterna_id,
        "phrases": [order.phrase1, order.phrase2, order.phrase3],
        "images": order.image_count,
        "status": order.status
    }
