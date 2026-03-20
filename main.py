import os
import uuid
import urllib.parse

from fastapi import FastAPI, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
import stripe

# =========================
# CONFIG
# =========================

app = FastAPI()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

BASE_URL = os.getenv("PUBLIC_BASE_URL")

BASE_PRICE = float(os.getenv("ETERNA_BASE_PRICE", 29))
COMMISSION = float(os.getenv("GIFT_COMMISSION_RATE", 0.05))

orders = {}

# =========================
# HOME
# =========================

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
    <body style="background:black;color:white;font-family:Arial;padding:40px;">
        <h1>ETERNA</h1>

        <form action="/crear-eterna" method="post">

            <h3>Tu</h3>
            <input name="customer_name" placeholder="Nombre"><br><br>
            <input name="customer_email" placeholder="Email"><br><br>
            <input name="customer_phone" placeholder="Teléfono"><br><br>

            <h3>Persona que recibe</h3>
            <input name="recipient_name" placeholder="Nombre"><br><br>
            <input name="recipient_phone" placeholder="Teléfono"><br><br>

            <h3>Mensaje</h3>
            <input name="phrase_1" placeholder="Frase 1"><br><br>
            <input name="phrase_2" placeholder="Frase 2"><br><br>
            <input name="phrase_3" placeholder="Frase 3"><br><br>

            <h3>💸 Dinero que quieres regalar</h3>
            <input name="gift_amount" placeholder="Ej: 20"><br><br>

            <button type="submit">CREAR MI ETERNA</button>
        </form>
    </body>
    </html>
    """

# =========================
# CREAR ETERNA (CLAVE 🔥)
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
    gift_amount: float = Form(0)
):

    order_id = str(uuid.uuid4())[:12]

    # 💸 cálculo
    gift = gift_amount
    commission = gift * COMMISSION
    total = BASE_PRICE + gift + commission

    # guardar
    orders[order_id] = {
        "customer_name": customer_name,
        "customer_email": customer_email,
        "customer_phone": customer_phone,
        "recipient_name": recipient_name,
        "recipient_phone": recipient_phone,
        "phrase_1": phrase_1,
        "phrase_2": phrase_2,
        "phrase_3": phrase_3,
        "gift": gift,
        "commission": commission,
        "total": total,
        "paid": False
    }

    # 💳 STRIPE DINÁMICO
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "eur",
                "product_data": {
                    "name": "ETERNA"
                },
                "unit_amount": int(total * 100)
            },
            "quantity": 1
        }],
        mode="payment",
        success_url=f"{BASE_URL}/post-pago?order_id={order_id}",
        cancel_url=f"{BASE_URL}/"
    )

    return RedirectResponse(session.url)

# =========================
# POST PAGO (CLAVE 🔥🔥🔥)
# =========================

@app.get("/post-pago")
def post_pago(order_id: str):

    order = orders.get(order_id)

    if not order:
        raise HTTPException(404, "Pedido no encontrado")

    order["paid"] = True

    return RedirectResponse(f"/resumen/{order_id}")

# =========================
# RESUMEN
# =========================

@app.get("/resumen/{order_id}", response_class=HTMLResponse)
def resumen(order_id: str):

    order = orders.get(order_id)

    if not order:
        return "Pedido no encontrado"

    whatsapp_msg = urllib.parse.quote(f"""
Hola ❤️

{order["customer_name"]} te ha enviado una ETERNA.

Ábrela aquí:
{BASE_URL}/pedido/{order_id}
""")

    whatsapp_link = f"https://wa.me/{order['recipient_phone']}?text={whatsapp_msg}"

    return f"""
    <html>
    <body style="background:black;color:white;font-family:Arial;padding:40px;">

        <h1>Resumen ETERNA</h1>

        <p>Estado: {"Pagado" if order["paid"] else "Pendiente"}</p>

        <h3>💸 Pago</h3>
        <p>ETERNA: {BASE_PRICE}€</p>
        <p>Regalo: {order["gift"]}€</p>
        <p>Comisión: {round(order["commission"],2)}€</p>
        <p><b>Total: {round(order["total"],2)}€</b></p>

        <br>

        <a href="/pedido/{order_id}">
            <button>VER TU ETERNA</button>
        </a>

        <a href="{whatsapp_link}">
            <button style="background:green;color:white;">ENVIAR POR WHATSAPP</button>
        </a>

    </body>
    </html>
    """

# =========================
# EXPERIENCIA (SIMPLIFICADA)
# =========================

@app.get("/pedido/{order_id}", response_class=HTMLResponse)
def ver_eterna(order_id: str):

    order = orders.get(order_id)

    if not order:
        return "No existe"

    return f"""
    <html>
    <body style="background:black;color:white;text-align:center;padding-top:100px;">
        <h1>Hay algo para ti</h1>
        <p>{order["phrase_1"]}</p>
        <p>{order["phrase_2"]}</p>
        <p>{order["phrase_3"]}</p>
    </body>
    </html>
    """
