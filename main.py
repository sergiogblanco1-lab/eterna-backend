import os
import uuid
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
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
        <title>ETERNA</title>
    </head>
    <body style="background:#0b0b0b;color:white;font-family:sans-serif;padding:20px;">
        <h1>ETERNA</h1>
        <p>Hay momentos que merecen quedarse para siempre.</p>

        <form action="/crear-eterna" method="post" enctype="multipart/form-data">

            <input name="nombre" placeholder="Tu nombre" required><br><br>
            <input name="email" type="email" placeholder="Tu email" required><br><br>
            <input name="telefono_regalante" placeholder="Tu teléfono" required><br><br>

            <input name="nombre_destinatario" placeholder="Nombre destinatario" required><br><br>
            <input name="telefono_destinatario" placeholder="Teléfono destinatario" required><br><br>

            <textarea name="frase1" placeholder="Frase 1" required></textarea><br><br>
            <textarea name="frase2" placeholder="Frase 2" required></textarea><br><br>
            <textarea name="frase3" placeholder="Frase 3" required></textarea><br><br>

            <p>Sube 6 fotos</p>
            <input type="file" name="foto1" required><br>
            <input type="file" name="foto2" required><br>
            <input type="file" name="foto3" required><br>
            <input type="file" name="foto4" required><br>
            <input type="file" name="foto5" required><br>
            <input type="file" name="foto6" required><br><br>

            <button type="submit">Crear mi ETERNA</button>
        </form>
    </body>
    </html>
    """


@app.get("/health", response_model=HealthResponse)
def health():
    return {"status": "ok"}


@app.post("/crear-eterna", response_class=HTMLResponse)
async def crear_eterna(
    nombre: str = Form(...),
    email: str = Form(...),
    telefono_regalante: str = Form(...),
    nombre_destinatario: str = Form(...),
    telefono_destinatario: str = Form(...),
    frase1: str = Form(...),
    frase2: str = Form(...),
    frase3: str = Form(...),

    foto1: UploadFile = File(None),
    foto2: UploadFile = File(None),
    foto3: UploadFile = File(None),
    foto4: UploadFile = File(None),
    foto5: UploadFile = File(None),
    foto6: UploadFile = File(None),

    db: Session = Depends(get_db)
):

    fotos = [f for f in [foto1, foto2, foto3, foto4, foto5, foto6] if f]

    if len(fotos) != 6:
        raise HTTPException(status_code=400, detail="Debes subir 6 fotos")

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

    try:
        photo_paths = [
            os.path.join(storage.order_photos_dir(order_id), filename)
            for filename in saved_photos
        ]

        output_path = storage.order_final_video_path(order_id)

        final_video_path = video_engine.generate_video(
            order_id=order_id,
            photos=photo_paths,
            phrases=[frase1, frase2, frase3],
            output_path=output_path
        )

        orden.final_video_path = final_video_path
        orden.state = "video_generated"
        db.commit()

        return f"<h1>ETERNA creada</h1><a href='/video/{order_id}'>Ver vídeo</a>"

    except Exception as e:
        orden.state = "video_error"
        db.commit()

        return f"<h1>Error creando vídeo</h1><p>{str(e)}</p>"


@app.get("/video/{order_id}")
def get_video(order_id: str, db: Session = Depends(get_db)):
    o = db.query(EternaOrder).filter(EternaOrder.id == order_id).first()

    if not o or not o.final_video_path:
        raise HTTPException(status_code=404, detail="Vídeo no disponible")

    return FileResponse(o.final_video_path, media_type="video/mp4")
