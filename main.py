import uuid
from datetime import datetime

from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Customer, Recipient, EternaOrder


app = FastAPI(title="ETERNA backend")

Base.metadata.create_all(bind=engine)


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
        </style>
    </head>
    <body>
        <h1>ETERNA</h1>
        <p>Hay momentos que merecen quedarse para siempre.</p>

        <div class="box">
            <form action="/crear-eterna" method="post" enctype="multipart/form-data" novalidate>
                <input name="nombre" placeholder="Tu nombre">
                <input name="email" placeholder="Tu email">
                <input name="telefono_regalante" placeholder="Tu teléfono">

                <input name="nombre_destinatario" placeholder="Nombre destinatario">
                <input name="telefono_destinatario" placeholder="Teléfono destinatario">

                <textarea name="frase1" placeholder="Frase 1"></textarea>
                <textarea name="frase2" placeholder="Frase 2"></textarea>
                <textarea name="frase3" placeholder="Frase 3"></textarea>

                <label>Sube 6 fotos</label>
                <input name="foto1" type="file">
                <input name="foto2" type="file">
                <input name="foto3" type="file">
                <input name="foto4" type="file">
                <input name="foto5" type="file">
                <input name="foto6" type="file">

                <div class="note">Ahora solo guardamos el pedido en base de datos.</div>

                <button type="submit">Crear mi ETERNA</button>
            </form>
        </div>
    </body>
    </html>
    """


@app.get("/health")
def health():
    return {"status": "ok"}


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

        return f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Pedido guardado</title>
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
                <h1>Pedido guardado ✅</h1>
                <p class="ok">La base de datos ha guardado la ETERNA.</p>

                <p><strong>Order ID:</strong> <code>{orden.id}</code></p>
                <p><strong>Estado:</strong> <code>{orden.state}</code></p>
                <p><strong>Cliente:</strong> <code>{cliente.name}</code></p>
                <p><strong>Destinatario:</strong> <code>{destinatario.name}</code></p>

                <a class="button" href="/">Volver</a>
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
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
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
                <h1>Error guardando pedido</h1>
                <p class="error">Algo ha fallado.</p>
                <p><strong>Detalle:</strong> <code>{str(e)}</code></p>
                <a class="button" href="/">Volver</a>
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
            "created_at": o.created_at.isoformat() if o.created_at else None
        }
        for o in lista
    ]
