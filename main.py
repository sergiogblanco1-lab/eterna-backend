import os
import json
import uuid
from pathlib import Path
from typing import List

import stripe
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles


# =========================================================
# CONFIGURACIÓN
# =========================================================

app = FastAPI(title="ETERNA backend")

BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"
MEDIA_DIR = STORAGE_DIR / "media"
PENDING_DIR = STORAGE_DIR / "pending"
ORDERS_DIR = STORAGE_DIR / "orders"

MEDIA_DIR.mkdir(parents=True, exist_ok=True)
PENDING_DIR.mkdir(parents=True, exist_ok=True)
ORDERS_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PAYMENT_LINK = os.getenv(
    "STRIPE_PAYMENT_LINK",
    "https://buy.stripe.com/9B6dR9eDo3d91UBfjxaZi00"
)

stripe.api_key = STRIPE_SECRET_KEY


# =========================================================
# FUNCIONES AUXILIARES
# =========================================================

def guardar_datos_pendientes(data: dict, archivos_fotos: List[tuple]) -> str:
    """
    Guarda datos y fotos antes del pago.
    archivos_fotos = [(filename, bytes), ...]
    """
    eterna_id = str(uuid.uuid4())
    carpeta = PENDING_DIR / eterna_id
    carpeta.mkdir(parents=True, exist_ok=True)

    carpeta_fotos = carpeta / "photos"
    carpeta_fotos.mkdir(exist_ok=True)

    fotos_guardadas = []

    for i, (filename, content) in enumerate(archivos_fotos, start=1):
        ext = Path(filename).suffix.lower() or ".jpg"
        nombre_limpio = f"foto_{i}{ext}"
        ruta_foto = carpeta_fotos / nombre_limpio

        with open(ruta_foto, "wb") as f:
            f.write(content)

        fotos_guardadas.append(str(ruta_foto))

    data["fotos_guardadas"] = fotos_guardadas

    with open(carpeta / "data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return eterna_id


def cargar_datos_pendientes(eterna_id: str) -> dict:
    carpeta = PENDING_DIR / eterna_id
    archivo_data = carpeta / "data.json"

    if not archivo_data.exists():
        raise FileNotFoundError(f"No existe data.json para {eterna_id}")

    with open(archivo_data, "r", encoding="utf-8") as f:
        return json.load(f)


def mover_pendiente_a_orden(eterna_id: str) -> Path:
    carpeta_pendiente = PENDING_DIR / eterna_id
    carpeta_orden = ORDERS_DIR / eterna_id

    if not carpeta_pendiente.exists():
        raise FileNotFoundError(f"No existe carpeta pending para {eterna_id}")

    if carpeta_orden.exists():
        return carpeta_orden

    carpeta_pendiente.rename(carpeta_orden)
    return carpeta_orden


def crear_video_temporal(carpeta_orden: Path) -> str:
    """
    Temporal.
    Luego aquí meteremos el generador real del vídeo.
    """
    archivo_salida = carpeta_orden / "video_generado.txt"
    with open(archivo_salida, "w", encoding="utf-8") as f:
        f.write("VIDEO GENERADO CORRECTAMENTE PARA ETERNA\n")

    return str(archivo_salida)


# =========================================================
# HOME
# =========================================================

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
          max-width: 700px;
          margin: 0 auto;
          padding: 30px 20px;
        }
        h1 {
          letter-spacing: 3px;
        }
        input, textarea, button {
          width: 100%;
          margin-bottom: 14px;
          padding: 12px;
          border-radius: 10px;
          border: 1px solid #333;
          background: #161616;
          color: white;
          box-sizing: border-box;
        }
        button {
          background: white;
          color: black;
          font-weight: bold;
          cursor: pointer;
        }
        .small {
          opacity: 0.75;
          font-size: 14px;
        }
      </style>
    </head>
    <body>
      <h1>ETERNA</h1>
      <p>Sube tus fotos, escribe tus frases y pasa al pago.</p>

      <form action="/preparar-pago" method="post" enctype="multipart/form-data">
        <input type="text" name="nombre_cliente" placeholder="Tu nombre" required>
        <input type="email" name="email_cliente" placeholder="Tu email" required>
        <input type="text" name="telefono_cliente" placeholder="Tu teléfono">

        <input type="text" name="nombre_destinatario" placeholder="Nombre de quien recibirá la ETERNA" required>
        <input type="text" name="telefono_destinatario" placeholder="Teléfono de quien la recibirá">

        <textarea name="frase_1" placeholder="Frase 1" required></textarea>
        <textarea name="frase_2" placeholder="Frase 2" required></textarea>
        <textarea name="frase_3" placeholder="Frase 3" required></textarea>

        <input type="file" name="fotos" accept="image/*" multiple required>

        <button type="submit">Crear mi ETERNA</button>
      </form>

      <p class="small">Después del pago, tu pedido quedará confirmado.</p>
    </body>
    </html>
    """


# =========================================================
# GUARDAR FORMULARIO Y REDIRIGIR A STRIPE
# =========================================================

@app.post("/preparar-pago")
async def preparar_pago(
    nombre_cliente: str = Form(...),
    email_cliente: str = Form(...),
    telefono_cliente: str = Form(""),
    nombre_destinatario: str = Form(...),
    telefono_destinatario: str = Form(""),
    frase_1: str = Form(...),
    frase_2: str = Form(...),
    frase_3: str = Form(...),
    fotos: List[UploadFile] = File(...)
):
    if len(fotos) < 1:
        raise HTTPException(status_code=400, detail="Debes subir al menos 1 foto.")

    if len(fotos) > 10:
        raise HTTPException(status_code=400, detail="Máximo 10 fotos.")

    archivos_fotos = []
    for foto in fotos:
        contenido = await foto.read()
        archivos_fotos.append((foto.filename, contenido))

    data = {
        "nombre_cliente": nombre_cliente,
        "email_cliente": email_cliente,
        "telefono_cliente": telefono_cliente,
        "nombre_destinatario": nombre_destinatario,
        "telefono_destinatario": telefono_destinatario,
        "frase_1": frase_1,
        "frase_2": frase_2,
        "frase_3": frase_3,
        "payment_status": "pending"
    }

    eterna_id = guardar_datos_pendientes(data, archivos_fotos)

    payment_url = f"{STRIPE_PAYMENT_LINK}?client_reference_id={eterna_id}"

    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
      <meta charset="UTF-8">
      <meta http-equiv="refresh" content="0; url={payment_url}">
      <title>Redirigiendo...</title>
    </head>
    <body style="background:black;color:white;font-family:Arial;padding:40px;">
      <p>Redirigiendo a Stripe...</p>
      <p>Si no pasa automáticamente, pulsa aquí:</p>
      <a href="{payment_url}" style="color:white;">Ir al pago</a>
    </body>
    </html>
    """)


