import os
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Customer, Recipient, EternaOrder
from schemas import HealthResponse
from storage_service import StorageService
from video_engine import VideoEngine

from utils import (
    valid_email,
    valid_phone,
    normalize_phone,
    new_slug
)

# ----------------------------------------------------
# CREAR BASE DE DATOS
# ----------------------------------------------------

Base.metadata.create_all(bind=engine)

# ----------------------------------------------------
# APP
# ----------------------------------------------------

app = FastAPI(title="ETERNA")

storage = StorageService()
video_engine = VideoEngine()


# ----------------------------------------------------
# SALUD DEL SERVIDOR
# ----------------------------------------------------

@app.get("/health", response_model=HealthResponse)
def health():
    return {"status": "ok", "service": "ETERNA backend alive"}


# ----------------------------------------------------
# PÁGINA PRINCIPAL
# ----------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
    <head>
    <title>ETERNA</title>
    <style>
    body{
        background:#0b0b0b;
        color:white;
        font-family:Arial;
        max-width:700px;
        margin:auto;
        padding:40px;
    }

    input,textarea{
        width:100%;
        margin-bottom:10px;
        padding:12px;
        border-radius:8px;
        border:none;
        background:#1f1f1f;
        color:white;
    }

    button{
        background:#e7c27d;
        border:none;
        padding:15px;
        border-radius:999px;
        font-weight:bold;
        width:100%;
        cursor:pointer;
    }
    </style>
    </head>

    <body>

    <h1>ETERNA</h1>
    <p>Hay momentos que merecen quedarse para siempre.</p>

    <form action="/crear-eterna" method="post" enctype="multipart/form-data">

    <h3>TUS DATOS</h3>

    <input name="nombre" placeholder="Tu nombre" required>
    <input name="email" placeholder="Tu email" required>
    <input name="telefono_regalante" placeholder="Tu teléfono" required>

    <h3>DESTINATARIO</h3>

    <input name="nombre_destinatario" placeholder="Nombre destinatario" required>
    <input name="telefono_destinatario" placeholder="Teléfono destinatario" required>

    <h3>FRASES</h3>

    <textarea name="frase1" placeholder="Frase 1" required></textarea>
    <textarea name="frase2" placeholder="Frase 2" required></textarea>
    <textarea name="frase3" placeholder="Frase 3" required></textarea>

    <h3>FOTOS</h3>

    <input type="file" name="fotos" accept="image/*" multiple required>

    <h3>VIDEO MENSAJE (OPCIONAL)</h3>

    <input type="file" name="video_mensaje" accept="video/*">

    <br><br>

    <button type="submit">Crear mi ETERNA</button>

    </form>

    </body>
    </html>
    """


# ----------------------------------------------------
# CREAR ETERNA
# ----------------------------------------------------

@app.post("/crear-eterna")
async def crear_eterna(
    nombre: str = Form(...),
    email: str = Form(...),
    telefono_regalante: str = Form(...),
    nombre_destinatario: str = Form(...),
    telefono_destinatario: str = Form(...),
    frase1: str = Form(...),
    frase2: str = Form(...),
    frase3: str = Form(...),
    fotos: List[UploadFile] = File(...),
    video_mensaje: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):

    email = email.lower().strip()
    telefono_regalante = normalize_phone(telefono_regalante)
    telefono_destinatario = normalize_phone(telefono_destinatario)

    if not valid_email(email):
        raise HTTPException(status_code=400, detail="Email inválido")

    if not valid_phone(telefono_regalante):
        raise HTTPException(status_code=400, detail="Teléfono regalante inválido")

    if not valid_phone(telefono_destinatario):
        raise HTTPException(status_code=400, detail="Teléfono destinatario inválido")

    if len(fotos) != 6:
        raise HTTPException(status_code=400, detail="Debes subir exactamente 6 fotos")

    # ------------------------------------------------
    # CLIENTE
    # ------------------------------------------------

    cliente = db.query(Customer).filter(Customer.email == email).first()

    if not cliente:
        cliente = Customer(
            name=nombre,
            email=email,
            phone=telefono_regalante,
            created_at=datetime.utcnow()
        )
        db.add(cliente)
        db.commit()
        db.refresh(cliente)

    # ------------------------------------------------
    # DESTINATARIO
    # ------------------------------------------------

    destinatario = Recipient(
        name=nombre_destinatario,
        phone=telefono_destinatario,
        consent_confirmed=True,
        created_at=datetime.utcnow()
    )

    db.add(destinatario)
    db.commit()
    db.refresh(destinatario)

    # ------------------------------------------------
    # ORDEN
    # ------------------------------------------------

    slug = new_slug()

    orden = EternaOrder(
        customer_id=cliente.id,
        recipient_id=destinatario.id,
        phrase_1=frase1,
        phrase_2=frase2,
        phrase_3=frase3,
        public_slug=slug,
        state="uploaded",
        created_at=datetime.utcnow()
    )

    db.add(orden)
    db.commit()
    db.refresh(orden)

    # ------------------------------------------------
    # GUARDAR FOTOS
    # ------------------------------------------------

    storage.save_photos(orden.id, fotos)

    if video_mensaje:
        storage.save_sender_video(orden.id, video_mensaje)

    return JSONResponse(
        {
            "ok": True,
            "order_id": orden.id,
            "slug": slug,
            "message": "ETERNA creada correctamente"
        }
    )


# ----------------------------------------------------
# LISTAR PEDIDOS
# ----------------------------------------------------

@app.get("/orders")
def orders(db: Session = Depends(get_db)):

    lista = db.query(EternaOrder).all()

    resultado = []

    for o in lista:

        resultado.append({
            "id": o.id,
            "estado": o.state,
            "cliente": o.customer.name,
            "destinatario": o.recipient.name,
            "fecha": o.created_at
        })

    return resultado
