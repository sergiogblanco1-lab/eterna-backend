import os
import uuid
from datetime import datetime

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Customer, Recipient, EternaOrder
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
            h1 { margin-bottom: 8px; }
            p { color: #cccccc; margin-bottom: 24px; line-height: 1.5; }
            form {
                display: flex;
                flex-direction: column;
                gap: 12px;
            }
            input, textarea, button {
                width: 100%;
                box-sizing: border-box;
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
            .ok {
                color: #9fe870;
                font-weight: bold;
            }
            .error {
                color: #ff9a9a;
                font-weight: bold;
            }
            code {
                background: #1b1b1b;
                padding: 3px 6px;
                border-radius: 6px;
                color: #f1f1f1;
                word-break: break-word;
            }
            a.button {
                display: inline-block;
                margin-top: 18px;
                padding: 12px 18px;
                border-radius: 999px;
                background: #e7c27d;
                color: black;
                font-weight: bold;
                text-decoration: none;
            }
            video {
                width: 100%;
                max-width: 420px;
                border-radius: 16px;
                background: black;
                margin-top: 16px;
            }
        </style>
    </head>
    <body>
        <h1>ETERNA</h1>
        <p>Hay momentos que merecen quedarse para siempre.</p>

        <div class="box">
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

                <div class="note">Esta versión guarda pedido, fotos y genera el vídeo automáticamente.</div>

                <button type="submit">Crear mi ETERNA</button>
            </form>
        </div>
    </body>
    </html>
    """


@app.get("/health")
def health():
    return {"status": "ok", "service": "ETERNA backend"}


@app.post("/crear-eterna", response_class=HTMLResponse)
async def crear_eterna(request: Request, db: Session = Depends(get_db)):
    form = await request.form()

    nombre = (form.get("nombre") or "").strip()
    email = (form.get("email") or "").strip()
    telefono_regalante = (form.get("telefono_regalante") or "").strip()
    nombre_destinatario = (form.get("nombre_destinatario") or "").strip()
    telefono_destinatario = (form.get("telefono_destinatario") or "").strip()
    frase1 = (form.get("frase1") or "").strip()
    frase2 = (form.get("frase2") or "").strip()
    frase3 = (form.get("frase3") or "").strip()

    fotos = [
        form.get("foto1"),
        form.get("foto2"),
        form.get("foto3"),
        form.get("foto4"),
        form.get("foto5"),
        form.get("foto6"),
    ]

    if not nombre or not email or not telefono_regalante:
        raise HTTPException(status_code=400, detail="Faltan datos del regalante")

    if not nombre_destinatario or not telefono_destinatario:
        raise HTTPException(status_code=400, detail="Faltan datos del destinatario")

    if not frase1 or not frase2 or not frase3:
        raise HTTPException(status_code=400, detail="Faltan frases")

    fotos_validas = [f for f in fotos if f is not None and getattr(f, "filename", None)]
    if len(fotos_validas) != 6:
        raise HTTPException(status_code=400, detail="Debes subir exactamente 6 fotos")

    try:
        cliente = db.query(Customer).filter(Customer.email == email).first()

        if not cliente:
            cliente = Customer(
                id=str(uuid.uuid4()),
                name=nombre,
                email=email,
                phone=telefono_regalante,
                created_at=datetime.utcnow()
            )
            db.add(cliente)
            db.commit()
            db.refresh(cliente)

        destinatario = Recipient(
            id=str(uuid.uuid4()),
            name=nombre_destinatario,
            phone=telefono_destinatario,
            consent_confirmed=False,
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
            state="created",
            created_at=datetime.utcnow()
        )
        db.add(orden)
        db.commit()
        db.refresh(orden)

        saved_photos = await storage.save_photos(order_id, fotos_validas)
        orden.photos_json = storage.photos_json(saved_photos)
        orden.state = "photos_saved"
        db.commit()
        db.refresh(orden)

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
        db.refresh(orden)

        return f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>ETERNA creada</title>
            <style>
                body {{
                    background: #0b0b0b;
                    color: white;
                    font-family: Arial, sans-serif;
                    max-width: 760px;
                    margin: 0 auto;
                    padding: 30px 20px;
                }}
                .box {{
                    background: #111;
                    padding: 24px;
                    border-radius: 16px;
                    border: 1px solid #222;
                }}
                .ok {{
                    color: #9fe870;
                    font-weight: bold;
                }}
                code {{
                    background: #1b1b1b;
                    padding: 3px 6px;
                    border-radius: 6px;
                    color: #f1f1f1;
                    word-break: break-word;
                }}
                a.button {{
                    display: inline-block;
                    margin-top: 18px;
                    padding: 12px 18px;
                    border-radius: 999px;
                    background: #e7c27d;
                    color: black;
                    font-weight: bold;
                    text-decoration: none;
                }}
            </style>
        </head>
        <body>
            <div class="box">
                <h1>ETERNA creada ✅</h1>
                <p class="ok">Pedido, fotos y vídeo generados correctamente.</p>

                <p><strong>Order ID:</strong> <code>{orden.id}</code></p>
                <p><strong>Estado:</strong> <code>{orden.state}</code></p>
                <p><strong>Cliente:</strong> <code>{cliente.name}</code></p>
                <p><strong>Destinatario:</strong> <code>{destinatario.name}</code></p>
                <p><strong>Fotos guardadas:</strong> <code>{len(saved_photos)}</code></p>

                <a class="button" href="/video/{orden.id}">Ver vídeo</a>
                <br>
                <a class="button" href="/">Crear otra ETERNA</a>
            </div>
        </body>
        </html>
        """

    except Exception as e:
        db.rollback()
        return f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <title>Error</title>
            <style>
                body {{
                    background: #0b0b0b;
                    color: white;
                    font-family: Arial, sans-serif;
                    max-width: 760px;
                    margin: 0 auto;
                    padding: 30px 20px;
                }}
                .box {{
                    background: #111;
                    padding: 24px;
                    border-radius: 16px;
                    border: 1px solid #422;
                }}
                .error {{
                    color: #ff9a9a;
                    font-weight: bold;
                }}
                code {{
                    background: #1b1b1b;
                    padding: 3px 6px;
                    border-radius: 6px;
                    color: #f1f1f1;
                    word-break: break-word;
                }}
            </style>
        </head>
        <body>
            <div class="box">
                <h1>Error creando ETERNA</h1>
                <p class="error">Algo ha fallado.</p>
                <p><strong>Detalle:</strong> <code>{str(e)}</code></p>
            </div>
        </body>
        </html>
        """


@app.get("/orders")
def orders(db: Session = Depends(get_db)):
    lista = db.query(EternaOrder).all()
    return [
        {
            "id": o.id,
            "state": o.state,
            "customer_id": o.customer_id,
            "recipient_id": o.recipient_id,
            "photos_json": o.photos_json,
            "final_video_path": o.final_video_path,
            "created_at": o.created_at.isoformat() if o.created_at else None
        }
        for o in lista
    ]


@app.get("/orders/{order_id}")
def order_detail(order_id: str, db: Session = Depends(get_db)):
    o = db.query(EternaOrder).filter(EternaOrder.id == order_id).first()

    if not o:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    return {
        "id": o.id,
        "state": o.state,
        "customer_id": o.customer_id,
        "recipient_id": o.recipient_id,
        "phrase_1": o.phrase_1,
        "phrase_2": o.phrase_2,
        "phrase_3": o.phrase_3,
        "photos_json": o.photos_json,
        "final_video_path": o.final_video_path,
        "created_at": o.created_at.isoformat() if o.created_at else None
    }


@app.get("/video/{order_id}", response_class=HTMLResponse)
def video_page(order_id: str, db: Session = Depends(get_db)):
    o = db.query(EternaOrder).filter(EternaOrder.id == order_id).first()

    if not o or not o.final_video_path:
        raise HTTPException(status_code=404, detail="Vídeo no disponible")

    if not os.path.exists(o.final_video_path):
        raise HTTPException(status_code=404, detail="Archivo de vídeo no encontrado")

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Vídeo ETERNA</title>
        <style>
            body {{
                background: #000;
                color: white;
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                text-align: center;
            }}
            .wrap {{
                max-width: 460px;
                margin: 0 auto;
            }}
            video {{
                width: 100%;
                border-radius: 16px;
                background: black;
                margin-top: 12px;
            }}
            a.button {{
                display: inline-block;
                margin-top: 18px;
                padding: 12px 18px;
                border-radius: 999px;
                background: #e7c27d;
                color: black;
                font-weight: bold;
                text-decoration: none;
            }}
        </style>
    </head>
    <body>
        <div class="wrap">
            <h1>Tu ETERNA</h1>
            <video controls autoplay playsinline>
                <source src="/video-file/{order_id}" type="video/mp4">
                Tu navegador no puede reproducir este vídeo.
            </video>
            <a class="button" href="/">Crear otra ETERNA</a>
        </div>
    </body>
    </html>
    """


@app.get("/video-file/{order_id}")
def get_video_file(order_id: str, db: Session = Depends(get_db)):
    o = db.query(EternaOrder).filter(EternaOrder.id == order_id).first()

    if not o or not o.final_video_path:
        raise HTTPException(status_code=404, detail="Vídeo no disponible")

    if not os.path.exists(o.final_video_path):
        raise HTTPException(status_code=404, detail="Archivo de vídeo no encontrado")

    return FileResponse(
        path=o.final_video_path,
        media_type="video/mp4",
        filename=f"{order_id}.mp4"
    )
