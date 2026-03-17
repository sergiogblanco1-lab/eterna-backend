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
                line-height: 1.6;
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
                box-sizing: border-box;
                width: 100%;
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
            a.button {
                display: inline-block;
                margin-top: 14px;
                padding: 12px 18px;
                border-radius: 999px;
                background: #e7c27d;
                color: black;
                font-weight: bold;
                text-decoration: none;
            }
            code {
                background: #1b1b1b;
                padding: 3px 6px;
                border-radius: 6px;
                color: #f1f1f1;
                word-break: break-word;
            }
            label {
                color: #ddd;
                font-size: 15px;
                margin-top: 5px;
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
    return {
        "status": "ok",
        "service": "ETERNA backend alive"
    }


@app.post("/crear-eterna", response_class=HTMLResponse)
async def crear_eterna(request: Request, db: Session = Depends(get_db)):
    form = await request.form()

    nombre = form.get("nombre")
    email = form.get("email")
    telefono_regalante = form.get("telefono_regalante")
    nombre_destinatario = form.get("nombre_destinatario")
    telefono_destinatario = form.get("telefono_destinatario")
    frase1 = form.get("frase1")
    frase2 = form.get("frase2")
    frase3 = form.get("frase3")

    if not nombre:
        raise HTTPException(status_code=400, detail="Falta nombre")
    if not email:
        raise HTTPException(status_code=400, detail="Falta email")
    if not telefono_regalante:
        raise HTTPException(status_code=400, detail="Falta telefono_regalante")
    if not nombre_destinatario:
        raise HTTPException(status_code=400, detail="Falta nombre_destinatario")
    if not telefono_destinatario:
        raise HTTPException(status_code=400, detail="Falta telefono_destinatario")
    if not frase1:
        raise HTTPException(status_code=400, detail="Falta frase1")
    if not frase2:
        raise HTTPException(status_code=400, detail="Falta frase2")
    if not frase3:
        raise HTTPException(status_code=400, detail="Falta frase3")

    fotos = [
        form.get("foto1"),
        form.get("foto2"),
        form.get("foto3"),
        form.get("foto4"),
        form.get("foto5"),
        form.get("foto6"),
    ]

    fotos = [f for f in fotos if f is not None and getattr(f, "filename", None)]

    if len(fotos) != 6:
        raise HTTPException(status_code=400, detail="Debes subir exactamente 6 fotos")

    order_id = str(uuid.uuid4())
    orden = None

    try:
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
            consent_confirmed=False,
            created_at=datetime.utcnow()
        )
        db.add(destinatario)
        db.commit()
        db.refresh(destinatario)

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

        folder = storage.order_photos_dir(order_id)
        os.makedirs(folder, exist_ok=True)

        saved_photos = []
        extensiones_validas = {".jpg", ".jpeg", ".png", ".webp"}

        for i, foto in enumerate(fotos, start=1):
            extension = os.path.splitext(foto.filename)[1].lower()

            if extension not in extensiones_validas:
                raise HTTPException(
                    status_code=400,
                    detail=f"La foto {i} debe ser JPG, JPEG, PNG o WEBP"
                )

            nombre_archivo = f"foto_{i}{extension}"
            path = os.path.join(folder, nombre_archivo)

            contenido = await foto.read()
            if not contenido:
                raise HTTPException(
                    status_code=400,
                    detail=f"La foto {i} está vacía"
                )

            with open(path, "wb") as f:
                f.write(contenido)

            saved_photos.append(nombre_archivo)

        orden.photos_json = storage.photos_json(saved_photos)
        db.commit()
        db.refresh(orden)

        video_ok = False
        video_error = None
        video_url = None

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

            if not final_video_path:
                raise Exception("El generador no devolvió una ruta de vídeo")

            if not os.path.exists(final_video_path):
                raise Exception("El archivo de vídeo no fue encontrado en disco")

            orden.final_video_path = final_video_path
            orden.state = "video_generated"
            db.commit()
            db.refresh(orden)

            video_ok = True
            video_url = f"/video/{orden.id}"

        except Exception as e:
            orden.state = "video_error"
            db.commit()
            video_error = str(e)

        success_html = f"""
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
                h1 {{
                    margin-top: 0;
                }}
                p {{
                    color: #ddd;
                    line-height: 1.6;
                }}
                .ok {{
                    color: #9fe870;
                    font-weight: bold;
                }}
                .error {{
                    color: #ff9a9a;
                    font-weight: bold;
                }}
                a.button {{
                    display: inline-block;
                    margin-top: 14px;
                    padding: 12px 18px;
                    border-radius: 999px;
                    background: #e7c27d;
                    color: black;
                    font-weight: bold;
                    text-decoration: none;
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
                <h1>ETERNA creada</h1>
                <p class="ok">Tu recuerdo se ha guardado correctamente.</p>

                <p><strong>Order ID:</strong> <code>{orden.id}</code></p>
                <p><strong>Slug:</strong> <code>{orden.public_slug}</code></p>
                <p><strong>Estado:</strong> <code>{orden.state}</code></p>

                {"<p class='ok'>Vídeo generado correctamente.</p>" if video_ok else ""}
                {f"<p class='error'>El pedido se creó, pero el vídeo no se pudo generar todavía.</p><p><strong>Error:</strong> <code>{video_error}</code></p>" if video_error else ""}
                {f"<a class='button' href='{video_url}' target='_blank'>Ver vídeo</a>" if video_ok and video_url else ""}

                <p style="margin-top:20px;">
                    <a class="button" href="/">Crear otra ETERNA</a>
                </p>
            </div>
        </body>
        </html>
        """

        return HTMLResponse(content=success_html)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()

        if orden:
            try:
                orden_db = db.query(EternaOrder).filter(EternaOrder.id == order_id).first()
                if orden_db:
                    orden_db.state = "error"
                    db.commit()
            except Exception:
                db.rollback()

        return HTMLResponse(
            content=f"""
            <!DOCTYPE html>
            <html lang="es">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Error ETERNA</title>
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
                    a.button {{
                        display: inline-block;
                        margin-top: 14px;
                        padding: 12px 18px;
                        border-radius: 999px;
                        background: #e7c27d;
                        color: black;
                        font-weight: bold;
                        text-decoration: none;
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
                    <p class="error">Ha ocurrido un problema.</p>
                    <p><strong>Detalle:</strong> <code>{str(e)}</code></p>
                    <a class="button" href="/">Volver</a>
                </div>
            </body>
            </html>
            """,
            status_code=500
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
            "fecha": o.created_at.isoformat() if o.created_at else None,
            "final_video_path": o.final_video_path
        })

    return resultado


