import os
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Customer, Recipient, EternaOrder
from schemas import HealthResponse
from storage_service import StorageService
from video_engine import VideoEngine


# ----------------------------------------------------
# Inicialización
# ----------------------------------------------------

app = FastAPI(title="ETERNA backend")

Base.metadata.create_all(bind=engine)

storage = StorageService()
video_engine = VideoEngine()


# ----------------------------------------------------
# Health check
# ----------------------------------------------------

@app.get("/health", response_model=HealthResponse)
def health():
    return {
        "status": "ok",
        "service": "ETERNA backend alive"
    }


# ----------------------------------------------------
# Crear ETERNA
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

    db: Session = Depends(get_db)
):

    if len(fotos) != 6:
        raise HTTPException(
            status_code=400,
            detail="Debes subir exactamente 6 fotos"
        )

    # --------------------------------------------
    # Crear cliente
    # --------------------------------------------

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

    # --------------------------------------------
    # Crear destinatario
    # --------------------------------------------

    destinatario = Recipient(
        name=nombre_destinatario,
        phone=telefono_destinatario,
        consent_confirmed=True,
        created_at=datetime.utcnow()
    )

    db.add(destinatario)
    db.commit()
    db.refresh(destinatario)

    # --------------------------------------------
    # Crear pedido
    # --------------------------------------------

    order_id = str(uuid.uuid4())

    orden = EternaOrder(
        id=order_id,
        customer_id=cliente.id,
        recipient_id=destinatario.id,

        phrase_1=frase1,
        phrase_2=frase2,
        phrase_3=frase3,

        photos_json="[]",

        public_slug=order_id,
        state="uploaded",
        created_at=datetime.utcnow()
    )

    db.add(orden)
    db.commit()
    db.refresh(orden)

    # --------------------------------------------
    # Guardar fotos
    # --------------------------------------------

    saved_photos = storage.save_photos(order_id, fotos)

    orden.photos_json = storage.photos_json(saved_photos)

    db.commit()

    return JSONResponse(
        {
            "ok": True,
            "order_id": orden.id,
            "slug": orden.public_slug,
            "message": "ETERNA creada correctamente"
        }
    )


# ----------------------------------------------------
# Listar pedidos
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
