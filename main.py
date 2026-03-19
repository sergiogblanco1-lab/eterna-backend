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

def save_pending_data(data: dict, files_data: List[tuple]) -> str:
    """
    Guarda datos y fotos antes del pago.
    files_data = [(filename, bytes), ...]
    """
    eterna_id = str(uuid.uuid4())
    folder = PENDING_DIR / eterna_id
    folder.mkdir(parents=True, exist_ok=True)

    photos_dir = folder / "photos"
    photos_dir.mkdir(exist_ok=True)

    saved_photos = []

    for i, (filename, content) in enumerate(files_data, start=1):
        ext = Path(filename).suffix.lower() or ".jpg"
        clean_name = f"foto_{i}{ext}"
        photo_path = photos_dir / clean_name

        with open(photo_path, "wb") as f:
            f.write(content)

        saved_photos.append(str(photo_path))

    data["saved_photos"] = saved_photos

    with open(folder / "data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return eterna_id


def load_pending_data(eterna_id: str) -> dict:
    folder = PENDING_DIR / eterna_id
    data_file = folder / "data.json"

    if not data_file.exists():
        raise FileNotFoundError(f"No existe data.json para {eterna_id}")

    with open(data_file, "r", encoding="utf-8") as f:
        return json.load(f)


def move_pending_to_order(eterna_id: str) -> Path:
    pending_folder = PENDING_DIR / eterna_id
    order_folder = ORDERS_DIR / eterna_id

    if not pending_folder.exists():
        raise FileNotFoundError(f"No existe carpeta pending para {eterna_id}")

    if order_folder.exists():
        return order_folder

    pending_folder.rename(order_folder)
    return order_folder


def create_fake_video(order_folder: Path) -> str:
    """
    Placeholder temporal.
    Luego aquí meteremos el generador real del vídeo.
    """
    output_file = order_folder / "video_generado.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("VIDEO GENERADO CORRECTAMENTE PARA ETERNA\n")

    return str(output_file)


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
        <input type="text" name="customer_name" placeholder="Tu nombre" required>
        <input type="email" name="customer_email" placeholder="Tu email" required>
        <input type="text" name="customer_phone" placeholder="Tu teléfono">

        <input type="text" name="recipient_name" placeholder="Nombre de la persona que recibirá la ETERNA" required>
        <input type="text" name="recipient_phone" placeholder="Teléfono de la persona que la recibirá">

        <textarea name="phrase_1" placeholder="Frase 1" required></textarea>
        <textarea name="phrase_2" placeholder="Frase 2" required></textarea>
        <textarea name="phrase_3" placeholder="Frase 3" required></textarea>

        <input type="file" name="photos" accept="image/*" multiple required>

        <button type="submit">Crear mi ETERNA</button>
      </form>

      <p class="small">Después del pago, tu pedido quedará confirmado.</p>
    </body>
    </html>
    """


# =========================================================
# PASO 1: GUARDAR FORMULARIO Y REDIRIGIR A STRIPE
# =========================================================

@app.post("/preparar-pago")
async def preparar_pago(
    customer_name: str = Form(...),
    customer_email: str = Form(...),
    customer_phone: str = Form(""),
    recipient_name: str = Form(...),
    recipient_phone: str = Form(""),
    phrase_1: str = Form(...),
    phrase_2: str = Form(...),
    phrase_3: str = Form(...),
    photos: List[UploadFile] = File(...)
):
    if len(photos) < 1:
        raise HTTPException(status_code=400, detail="Debes subir al menos 1 foto.")

    if len(photos) > 10:
        raise HTTPException(status_code=400, detail="Máximo 10 fotos.")

    files_data = []
    for photo in photos:
        content = await photo.read()
        files_data.append((photo.filename, content))

    data = {
        "customer_name": customer_name,
        "customer_email": customer_email,
        "customer_phone": customer_phone,
        "recipient_name": recipient_name,
        "recipient_phone": recipient_phone,
        "phrase_1": phrase_1,
        "phrase_2": phrase_2,
        "phrase_3": phrase_3,
        "payment_status": "pending"
    }

    eterna_id = save_pending_data(data, files_data)

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
# OPCIONAL: CREAR CHECKOUT SESSION DESDE EL BACKEND
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
                            "description": "Video emocional personalizado"
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
        customer_email_paid = session.get("customer_details", {}).get("email")
        payment_status = session.get("payment_status")

        if eterna_id and payment_status == "paid":
            try:
                data = load_pending_data(eterna_id)
                data["payment_status"] = "paid"
                data["paid_email"] = customer_email_paid or ""

                pending_folder = PENDING_DIR / eterna_id
                with open(pending_folder / "data.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                order_folder = move_pending_to_order(eterna_id)
                create_fake_video(order_folder)

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


@app.get("/debug-pending")
def debug_pending():
    items = []
    for p in PENDING_DIR.iterdir():
        if p.is_dir():
            items.append(p.name)
    return {"pending": items}


@app.get("/debug-orders")
def debug_orders():
    items = []
    for p in ORDERS_DIR.iterdir():
        if p.is_dir():
            items.append(p.name)
    return {"orders": items}
