import os
import json
import uuid
import urllib.parse
from pathlib import Path

import stripe
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

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
ORDERS_DIR = BASE_DIR / "orders"

BASE_DIR.mkdir(parents=True, exist_ok=True)
ORDERS_DIR.mkdir(parents=True, exist_ok=True)

# =========================
# HELPERS
# =========================

def clean_phone(phone: str) -> str:
    phone = "".join(filter(str.isdigit, phone or ""))
    if phone.startswith("00"):
        phone = phone[2:]
    if phone.startswith("0"):
        phone = phone[1:]
    return phone

def whatsapp_link(phone: str, url: str) -> str:
    phone = clean_phone(phone)
    msg = f"""Hola ❤️

Alguien ha creado una ETERNA para ti.

Vívelo.

👉 {url}
"""
    return f"https://wa.me/{phone}?text={urllib.parse.quote(msg)}"

def order_path(order_id: str) -> Path:
    return ORDERS_DIR / f"{order_id}.json"

def save_order(order_id: str, data: dict) -> None:
    with open(order_path(order_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_order(order_id: str):
    path = order_path(order_id)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# =========================
# HOME
# =========================

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
    <body style="background:black;color:white;text-align:center;padding-top:80px;font-family:Arial;">
        <h1>ETERNA</h1>
        <p>Crea una ETERNA</p>

        <form action="/crear-eterna" method="post">
            <input name="customer_name" placeholder="Tu nombre"><br><br>
            <input name="customer_email" placeholder="Tu email"><br><br>
            <input name="recipient_name" placeholder="Nombre destinatario"><br><br>
            <input name="recipient_phone" placeholder="Teléfono destinatario"><br><br>
            <input name="phrase_1" placeholder="Frase 1"><br><br>
            <input name="phrase_2" placeholder="Frase 2"><br><br>
            <input name="phrase_3" placeholder="Frase 3"><br><br>
            <input name="amount" type="number" step="0.01" placeholder="Cantidad regalo (€)"><br><br>

            <button type="submit">Crear ETERNA</button>
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
    recipient_name: str = Form(...),
    recipient_phone: str = Form(...),
    phrase_1: str = Form(...),
    phrase_2: str = Form(...),
    phrase_3: str = Form(...),
    amount: float = Form(...)
):
    order_id = str(uuid.uuid4())

    precio_video = 5.0
    comision_pct = 0.05

    comision = round(amount * comision_pct, 2)
    total = round(amount + comision + precio_video, 2)

    order_data = {
        "order_id": order_id,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "recipient_name": recipient_name,
        "recipient_phone": recipient_phone,
        "phrase_1": phrase_1,
        "phrase_2": phrase_2,
        "phrase_3": phrase_3,
        "amount": round(amount, 2),
        "comision": comision,
        "precio_video": precio_video,
        "total": total,
        "paid": False
    }

    save_order(order_id, order_data)

    session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": "eur",
                    "product_data": {
                        "name": "ETERNA"
                    },
                    "unit_amount": int(total * 100),
                },
                "quantity": 1,
            }
        ],
        customer_email=customer_email,
        metadata={
            "order_id": order_id
        },
        success_url=f"{PUBLIC_URL}/pedido/{order_id}",
        cancel_url=f"{PUBLIC_URL}/",
    )

    return RedirectResponse(session.url, status_code=303)

# =========================
# WEBHOOK STRIPE
# =========================

@app.post("/webhook")
async def webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            STRIPE_WEBHOOK_SECRET
        )
    except Exception:
        return JSONResponse({"error": "webhook"}, status_code=400)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        order_id = session["metadata"]["order_id"]

        order = load_order(order_id)
        if order:
            order["paid"] = True
            save_order(order_id, order)

    return {"ok": True}

# =========================
# PÁGINA TRAS PAGO
# =========================

@app.get("/pedido/{order_id}", response_class=HTMLResponse)
def pedido(order_id: str):
    order = load_order(order_id)

    if not order:
        return HTMLResponse("<h1>No existe</h1>")

    if not order["paid"]:
        return HTMLResponse("""
        <html>
        <body style="background:black;color:white;text-align:center;padding-top:100px;font-family:Arial;">
            <h1>Pago pendiente...</h1>
            <p>Si acabas de pagar, espera unos segundos y recarga.</p>
        </body>
        </html>
        """)

    link_experiencia = f"{PUBLIC_URL}/ver/{order_id}"
    wa_link = whatsapp_link(order["recipient_phone"], link_experiencia)

    return HTMLResponse(f"""
    <html>
    <body style="background:black;color:white;text-align:center;padding-top:80px;font-family:Arial;">

        <h1>ETERNA lista</h1>

        <p>Destinatario: {order["recipient_name"]}</p>
        <p>Frase 1: {order["phrase_1"]}</p>
        <p>Frase 2: {order["phrase_2"]}</p>
        <p>Frase 3: {order["phrase_3"]}</p>

        <h2 style="color:#00ff88;">Has regalado {order["amount"]}€</h2>

        <p>Comisión: {order["comision"]}€</p>
        <p>Vídeo ETERNA: {order["precio_video"]}€</p>
        <h3>Total pagado: {order["total"]}€</h3>

        <p style="margin-top:30px;">Enlace directo:</p>
        <p>{link_experiencia}</p>

        <a href="{wa_link}">
            <button style="padding:20px;background:green;color:white;border:none;border-radius:8px;margin-top:20px;">
                Enviar por WhatsApp
            </button>
        </a>

    </body>
    </html>
    """)

# =========================
# EXPERIENCIA RECEPTOR
# =========================

@app.get("/ver/{order_id}", response_class=HTMLResponse)
def ver_eterna(order_id: str):
    order = load_order(order_id)

    if not order:
        return HTMLResponse("<h1>No existe</h1>")

    if not order["paid"]:
        return HTMLResponse("<h1>Aún no disponible</h1>")

    return HTMLResponse(f"""
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="background:black;color:white;text-align:center;font-family:Arial;display:flex;justify-content:center;align-items:center;height:100vh;">

        <div id="start">
            <h1 style="font-size:28px;">ETERNA</h1>
            <p style="margin-top:20px;">Este momento será guardado para quien lo creó ❤️</p>
            <button onclick="startExperience()" style="
                margin-top:40px;
                padding:15px 25px;
                font-size:16px;
                background:white;
                color:black;
                border:none;
                border-radius:10px;
            ">
                Aceptar y continuar
            </button>
        </div>

        <div id="countdown" style="display:none;font-size:60px;">
            3
        </div>

        <div id="experience" style="display:none;">
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

            <p style="margin-top:20px;">
                Tu momento ha sido vivido ❤️
            </p>
        </div>

        <script>
        function startExperience() {{
            document.getElementById("start").style.display = "none";
            document.getElementById("countdown").style.display = "block";

            let count = 3;

            let interval = setInterval(() => {{
                count--;

                if (count > 0) {{
                    document.getElementById("countdown").innerText = count;
                }} else {{
                    clearInterval(interval);
                    document.getElementById("countdown").style.display = "none";
                    document.getElementById("experience").style.display = "block";
                }}
            }}, 1000);
        }}
        </script>

    </body>
    </html>
    """)

# =========================
# TEST
# =========================

@app.get("/test")
def test():
    return {"status": "ok"}