@app.get("/orders/{order_id}")
def order_detail(order_id: str, db: Session = Depends(get_db)):
    o = db.query(EternaOrder).filter(EternaOrder.id == order_id).first()

    if not o:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    return {
        "id": o.id,
        "estado": o.state,
        "cliente": {
            "nombre": o.customer.name if o.customer else None,
            "email": o.customer.email if o.customer else None,
            "telefono": o.customer.phone if o.customer else None,
        },
        "destinatario": {
            "nombre": o.recipient.name if o.recipient else None,
            "telefono": o.recipient.phone if o.recipient else None,
            "consent_confirmed": o.recipient.consent_confirmed if o.recipient else None,
        },
        "frases": [o.phrase_1, o.phrase_2, o.phrase_3],
        "photos_json": o.photos_json,
        "final_video_path": o.final_video_path,
        "fecha": o.created_at.isoformat() if o.created_at else None
    }


@app.get("/video/{order_id}", response_class=HTMLResponse)
def video_page(order_id: str, db: Session = Depends(get_db)):
    o = db.query(EternaOrder).filter(EternaOrder.id == order_id).first()

    if not o:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    if not o.final_video_path:
        raise HTTPException(status_code=404, detail="Vídeo no generado")

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

    if not o:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    if not o.final_video_path:
        raise HTTPException(status_code=404, detail="Vídeo no generado")

    if not os.path.exists(o.final_video_path):
        raise HTTPException(status_code=404, detail="Archivo de vídeo no encontrado")

    return FileResponse(
        path=o.final_video_path,
        media_type="video/mp4",
        filename=f"{order_id}.mp4"
    )
