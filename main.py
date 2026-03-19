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

if not STRIPE_PAYMENT_LINK:
    print("❌ Falta STRIPE_PAYMENT_LINK")

stripe.api_key = STRIPE_SECRET_KEY

# memoria simple (luego BD)
ORDERS = {}

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
    order_id = str(uuid.uuid4())

    ORDERS[order_id] = {
        "paid": False,
        "customer_name": customer_name,
        "recipient_name": recipient_name,
        "recipient_phone": recipient_phone,
        "phrases": [phrase_1, phrase_2, phrase_3]
    }

    success_url = f"{PUBLIC_URL}/pedido/{order_id}"

    payment_url = (
        f"{STRIPE_PAYMENT_LINK}"
        f"?client_reference_id={urllib.parse.quote(order_id)}"
        f"&redirect_url={urllib.parse.quote(success_url)}"
    )

    print("🆕 Pedido creado:", order_id)
    print("➡️ Redirigiendo a Stripe:", payment_url)

    return HTMLResponse(f"""
    <html>
        <body style="background:black;color:white;text-align:center;padding-top:100px;">
            <h1>Redirigiendo a pago...</h1>
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

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        order_id = session.get("client_reference_id")

        print("💰 Pago completado:", order_id)

        if order_id in ORDERS:
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
        <body style="background:black;color:white;text-align:center;padding-top:100px;">
            <h1>Pedido no encontrado</h1>
        </body>
        </html>
        """)

    if not order["paid"]:
        return HTMLResponse("""
        <html>
        <body style="background:black;color:white;text-align:center;padding-top:100px;">
            <h1>Pago pendiente...</h1>
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
    <body style="background:black;color:white;text-align:center;padding-top:100px;">
        <h1>ETERNA lista 💔</h1>

        <a href="{link_whatsapp}" target="_blank">
            <button style="padding:20px;font-size:20px;background:green;color:white;border:none;border-radius:10px;">
                Enviar por WhatsApp
            </button>
        </a>
    </body>
    </html>
    """)

# =========================
# HOME
# =========================

@app.get("/")
def home():
    return {"status": "ETERNA funcionando"}