# =========================================================
# OPCIONAL: CREAR CHECKOUT SESSION DESDE BACKEND
# =========================================================

@app.post("/crear-checkout-session")
async def crear_checkout_session(request: Request):
    try:
        body = await request.json()
        eterna_id = body.get("eterna_id")

        if not eterna_id:
            raise HTTPException(status_code=400, detail="Falta eterna_id.")

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": "eur",
                        "product_data": {
                            "name": "ETERNA",
                            "description": "Vídeo emocional personalizado"
                        },
                        "unit_amount": 4900
                    },
                    "quantity": 1,
                }
            ],
            client_reference_id=eterna_id,
            success_url=f"{request.base_url}gracias?eterna_id={eterna_id}",
            cancel_url=f"{request.base_url}cancelado?eterna_id={eterna_id}",
        )

        return {"checkout_url": session.url}

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# =========================================================
# WEBHOOK DE STRIPE
# =========================================================

@app.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Payload inválido.")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Firma webhook inválida.")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        eterna_id = session.get("client_reference_id")
        email_pagado = session.get("customer_details", {}).get("email")
        payment_status = session.get("payment_status")

        if eterna_id and payment_status == "paid":
            try:
                data = cargar_datos_pendientes(eterna_id)
                data["payment_status"] = "paid"
                data["email_pagado"] = email_pagado or ""

                carpeta_pendiente = PENDING_DIR / eterna_id
                with open(carpeta_pendiente / "data.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                carpeta_orden = mover_pendiente_a_orden(eterna_id)
                crear_video_temporal(carpeta_orden)

                print(f"✅ PAGO CONFIRMADO - ETERNA {eterna_id}")

            except Exception as e:
                print(f"❌ ERROR procesando pago {eterna_id}: {e}")

    return {"status": "ok"}


# =========================================================
# PÁGINAS DE RESULTADO
# =========================================================

@app.get("/gracias", response_class=HTMLResponse)
def gracias(eterna_id: str = ""):
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
      <meta charset="UTF-8">
      <title>Gracias</title>
    </head>
    <body style="background:black;color:white;font-family:Arial;padding:40px;">
      <h1>Pago completado</h1>
      <p>Tu ETERNA ha sido confirmada correctamente.</p>
      <p>ID: {eterna_id}</p>
    </body>
    </html>
    """


@app.get("/cancelado", response_class=HTMLResponse)
def cancelado(eterna_id: str = ""):
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
      <meta charset="UTF-8">
      <title>Pago cancelado</title>
    </head>
    <body style="background:black;color:white;font-family:Arial;padding:40px;">
      <h1>Pago cancelado</h1>
      <p>No se completó el pago de tu ETERNA.</p>
      <p>ID: {eterna_id}</p>
    </body>
    </html>
    """


# =========================================================
# RUTAS DE PRUEBA
# =========================================================

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/debug-pendientes")
def debug_pendientes():
    items = []
    for p in PENDING_DIR.iterdir():
        if p.is_dir():
            items.append(p.name)
    return {"pendientes": items}


@app.get("/debug-ordenes")
def debug_ordenes():
    items = []
    for p in ORDERS_DIR.iterdir():
        if p.is_dir():
            items.append(p.name)
    return {"ordenes": items}
