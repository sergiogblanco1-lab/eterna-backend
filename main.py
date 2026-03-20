import os
import uuid
import urllib.parse
from typing import List, Optional
from pathlib import Path

import stripe
from fastapi import FastAPI, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

# =========================
# CONFIG
# =========================

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
PUBLIC_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:10000")

stripe.api_key = STRIPE_SECRET_KEY

app = FastAPI(title="ETERNA")

# =========================
# STORAGE
# =========================

BASE_DIR = Path("storage")
MEDIA_DIR = BASE_DIR / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")

ORDERS = {}

# =========================
# HELPERS
# =========================

def clean_phone(phone):
    phone = "".join(filter(str.isdigit, phone))
    if phone.startswith("00"):
        phone = phone[2:]
    if phone.startswith("0"):
        phone = phone[1:]
    return phone

def whatsapp_link(phone, url):
    phone = clean_phone(phone)
    msg = f"""Hola ❤️

Alguien ha creado una ETERNA para ti.

Vívelo.

👉 {url}
"""
    return f"https://wa.me/{phone}?text={urllib.parse.quote(msg)}"

# =========================
# ROUTES
# =========================

@app.get("/")
def home():
    return {"status": "ETERNA funcionando"}


@app.post("/crear-eterna")
async def crear_eterna(
    customer_name: str = Form(...),
    customer_email: str = Form(...),
    recipient_name: str = Form(...),
    recipient_phone: str = Form(...),
    phrase_1: str = Form(...),
    phrase_2: str = Form(...),
    phrase_3: str = Form(...),
    amount: int = Form(...),
    photos: Optional[List[UploadFile]] = File(None),
):

    order_id = str(uuid.uuid4())

    # 💰 comisión 10%
    commission = int(amount * 0.10)
    total = amount + commission

    # guardar datos
    ORDERS[order_id] = {
        "paid": False,
        "recipient_phone": recipient_phone,
        "recipient_name": recipient_name,
        "phrase_1": phrase_1,
        "phrase_2": phrase_2,
        "phrase_3": phrase_3,
        "amount": amount,
        "commission": commission,
        "total": total
    }

    # STRIPE
    session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "eur",
                "product_data": {"name": "ETERNA"},
                "unit_amount": total * 100,
            },
            "quantity": 1,
        }],
        customer_email=customer_email,
        metadata={"order_id": order_id},
        success_url=f"{PUBLIC_URL}/pedido/{order_id}",
        cancel_url=f"{PUBLIC_URL}",
    )

    return RedirectResponse(session.url, status_code=303)


@app.post("/webhook")
async def webhook(request: Request):

    payload = await request.body()
    sig = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except:
        return {"error": "webhook"}

    if event["type"] == "checkout.session.completed":
        order_id = event["data"]["object"]["metadata"]["order_id"]

        if order_id in ORDERS:
            ORDERS[order_id]["paid"] = True

    return {"ok": True}


@app.get("/pedido/{order_id}", response_class=HTMLResponse)
def pedido(order_id: str):

    order = ORDERS.get(order_id)

    if not order:
        return HTMLResponse("<h1>No existe</h1>")

    if not order["paid"]:
        return HTMLResponse("<h1>Pago pendiente...</h1>")

    link = whatsapp_link(
        order["recipient_phone"],
        f"{PUBLIC_URL}/ver/{order_id}"
    )

    return HTMLResponse(f"""
    <html>
    <body style="background:black;color:white;text-align:center;padding-top:100px;">
        <h1>ETERNA lista</h1>

        <p>Regalo preparado para {order["recipient_name"]}</p>

        <a href="{link}">
            <button style="padding:20px;background:green;color:white;">
                Enviar por WhatsApp
            </button>
        </a>
    </body>
    </html>
    """)


@app.get("/ver/{order_id}", response_class=HTMLResponse)
def ver_eterna(order_id: str):

    order = ORDERS.get(order_id)

    if not order:
        return HTMLResponse("<h1>No existe</h1>")

    if not order["paid"]:
        return HTMLResponse("<h1>Aún no disponible</h1>")

    return HTMLResponse(f"""
    <html>
    <body style="
        background:black;
        color:white;
        text-align:center;
        font-family:Arial;
        padding-top:80px;
    ">
        <h1>ETERNA</h1>

        <p style="margin-top:20px;">
            Esto se está viviendo contigo ❤️
        </p>

        <div style="margin-top:40px;font-size:24px;">
            <p>{order["phrase_1"]}</p>
            <p>{order["phrase_2"]}</p>
            <p>{order["phrase_3"]}</p>
        </div>

        <h2 style="margin-top:60px;color:#00ff88;">
            Has recibido {order["amount"]}€
        </h2>

        <p style="margin-top:40px;">
            Tu momento ha sido vivido ❤️
        </p>
    </body>
    </html>
    """)
