import os
import json
import uuid
from pathlib import Path
from typing import List

import stripe
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles


# =========================================================
# CONFIGURACIÓN
# =========================================================

app = FastAPI(title="ETERNA backend")

BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"
PENDIENTES_DIR = STORAGE_DIR / "pendientes"
ORDENES_DIR = STORAGE_DIR / "ordenes"
MEDIA_DIR = STORAGE_DIR / "media"

PENDIENTES_DIR.mkdir(parents=True, exist_ok=True)
ORDENES_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
BASE_URL = os.getenv("BASE_URL", "").rstrip("/")

if not STRIPE_SECRET_KEY:
    print("⚠️ Falta STRIPE_SECRET_KEY en variables de entorno")

if not STRIPE_WEBHOOK_SECRET:
    print("⚠️ Falta STRIPE_WEBHOOK_SECRET en variables de entorno")

if not BASE_URL:
    print("⚠️ Falta BASE_URL en variables de entorno")

stripe.api_key = STRIPE_SECRET_KEY


# =========================================================
# FUNCIONES AUXILIARES
# =========================================================

def guardar_datos_pendientes(data: dict, archivos_fotos: List[tuple]) -> str:
    eterna_id = str(uuid.uuid4())
    carpeta = PENDIENTES_DIR / eterna_id
    carpeta.mkdir(parents=True, exist_ok=True)

    carpeta_fotos = carpeta / "fotos"
    carpeta_fotos.mkdir(parents=True, exist_ok=True)

    fotos_guardadas = []

    for i, (nombre_original, contenido) in enumerate(archivos_fotos, start=1):
        extension = Path(nombre_original).suffix.lower() or ".jpg"
        nombre_archivo = f"foto_{i}{extension}"
        ruta_archivo = carpeta_fotos / nombre_archivo

        with open(ruta_archivo, "wb") as f:
            f.write(contenido)

        fotos_guardadas.append(str(ruta_archivo))

    data["fotos_guardadas"] = fotos_guardadas

    with open(carpeta / "data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return eterna_id


def cargar_datos_pendientes(eterna_id: str) -> dict:
    archivo = PENDIENTES_DIR / eterna_id / "data.json"
    if not archivo.exists():
        raise FileNotFoundError(f"No existe data.json para {eterna_id}")

    with open(archivo, "r", encoding="utf-8") as f:
        return json.load(f)


def guardar_datos_pendientes_actualizados(eterna_id: str, data: dict) -> None:
    archivo = PENDIENTES_DIR / eterna_id / "data.json"
    with open(archivo, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def mover_pendiente_a_orden(eterna_id: str) -> Path:
    carpeta_pendiente = PENDIENTES_DIR / eterna_id
    carpeta_orden = ORDENES_DIR / eterna_id

    if not carpeta_pendiente.exists():
        raise FileNotFoundError(f"No existe carpeta pendiente para {eterna_id}")

    if carpeta_orden.exists():
        return carpeta_orden

    carpeta_pendiente.rename(carpeta_orden)
    return carpeta_orden


def crear_video_temporal(carpeta_orden: Path) -> str:
    """
    Temporal.
    Aquí luego pondremos el generador real del vídeo.
    """
    archivo_salida = carpeta_orden / "video_generado.txt"
    with open(archivo_salida, "w", encoding="utf-8") as f:
        f.write("VIDEO GENERADO CORRECTAMENTE PARA ETERNA\n")

    return str(archivo_salida)


def construir_url_base(request: Request) -> str:
    if BASE_URL:
        return BASE_URL
    return str(request.base_url).rstrip("/")


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
          max-width: 760px;
          margin: 0 auto;
          padding: 30px 20px;
        }
        h1 {
          letter-spacing: 3px;
          margin-bottom: 12px;
        }
        p {
          line-height: 1.5;
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
          font-size: 16px;
        }
        textarea {
          min-height: 95px;
          resize: vertical;
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
      <p>Sube tus fotos, escribe tus frases y completa el pago.</p>

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

      <p class="small">Al pagar, tu pedido quedará confirmado automáticamente.</p>
    </body>
    </html>
    """


# =========================================================
# PREPARAR PAGO: GUARDA DATOS Y CREA SESIÓN REAL DE STRIPE
# =========================================================

@app.post("/preparar-pago")
async def preparar_pago(
    request: Request,
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
        if not contenido:
            continue
        archivos_fotos.append((foto.filename or "foto.jpg", contenido))

    if len(archivos_fotos) < 1:
        raise HTTPException(status_code=400, detail="No se pudo leer ninguna foto.")

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
    url_base = construir_url_base(request)

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            customer_email=email_cliente,
            client_reference_id=eterna_id,
            metadata={
                "eterna_id": eterna_id,
                "nombre_cliente": nombre_cliente,
                "nombre_destinatario": nombre_destinatario
            },
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
                    "quantity": 1
                }
            ],
            success_url=f"{url_base}/gracias?eterna_id={eterna_id}",
            cancel_url=f"{url_base}/cancelado?eterna_id={eterna_id}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando sesión Stripe: {e}")

    return RedirectResponse(url=session.url, status_code=303)


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

        eterna_id = session.get("client_reference_id") or session.get("metadata", {}).get("eterna_id")
        email_pagado = session.get("customer_details", {}).get("email") or session.get("customer_email")
        payment_status = session.get("payment_status")

        if eterna_id and payment_status == "paid":
            try:
                data = cargar_datos_pendientes(eterna_id)
                data["payment_status"] = "paid"
                data["email_pagado"] = email_pagado or ""
                data["stripe_session_id"] = session.get("id", "")

                guardar_datos_pendientes_actualizados(eterna_id, data)

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
      <title>Pago completado</title>
      <style>
        body {{
          background: black;
          color: white;
          font-family: Arial, sans-serif;
          padding: 40px 20px;
          max-width: 700px;
          margin: 0 auto;
        }}
      </style>
    </head>
    <body>
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
      <style>
        body {{
          background: black;
          color: white;
          font-family: Arial, sans-serif;
          padding: 40px 20px;
          max-width: 700px;
          margin: 0 auto;
        }}
      </style>
    </head>
    <body>
      <h1>Pago cancelado</h1>
      <p>No se completó el pago de tu ETERNA.</p>
      <p>ID: {eterna_id}</p>
    </body>
    </html>
    """


# =========================================================
# SALUD Y DEBUG
# =========================================================

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/debug-pendientes")
def debug_pendientes():
    items = []
    for p in PENDIENTES_DIR.iterdir():
        if p.is_dir():
            items.append(p.name)
    return {"pendientes": items}


@app.get("/debug-ordenes")
def debug_ordenes():
    items = []
    for p in ORDENES_DIR.iterdir():
        if p.is_dir():
            items.append(p.name)
    return {"ordenes": items}


@app.get("/debug-eterna/{eterna_id}")
def debug_eterna(eterna_id: str):
    pendiente = PENDIENTES_DIR / eterna_id / "data.json"
    orden = ORDENES_DIR / eterna_id / "data.json"

    if pendiente.exists():
        with open(pendiente, "r", encoding="utf-8") as f:
            return JSONResponse(content=json.load(f))

    if orden.exists():
        with open(orden, "r", encoding="utf-8") as f:
            return JSONResponse(content=json.load(f))

    raise HTTPException(status_code=404, detail="ETERNA no encontrada")
