import os
import uuid
import urllib.parse
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import stripe

# =========================
# CONFIG
# =========================

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000")

BASE_PRICE = float(os.getenv("ETERNA_BASE_PRICE_EUR", "29"))
CURRENCY = os.getenv("ETERNA_CURRENCY", "eur")
COMMISSION = float(os.getenv("GIFT_COMMISSION_RATE", "0.05"))

stripe.api_key = STRIPE_SECRET_KEY

app = FastAPI()

# memoria temporal (luego base de datos)
orders = {}

# =========================
# HOME
# =========================

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
    <body style="background:black;color:white;font-family:Arial;padding:40px;text-align:center;">
        <h1>ETERNA</h1>

        <form action="/crear-eterna" method="post">

            <input name="customer_name" placeholder="Tu nombre"><br><br>
            <input name="customer_email" placeholder="Tu email"><br><br>
            <input name="customer_phone" placeholder="Tu teléfono"><br><br>

            <input name="recipient_name" placeholder="Nombre receptor"><br><br>
            <input name="recipient_phone" placeholder="Teléfono receptor"><br><br>

            <input name="phrase_1" placeholder="Frase 1"><br><br>
            <input name="phrase_2" placeholder="Frase 2"><br><br>
            <input name="phrase_3" placeholder="Frase 3"><br><br>

            <input name="gift_amount" placeholder="Dinero a regalar (€)" type="number" step="0.01"><br><br>

            <button type="submit">CREAR MI ETERNA</button>
        </form>
    </body>
    </html>
    """

# =========================
# CREAR ETERNA + STRIPE
# =========================

@app.post("/crear-eterna")
async def crear_eterna(
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

    # 💰 cálculo dinero
    gift_commission = gift_amount * COMMISSION
    total = BASE_PRICE + gift_amount + gift_commission

    # guardar pedido
    orders[order_id] = {
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
        "paid": False
    }

    # 💳 Stripe checkout
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": CURRENCY,
                "product_data": {
                    "name": "ETERNA"
                },
                "unit_amount": int(total * 100),
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=f"{PUBLIC_BASE_URL}/post-pago/{order_id}",
        cancel_url=f"{PUBLIC_BASE_URL}/"
    )

    return RedirectResponse(session.url)

# =========================
# POST PAGO
# =========================

@app.get("/post-pago/{order_id}")
def post_pago(order_id: str):
    order = orders.get(order_id)

    if not order:
        return {"detail": "Pedido no encontrado"}

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

    mensaje = urllib.parse.quote(f"""
Hola ❤️

{order['customer_name']} te ha enviado algo especial.

👉 {PUBLIC_BASE_URL}/pedido/{order_id}
""")

    whatsapp_url = f"https://wa.me/{order['recipient_phone']}?text={mensaje}"

    return f"""
    <html>
    <body style="background:black;color:white;font-family:Arial;padding:40px;">
        <h1>Resumen ETERNA</h1>

        <p><b>Estado:</b> {"Pagado" if order["paid"] else "Pendiente"}</p>

        <hr>

        <p><b>Regalante:</b> {order['customer_name']}</p>
        <p><b>Receptor:</b> {order['recipient_name']}</p>

        <p>Frase 1: {order['phrase_1']}</p>
        <p>Frase 2: {order['phrase_2']}</p>
        <p>Frase 3: {order['phrase_3']}</p>

        <hr>

        <p>ETERNA: {BASE_PRICE}€</p>
        <p>Regalo: {order['gift_amount']}€</p>
        <p>Comisión: {round(order['gift_commission'],2)}€</p>
        <p><b>Total: {round(order['total'],2)}€</b></p>

        <br>

        <a href="/pedido/{order_id}">
            <button>VER TU ETERNA</button>
        </a>

        <a href="{whatsapp_url}">
            <button>ENVIAR POR WHATSAPP</button>
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
        return "No existe"

    return f"""
    <html>
    <body style="background:black;color:white;text-align:center;padding-top:100px;">
        <h1>Hay algo para ti</h1>
        <p>{order['phrase_1']}</p>
        <p>{order['phrase_2']}</p>
        <p>{order['phrase_3']}</p>
    </body>
    </html>
    """
