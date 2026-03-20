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

if not STRIPE_SECRET_KEY:
    print("❌ Falta STRIPE_SECRET_KEY")

if not STRIPE_WEBHOOK_SECRET:
    print("❌ Falta STRIPE_WEBHOOK_SECRET")

if not PUBLIC_URL:
    print("❌ Falta PUBLIC_BASE_URL")

stripe.api_key = STRIPE_SECRET_KEY

# =========================
# MEMORIA SIMPLE
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
    order_id = str(uuid.uuid4())

    ORDERS[order_id] = {
        "paid": False,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "recipient_name": recipient_name,
        "recipient_phone": recipient_phone,
        "phrase_1": phrase_1,
        "phrase_2": phrase_2,
        "phrase_3": phrase_3,
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
                            "name": "ETERNA",
                            "description": "Recuerdo emocional creado a partir de tus frases y recuerdos.",
                        },
                        "unit_amount": 2900,
                    },
                    "quantity": 1,
                }
            ],
            customer_email=customer_email,
            metadata={
                "order_id": order_id,
            },
            success_url=f"{PUBLIC_URL}/pedido/{order_id}?paid=1",
            cancel_url=f"{PUBLIC_URL}/pedido/{order_id}?cancelled=1",
        )
    except Exception as e:
        print("❌ Error Stripe:", e)
        raise HTTPException(status_code=500, detail="Error creando pago")

    print("➡️ Stripe session:", checkout_session.id)

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
        print("❌ Error webhook:", e)
        return {"status": "error"}

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        order_id = session.get("metadata", {}).get("order_id")

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
def ver_pedido(order_id: str, paid: int = 0, cancelled: int = 0):
    order = ORDERS.get(order_id)

    if not order:
        return HTMLResponse("""
        <html>
        <body style="background:black;color:white;text-align:center;padding-top:100px;font-family:Arial;">
            <h1>Pedido no encontrado</h1>
        </body>
        </html>
        """)

    if cancelled:
        return HTMLResponse("""
        <html>
        <body style="background:black;color:white;text-align:center;padding-top:100px;font-family:Arial;">
            <h1>Pago cancelado</h1>
        </body>
        </html>
        """)

    if not order["paid"]:
        return HTMLResponse("""
        <html>
        <body style="background:black;color:white;text-align:center;padding-top:100px;font-family:Arial;">
            <h1>Pago pendiente...</h1>
        </body>
        </html>
        """)

    telefono_original = order["recipient_phone"]
    telefono = "".join(filter(str.isdigit, telefono_original))

    # quitar 00 internacional si lo escriben así
    if telefono.startswith("00"):
        telefono = telefono[2:]

    # quitar 0 inicial local si lo escriben por costumbre
    if telefono.startswith("0"):
        telefono = telefono[1:]

    mensaje = (
        "Hola ❤️\n\n"
        "Alguien ha creado algo muy especial para ti.\n\n"
        "Ábrelo cuando estés en un momento tranquilo.\n\n"
        f"👉 https://eterna-v2-lab.onrender.com/pedido/{order_id}"
    )

    link_whatsapp = f"https://wa.me/{telefono}?text={urllib.parse.quote(mensaje)}"

    print("📱 Telefono original:", telefono_original)
    print("📱 Telefono limpio:", telefono)
    print("📱 Link WhatsApp:", link_whatsapp)

    return HTMLResponse(f"""
    <html>
    <body style="background:black;color:white;text-align:center;padding-top:100px;font-family:Arial;">
        <h1>ETERNA lista 💔</h1>

        <a href="{link_whatsapp}" target="_blank">
            <button style="padding:20px;font-size:20px;background:green;color:white;border:none;border-radius:10px;cursor:pointer;">
                Enviar por WhatsApp
            </button>
        </a>
    </body>
    </html>
    """)
