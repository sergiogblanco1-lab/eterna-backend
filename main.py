import uuid
from datetime import datetime
from typing import List

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Customer, Recipient, EternaOrder
from schemas import HealthResponse
from storage_service import StorageService


app = FastAPI(title="ETERNA backend")

Base.metadata.create_all(bind=engine)

storage = StorageService()


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
            <form action="/crear-eterna" method="post" enctype="multipart/form-data">
                <input name="nombre" placeholder="Tu nombre" required>
                <input name="email" type="email" placeholder="Tu email" required>
                <input name="telefono_regalante" placeholder="Tu teléfono" required>

                <input name="nombre_destinatario" placeholder="Nombre destinatario" required>
                <input name="telefono_destinatario" placeholder="Teléfono destinatario" required>

                <textarea name="frase1" placeholder="Frase 1" required></textarea>
                <textarea name="frase2" placeholder="Frase 2" required></textarea>
                <textarea name="frase3" placeholder="Frase 3" required></textarea>

                <label>Sube exactamente 6 fotos</label>
                <input name="fotos" type="file" accept="image/*" multiple required>

                <div class="note">Selecciona 6 imágenes en ese botón.</div>

                <button type="submit">Crear mi ETERNA</button>
            </form>
        </div>
    </body>
    </html>
    """


@app.get("/health", response_model=HealthResponse)
def health():
    return {
        "status": "ok",
        "service": "ETERNA backend alive"
    }


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

    destinatario = Recipient(
        name=nombre_destinatario,
        phone=telefono_destinatario,
        consent_confirmed=True,
        created_at=datetime.utcnow()
    )

    db.add(destinatario)
    db.commit()
    db.refresh(destinatario)

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

    saved_photos = storage.save_photos(order_id, fotos)
    orden.photos_json = storage.photos_json(saved_photos)
    db.commit()
    db.refresh(orden)

    return JSONResponse(
        {
            "ok": True,
            "order_id": orden.id,
            "slug": orden.public_slug,
            "message": "ETERNA creada correctamente"
        }
    )


@app.get("/orders")
def orders(db: Session = Depends(get_db)):
    lista = db.query(EternaOrder).all()
    resultado = []

    for o in lista:
        resultado.append({
            "id": o.id,
            "estado": o.state,
            "cliente": o.customer.name if o.customer else None,
            "destinatario": o.recipient.name if o.recipient else None,
            "fecha": o.created_at.isoformat() if o.created_at else None
        })

    return resultado
