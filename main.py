import os
import uuid
import urllib.parse

import stripe
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI(title="ETERNA")

# =========================
# CONFIG
# =========================

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000").strip()

BASE_PRICE = float(os.getenv("ETERNA_BASE_PRICE", "29"))
CURRENCY = os.getenv("ETERNA_CURRENCY", "eur").strip().lower()
COMMISSION_RATE = float(os.getenv("GIFT_COMMISSION_RATE", "0.05"))

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# memoria temporal
orders: dict[str, dict] = {}

# =========================
# HOME
# =========================

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
                background: #000;
                color: #fff;
                font-family: Arial, sans-serif;
                padding: 40px;
                text-align: center;
            }
            input {
                width: min(420px, 90vw);
                padding: 12px;
                margin: 8px 0;
                border-radius: 10px;
                border: 1px solid #333;
                background: #111;
                color: white;
            }
            button {
                padding: 14px 22px;
                border-radius: 999px;
                border: 0;
                background: white;
                color: black;
                font-weight: bold;
                cursor: pointer;
                margin-top: 12px;
            }
        </style>
    </head>
    <body>
        <h1>ETERNA</h1>

        <form action="/crear-eterna" method="post">
            <input name="customer_name" placeholder="Tu nombre" required><br>
            <input name="customer_email" placeholder="Tu email" required><br>
            <input name="customer_phone" placeholder="Tu teléfono" required><br>

            <input name="recipient_name" placeholder="Nombre receptor" required><br>
            <input name="recipient_phone" placeholder="Teléfono receptor" required><br>

            <input name="phrase_1" placeholder="Frase 1" required><br>
            <input name="phrase_2" placeholder="Frase 2" required><br>
            <input name="phrase_3" placeholder="Frase 3" required><br>

            <input name="gift_amount" placeholder="Dinero a regalar (€)" type="number" step="0.01" min="0" value="0"><br>

            <button type="submit">CREAR MI ETERNA</button>
        </form>
    </body>
    </html>
    """

# =========================
# CREAR ETERNA
# =========================

@app.post("/crear-eterna")
def crear_eterna(
    customer_name: str = Form(...),
    customer_email: str = Form(...),
    customer_phone: str = Form(...),
    recipient_name: str = Form(...),
    recipient_phone: str = Form(...),
    phrase_1: str = Form(...),
    phrase_2: str = Form(...),
    phrase_3: str = Form(...),
    gift_amount: float = Form(0),
):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Falta STRIPE_SECRET_KEY.")

    order_id = str(uuid.uuid4())[:12]

    gift_amount = max(0.0, round(float(gift_amount or 0), 2))
    gift_commission = round(gift_amount * COMMISSION_RATE, 2)
    total = round(BASE_PRICE + gift_amount + gift_commission, 2)

    print("DEBUG gift_amount:", gift_amount)
    print("DEBUG gift_commission:", gift_commission)
    print("DEBUG total:", total)

    orders[order_id] = {
        "order_id": order_id,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "customer_phone": customer_phone,
        "recipient_name": recipient_name,
        "recipient_phone": recipient_phone,
        "phrase_1": phrase_1,
        "phrase_2": phrase_2,
        "phrase_3": phrase_3,
        "gift_amount": gift_amount,
        "gift_commission": gift_commission,
        "total": total,
        "paid": False,
        "stripe_session_id": None,
    }

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": CURRENCY,
                        "product_data": {
                            "name": "ETERNA",
                            "description": f"ETERNA {BASE_PRICE:.2f}€ + regalo {gift_amount:.2f}€ + comisión {gift_commission:.2f}€",
                        },
                        "unit_amount": int(round(total * 100)),
                    },
                    "quantity": 1,
                }
            ],
            success_url=f"{PUBLIC_BASE_URL}/post-pago?session_id={{CHECKOUT_SESSION_ID}}&order_id={order_id}",
            cancel_url=f"{PUBLIC_BASE_URL}/",
            client_reference_id=order_id,
            metadata={
                "order_id": order_id,
                "gift_amount": str(gift_amount),
                "gift_commission": str(gift_commission),
                "total": str(total),
            },
        )
    except Exception as e:
        print("DEBUG stripe error:", repr(e))
        raise HTTPException(status_code=500, detail=f"Error creando checkout Stripe: {e}")

    orders[order_id]["stripe_session_id"] = session.id

    return RedirectResponse(url=session.url, status_code=303)

# =========================
# POST PAGO
# =========================

@app.get("/post-pago")
def post_pago(session_id: str | None = None, order_id: str | None = None):
    print("DEBUG post-pago session_id:", session_id)
    print("DEBUG post-pago order_id:", order_id)

    # Primero intenta con order_id directo
    if order_id and order_id in orders:
        orders[order_id]["paid"] = True
        return RedirectResponse(url=f"/resumen/{order_id}", status_code=303)

    # Si no, intenta recuperar desde Stripe
    if session_id and STRIPE_SECRET_KEY:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            recovered_order_id = session.client_reference_id or session.metadata.get("order_id")
            print("DEBUG recovered_order_id:", recovered_order_id)

            if recovered_order_id and recovered_order_id in orders:
                orders[recovered_order_id]["paid"] = True
                return RedirectResponse(url=f"/resumen/{recovered_order_id}", status_code=303)
        except Exception as e:
            print("DEBUG error recuperando session:", repr(e))

    raise HTTPException(status_code=404, detail="Pedido no encontrado")

# =========================
# WEBHOOK
# =========================

@app.post("/webhook")
async def webhook(request: Request):
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Falta STRIPE_WEBHOOK_SECRET.")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=STRIPE_WEBHOOK_SECRET,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Payload inválido")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Firma inválida")

    print("DEBUG webhook event:", event["type"])

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        order_id = session.get("client_reference_id") or session.get("metadata", {}).get("order_id")

        print("DEBUG webhook order_id:", order_id)

        if order_id and order_id in orders:
            orders[order_id]["paid"] = True
            orders[order_id]["stripe_session_id"] = session.get("id")

    return {"ok": True}

# =========================
# RESUMEN
# =========================

@app.get("/resumen/{order_id}", response_class=HTMLResponse)
def resumen(order_id: str):
    order = orders.get(order_id)

    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    mensaje = urllib.parse.quote(
        f"Hola ❤️\n\n"
        f"{order['customer_name']} te ha enviado algo especial.\n\n"
        f"👉 {PUBLIC_BASE_URL}/pedido/{order_id}"
    )

    telefono = "".join(ch for ch in order["recipient_phone"] if ch.isdigit())
    whatsapp_url = f"https://wa.me/{telefono}?text={mensaje}"

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Resumen ETERNA</title>
        <style>
            body {{
                background: black;
                color: white;
                font-family: Arial, sans-serif;
                padding: 40px;
            }}
            button {{
                padding: 14px 22px;
                border-radius: 999px;
                border: 0;
                font-weight: bold;
                cursor: pointer;
                margin-right: 10px;
            }}
        </style>
    </head>
    <body>
        <h1>Resumen ETERNA</h1>

        <p><b>Estado:</b> {"Pagado" if order["paid"] else "Pendiente"}</p>

        <hr>

        <p><b>Regalante:</b> {order["customer_name"]}</p>
        <p><b>Receptor:</b> {order["recipient_name"]}</p>

        <p>Frase 1: {order["phrase_1"]}</p>
        <p>Frase 2: {order["phrase_2"]}</p>
        <p>Frase 3: {order["phrase_3"]}</p>

        <hr>

        <p>ETERNA: {BASE_PRICE:.2f}€</p>
        <p>Regalo: {order["gift_amount"]:.2f}€</p>
        <p>Comisión: {order["gift_commission"]:.2f}€</p>
        <p><b>Total: {order["total"]:.2f}€</b></p>

        <br>

        <a href="/pedido/{order_id}">
            <button>VER TU ETERNA</button>
        </a>

        <a href="{whatsapp_url}" target="_blank">
            <button style="background:green;color:white;">ENVIAR POR WHATSAPP</button>
        </a>
    </body>
    </html>
    """

# =========================
# EXPERIENCIA
# =========================

@app.get("/pedido/{order_id}", response_class=HTMLResponse)
def ver_eterna(order_id: str):
    order = orders.get(order_id)

    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ETERNA</title>
    </head>
    <body style="background:black;color:white;text-align:center;padding-top:100px;font-family:Arial;">
        <h1>Hay algo para ti</h1>
        <p>{order['phrase_1']}</p>
        <p>{order['phrase_2']}</p>
        <p>{order['phrase_3']}</p>
        <p style="margin-top:30px;">💸 Has recibido {order['gift_amount']:.2f}€</p>
    </body>
    </html>
    """
