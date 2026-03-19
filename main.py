import os
import uuid
import urllib.parse

import stripe
from fastapi import FastAPI, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI(title="ETERNA backend")

# =========================
# CONFIG
# =========================

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
PUBLIC_URL = os.getenv("PUBLIC_BASE_URL")

stripe.api_key = STRIPE_SECRET_KEY

if not STRIPE_SECRET_KEY:
    print("❌ Falta STRIPE_SECRET_KEY")

if not STRIPE_WEBHOOK_SECRET:
    print("❌ Falta STRIPE_WEBHOOK_SECRET")

if not PUBLIC_URL:
    print("❌ Falta PUBLIC_BASE_URL")

# =========================
# MEMORIA SIMPLE (TEST)
# =========================

ORDERS = {}

# =========================
# HOME
# =========================

@app.get("/")
def home():
    return {"status": "ETERNA funcionando"}

# =========================
# CREAR ETERNA
# =========================

@app.post("/crear-eterna")
async def crear_eterna(
    customer_name: str = Form(...),
    customer_email: str = Form(...),
    recipient_name: str = Form(...),
    recipient_phone: str = Form(...),
    phrase_1: str = Form(...),
    phrase_2: str = Form(...),
    phrase_3: str = Form(...)
):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Falta STRIPE_SECRET_KEY")

    if not PUBLIC_URL:
        raise HTTPException(status_code=500, detail="Falta PUBLIC_BASE_URL")

    order_id = str(uuid.uuid4())

    ORDERS[order_id] = {
        "paid": False,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "recipient_name": recipient_name,
        "recipient_phone": recipient_phone,
        "phrases": [phrase_1, phrase_2, phrase_3],
    }

    print("🆕 Pedido creado:", order_id)

    try:
        checkout_session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "eur",
                        "product_data": {
                            "name": "ETERNA RECUERDOS",
                            "description": "Recuerdo emocional creado a partir de tus fotos y frases.",
                        },
                        "unit_amount": 2900,  # 29,00 €
                    },
                    "quantity": 1,
                }
            ],
            customer_email=customer_email,
            metadata={
                "order_id": order_id,
                "customer_name": customer_name,
                "recipient_name": recipient_name,
                "recipient_phone": recipient_phone,
            },
            success_url=f"{PUBLIC_URL}/pedido/{order_id}?paid=1",
            cancel_url=f"{PUBLIC_URL}/pedido/{order_id}?cancelled=1",
        )
    except Exception as e:
        print("❌ Error creando Checkout Session:", e)
        raise HTTPException(status_code=500, detail="No se pudo crear la sesión de pago")

    print("➡️ Checkout Session creada:", checkout_session.id)
    print("➡️ URL Stripe:", checkout_session.url)

    return RedirectResponse(url=checkout_session.url, status_code=303)

# =========================
# WEBHOOK STRIPE
# =========================

@app.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        print("❌ Error verificando webhook:", e)
        raise HTTPException(status_code=400, detail="Webhook inválido")

    print("📩 Evento recibido:", event["type"])

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        metadata = session.get("metadata", {})
        order_id = metadata.get("order_id")

        print("💰 Pago completado. order_id:", order_id)

        if order_id and order_id in ORDERS:
            ORDERS[order_id]["paid"] = True
            print(f"✅ Pedido {order_id} marcado como pagado")
        else:
            print("⚠️ Pedido no encontrado en memoria")

    return {"status": "ok"}

# =========================
# PÁGINA PEDIDO
# =========================

@app.get("/pedido/{order_id}", response_class=HTMLResponse)
def ver_pedido(order_id: str, paid: int = 0, cancelled: int = 0):
    order = ORDERS.get(order_id)

    if not order:
        return HTMLResponse("""
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Pedido no encontrado</title>
        </head>
        <body style="background:black;color:white;text-align:center;padding-top:100px;font-family:Arial,sans-serif;">
            <h1>Pedido no encontrado</h1>
            <p>Puede que el servidor se haya reiniciado o que el pedido no exista ya en memoria.</p>
        </body>
        </html>
        """)

    if cancelled:
        return HTMLResponse(f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Pago cancelado</title>
        </head>
        <body style="background:black;color:white;text-align:center;padding-top:100px;font-family:Arial,sans-serif;">
            <h1>Pago cancelado</h1>
            <p>Tu pedido sigue guardado, pero no se ha completado el pago.</p>
            <p><strong>Pedido:</strong> {order_id}</p>
        </body>
        </html>
        """)

    if not order["paid"]:
        return HTMLResponse(f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Pago pendiente</title>
        </head>
        <body style="background:black;color:white;text-align:center;padding-top:100px;font-family:Arial,sans-serif;">
            <h1>Pago pendiente...</h1>
            <p>Tu pedido existe, pero todavía no aparece como pagado.</p>
            <p><strong>Pedido:</strong> {order_id}</p>
        </body>
        </html>
        """)

    telefono = "".join(filter(str.isdigit, order["recipient_phone"]))

    mensaje = f"""
Hola ❤️

Alguien ha creado algo muy especial para ti.

Ábrelo cuando estés en un momento tranquilo.

👉 https://eterna-video.com/{order_id}
"""

    link_whatsapp = f"https://wa.me/{telefono}?text={urllib.parse.quote(mensaje)}"

    return HTMLResponse(f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <title>ETERNA lista</title>
    </head>
    <body style="background:black;color:white;text-align:center;padding-top:100px;font-family:Arial,sans-serif;">
        <h1>ETERNA lista 💔</h1>
        <p>El pago se ha confirmado correctamente.</p>
        <p><strong>Pedido:</strong> {order_id}</p>

        <a href="{link_whatsapp}" target="_blank">
            <button style="padding:20px;font-size:20px;background:green;color:white;border:none;border-radius:10px;cursor:pointer;">
                Enviar por WhatsApp
            </button>
        </a>
    </body>
    </html>
    """)

# =========================
# DEBUG
# =========================

@app.get("/debug/orders")
def debug_orders():
    return ORDERS
