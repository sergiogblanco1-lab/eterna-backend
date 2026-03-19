import uuid
import urllib.parse
import os

import stripe
from fastapi import FastAPI, Form, Request, HTTPException
from fastapi.responses import HTMLResponse

app = FastAPI(title="ETERNA backend")

# =========================
# CONFIG
# =========================

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
STRIPE_PAYMENT_LINK = os.getenv("STRIPE_PAYMENT_LINK")
PUBLIC_URL = os.getenv("PUBLIC_BASE_URL")

if not STRIPE_SECRET_KEY:
    print("❌ Falta STRIPE_SECRET_KEY")

if not STRIPE_WEBHOOK_SECRET:
    print("❌ Falta STRIPE_WEBHOOK_SECRET")

if not STRIPE_PAYMENT_LINK:
    print("❌ Falta STRIPE_PAYMENT_LINK")

if not PUBLIC_URL:
    print("❌ Falta PUBLIC_BASE_URL")

stripe.api_key = STRIPE_SECRET_KEY

# =========================
# MEMORIA SIMPLE (SOLO TEST)
# =========================

ORDERS = {}
LAST_ORDER_ID = None

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
    global LAST_ORDER_ID

    if not STRIPE_PAYMENT_LINK:
        raise HTTPException(status_code=500, detail="Falta STRIPE_PAYMENT_LINK")

    if not PUBLIC_URL:
        raise HTTPException(status_code=500, detail="Falta PUBLIC_BASE_URL")

    order_id = str(uuid.uuid4())
    LAST_ORDER_ID = order_id

    ORDERS[order_id] = {
        "paid": False,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "recipient_name": recipient_name,
        "recipient_phone": recipient_phone,
        "phrases": [phrase_1, phrase_2, phrase_3],
    }

    success_url = f"{PUBLIC_URL}/pedido/{order_id}"

    payment_url = (
        f"{STRIPE_PAYMENT_LINK}"
        f"?client_reference_id={urllib.parse.quote(order_id)}"
        f"&redirect_url={urllib.parse.quote(success_url)}"
    )

    print("🆕 Pedido creado:", order_id)
    print("➡️ Último pedido guardado:", LAST_ORDER_ID)
    print("➡️ Redirigiendo a Stripe:", payment_url)

    return HTMLResponse(f"""
    <html>
        <head>
            <meta charset="UTF-8">
            <title>ETERNA - Redirigiendo</title>
        </head>
        <body style="background:black;color:white;text-align:center;padding-top:100px;font-family:Arial,sans-serif;">
            <h1>Redirigiendo a pago...</h1>
            <p>Si no sales automáticamente, pulsa abajo:</p>
            <p>
                <a href="{payment_url}" style="color:white;font-size:18px;">
                    Ir a pagar
                </a>
            </p>
            <script>
                window.location.href = "{payment_url}";
            </script>
        </body>
    </html>
    """)

# =========================
# WEBHOOK STRIPE
# =========================

@app.post("/webhook")
async def stripe_webhook(request: Request):
    global LAST_ORDER_ID

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

        order_id = session.get("client_reference_id")

        print("💰 Pago completado. client_reference_id:", order_id)

        # Payment Link no siempre manda client_reference_id
        # Entonces para test usamos el último pedido creado
        if not order_id:
            print("⚠️ Stripe no devolvió order_id. Usando LAST_ORDER_ID para pruebas.")
            order_id = LAST_ORDER_ID

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
def ver_pedido(order_id: str):
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
            <p>Puede que el servidor se haya reiniciado o que el pedido aún no exista en memoria.</p>
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
# DEBUG PEDIDOS (SOLO TEST)
# =========================

@app.get("/debug/orders")
def debug_orders():
    return {
        "last_order_id": LAST_ORDER_ID,
        "orders": ORDERS
    }
