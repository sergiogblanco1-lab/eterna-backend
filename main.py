import os
import uuid
import urllib.parse
from typing import List, Optional

import stripe
from fastapi import FastAPI, Form, UploadFile, File, Request
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI(title="ETERNA")

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:10000")

stripe.api_key = STRIPE_SECRET_KEY

ORDERS = {}

BASE_PRICE = 29.0
COMMISSION_RATE = 0.05


def clean_phone(phone: str) -> str:
    return "".join(filter(str.isdigit, phone or ""))


def whatsapp_link(phone: str, url: str) -> str:
    msg = f"Hay algo para ti ❤️\n\nÁbrelo cuando estés en un momento tranquilo.\n\n👉 {url}"
    return f"https://wa.me/{clean_phone(phone)}?text={urllib.parse.quote(msg)}"


def parse_money(value: str) -> float:
    if not value:
        return 0.0
    value = value.replace("€", "").replace(",", ".").strip()
    try:
        return float(value)
    except:
        return 0.0


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
    send_money: str = Form("no"),
    money_amount: str = Form("0"),
    photos: Optional[List[UploadFile]] = File(None),
):

    money = parse_money(money_amount) if send_money == "si" else 0.0
    commission = round(money * COMMISSION_RATE, 2)

    order_id = str(uuid.uuid4())

    ORDERS[order_id] = {
        "paid": False,
        "recipient_phone": recipient_phone,
        "phrase_1": phrase_1,
        "phrase_2": phrase_2,
        "phrase_3": phrase_3,
        "money": money,
        "commission": commission,
    }

    # Stripe items
    line_items = [
        {
            "price_data": {
                "currency": "eur",
                "product_data": {"name": "ETERNA"},
                "unit_amount": int(BASE_PRICE * 100),
            },
            "quantity": 1,
        }
    ]

    if money > 0:
        line_items.append({
            "price_data": {
                "currency": "eur",
                "product_data": {"name": "Dinero regalo"},
                "unit_amount": int(money * 100),
            },
            "quantity": 1,
        })

        line_items.append({
            "price_data": {
                "currency": "eur",
                "product_data": {"name": "Comisión ETERNA (5%)"},
                "unit_amount": int(commission * 100),
            },
            "quantity": 1,
        })

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=line_items,
        mode="payment",
        customer_email=customer_email,
        success_url=f"{PUBLIC_BASE_URL}/pedido/{order_id}",
        cancel_url=f"{PUBLIC_BASE_URL}",
        metadata={"order_id": order_id},
    )

    return RedirectResponse(session.url, status_code=303)


@app.get("/pedido/{order_id}", response_class=HTMLResponse)
def pedido(order_id: str):

    order = ORDERS.get(order_id)

    if not order:
        return HTMLResponse("<h1>No existe</h1>")

    link = whatsapp_link(
        order["recipient_phone"],
        f"{PUBLIC_BASE_URL}/ver/{order_id}"
    )

    return HTMLResponse(f"""
    <html>
    <body style="background:black;color:white;text-align:center;padding-top:100px;">
        <h1>ETERNA lista</h1>
        <a href="{link}">
            <button style="padding:20px;background:green;color:white;">
                Enviar por WhatsApp
            </button>
        </a>
    </body>
    </html>
    """)


@app.get("/ver/{order_id}", response_class=HTMLResponse)
def ver(order_id: str):

    order = ORDERS.get(order_id)

    if not order:
        return HTMLResponse("<h1>No existe</h1>")

    money_html = ""
    if order["money"] > 0:
        money_html = f"<h2>+ {order['money']}€</h2>"

    return HTMLResponse(f"""
    <html>
    <body style="background:black;color:white;text-align:center;padding-top:100px;">
        <h1>ETERNA</h1>
        <p>{order["phrase_1"]}</p>
        <p>{order["phrase_2"]}</p>
        <p>{order["phrase_3"]}</p>
        {money_html}
    </body>
    </html>
    """)
