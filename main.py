import html
import os
import urllib.parse
import uuid

import stripe
from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI(title="ETERNA V2")

# =========================
# CONFIG
# =========================

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000").strip()

BASE_PRICE = float(os.getenv("ETERNA_BASE_PRICE_EUR", "29"))
CURRENCY = os.getenv("ETERNA_CURRENCY", "eur").strip().lower()
COMMISSION_RATE = float(os.getenv("GIFT_COMMISSION_RATE", "0.05"))

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# Memoria temporal
orders: dict[str, dict] = {}


# =========================
# HELPERS
# =========================

def safe_text(value: str) -> str:
    return html.escape(str(value or "").strip())


def money(value: float) -> str:
    return f"{float(value):.2f}"


def normalize_phone(phone: str) -> str:
    return "".join(ch for ch in str(phone or "") if ch.isdigit())


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
            * {
                box-sizing: border-box;
            }

            body {
                margin: 0;
                min-height: 100vh;
                background:
                    radial-gradient(circle at top, rgba(255,255,255,0.08), transparent 30%),
                    linear-gradient(180deg, #050505 0%, #000000 100%);
                color: white;
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 24px;
            }

            .card {
                width: 100%;
                max-width: 620px;
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 24px;
                padding: 28px;
                backdrop-filter: blur(8px);
                box-shadow: 0 20px 60px rgba(0,0,0,0.35);
            }

            h1 {
                margin: 0 0 10px 0;
                font-size: 40px;
                letter-spacing: 2px;
                text-align: center;
            }

            .subtitle {
                text-align: center;
                color: rgba(255,255,255,0.75);
                margin-bottom: 28px;
                line-height: 1.5;
            }

            .section-title {
                margin: 22px 0 10px 0;
                font-size: 14px;
                text-transform: uppercase;
                letter-spacing: 1.5px;
                color: rgba(255,255,255,0.65);
            }

            input {
                width: 100%;
                padding: 14px 16px;
                margin: 8px 0;
                border-radius: 14px;
                border: 1px solid rgba(255,255,255,0.10);
                background: rgba(255,255,255,0.06);
                color: white;
                outline: none;
                font-size: 15px;
            }

            input::placeholder {
                color: rgba(255,255,255,0.45);
            }

            input:focus {
                border-color: rgba(255,255,255,0.25);
                background: rgba(255,255,255,0.08);
            }

            .hint {
                margin-top: 8px;
                font-size: 13px;
                color: rgba(255,255,255,0.5);
                line-height: 1.4;
            }

            button {
                width: 100%;
                margin-top: 22px;
                padding: 16px 22px;
                border-radius: 999px;
                border: 0;
                background: white;
                color: black;
                font-weight: bold;
                font-size: 15px;
                cursor: pointer;
                transition: transform 0.15s ease, opacity 0.15s ease;
            }

            button:hover {
                transform: translateY(-1px);
                opacity: 0.95;
            }

            .footer-note {
                text-align: center;
                margin-top: 16px;
                font-size: 12px;
                color: rgba(255,255,255,0.45);
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>ETERNA</h1>
            <div class="subtitle">
                Convierte emoción en un regalo inolvidable.<br>
                Crea una experiencia, añade dinero si quieres y envíala en un instante.
            </div>

            <form action="/crear-eterna" method="post">
                <div class="section-title">Tus datos</div>
                <input name="customer_name" placeholder="Tu nombre" required>
                <input name="customer_email" type="email" placeholder="Tu email" required>
                <input name="customer_phone" placeholder="Tu teléfono" required>

                <div class="section-title">Persona que recibe</div>
                <input name="recipient_name" placeholder="Nombre de la persona" required>
                <input name="recipient_phone" placeholder="Teléfono de la persona" required>

                <div class="section-title">Las 3 frases</div>
                <input name="phrase_1" placeholder="Frase 1" required>
                <input name="phrase_2" placeholder="Frase 2" required>
                <input name="phrase_3" placeholder="Frase 3" required>

                <div class="section-title">Dinero a regalar</div>
                <input
                    name="gift_amount"
                    placeholder="Dinero a regalar (€)"
                    type="number"
                    step="0.01"
                    min="0"
                    value="0"
                    required
                >

                <div class="hint">
                    Precio base: 29€ · Si añades dinero, se suma una pequeña comisión automática.
                </div>

                <button type="submit">CREAR MI ETERNA</button>
            </form>

            <div class="footer-note">
                ETERNA V2 · flujo en vivo
            </div>
        </div>
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
        raise HTTPException(status_code=500, detail="Falta STRIPE_SECRET_KEY en Render.")

    order_id = str(uuid.uuid4())[:12]

    gift_amount = max(0.0, round(float(gift_amount or 0), 2))
    gift_commission = round(gift_amount * COMMISSION_RATE, 2)
    total = round(BASE_PRICE + gift_amount + gift_commission, 2)

    orders[order_id] = {
        "order_id": order_id,
        "customer_name": customer_name.strip(),
        "customer_email": customer_email.strip(),
        "customer_phone": customer_phone.strip(),
        "recipient_name": recipient_name.strip(),
        "recipient_phone": recipient_phone.strip(),
        "phrase_1": phrase_1.strip(),
        "phrase_2": phrase_2.strip(),
        "phrase_3": phrase_3.strip(),
        "gift_amount": gift_amount,
        "gift_commission": gift_commission,
        "total": total,
        "paid": False,
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
                            "description": (
                                f"ETERNA {money(BASE_PRICE)}€ + "
                                f"regalo {money(gift_amount)}€ + "
                                f"comisión {money(gift_commission)}€"
                            ),
                        },
                        "unit_amount": int(round(total * 100)),
                    },
                    "quantity": 1,
                }
            ],
            success_url=f"{PUBLIC_BASE_URL}/post-pago/{order_id}",
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
        raise HTTPException(status_code=500, detail=f"Error creando checkout Stripe: {e}")

    return RedirectResponse(url=session.url, status_code=303)


# =========================
# POST PAGO
# =========================

@app.get("/post-pago/{order_id}")
def post_pago(order_id: str):
    order = orders.get(order_id)

    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    order["paid"] = True
    return RedirectResponse(url=f"/resumen/{order_id}", status_code=303)


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
        f"Ábrelo aquí:\n"
        f"{PUBLIC_BASE_URL}/pedido/{order_id}"
    )

    telefono = normalize_phone(order["recipient_phone"])
    whatsapp_url = f"https://wa.me/{telefono}?text={mensaje}"

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Resumen ETERNA</title>
        <style>
            * {{
                box-sizing: border-box;
            }}

            body {{
                margin: 0;
                min-height: 100vh;
                background:
                    radial-gradient(circle at top, rgba(255,255,255,0.08), transparent 30%),
                    linear-gradient(180deg, #050505 0%, #000000 100%);
                color: white;
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 24px;
            }}

            .card {{
                width: 100%;
                max-width: 700px;
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 24px;
                padding: 34px 28px;
                text-align: center;
            }}

            h1 {{
                margin-top: 0;
                font-size: 34px;
            }}

            .soft {{
                color: rgba(255,255,255,0.72);
                line-height: 1.6;
            }}

            .stats {{
                margin-top: 26px;
                display: grid;
                gap: 12px;
            }}

            .stat {{
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: 16px;
                padding: 16px;
            }}

            .stat-label {{
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 1.2px;
                color: rgba(255,255,255,0.48);
                margin-bottom: 6px;
            }}

            .stat-value {{
                font-size: 22px;
                font-weight: bold;
            }}

            .buttons {{
                margin-top: 34px;
                display: flex;
                flex-direction: column;
                gap: 14px;
            }}

            a {{
                text-decoration: none;
            }}

            button {{
                width: 100%;
                padding: 16px 22px;
                border-radius: 999px;
                border: 0;
                font-weight: bold;
                font-size: 15px;
                cursor: pointer;
            }}

            .whatsapp {{
                background: #25D366;
                color: white;
            }}

            .light {{
                background: white;
                color: black;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Tu ETERNA está lista ❤️</h1>

            <div class="soft">
                Ya puedes enviarla a {safe_text(order["recipient_name"])} por WhatsApp.
            </div>

            <div class="stats">
                <div class="stat">
                    <div class="stat-label">Regalo</div>
                    <div class="stat-value">{money(order["gift_amount"])}€</div>
                </div>
                <div class="stat">
                    <div class="stat-label">Total cobrado</div>
                    <div class="stat-value">{money(order["total"])}€</div>
                </div>
            </div>

            <div class="buttons">
                <a href="{whatsapp_url}" target="_blank">
                    <button class="whatsapp">Enviar por WhatsApp</button>
                </a>

                <a href="/pedido/{order_id}" target="_blank">
                    <button class="light">Ver experiencia ETERNA</button>
                </a>

                <a href="/">
                    <button class="light">Crear otra ETERNA ❤️</button>
                </a>
            </div>
        </div>
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

    if not order.get("paid"):
        return HTMLResponse(
            """
            <!DOCTYPE html>
            <html lang="es">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>ETERNA bloqueada</title>
                <style>
                    body {
                        margin: 0;
                        min-height: 100vh;
                        background: black;
                        color: white;
                        font-family: Arial, sans-serif;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        text-align: center;
                        padding: 24px;
                    }
                    .box {
                        max-width: 560px;
                    }
                    h1 {
                        font-size: 34px;
                        margin-bottom: 12px;
                    }
                    p {
                        color: rgba(255,255,255,0.72);
                        line-height: 1.6;
                    }
                </style>
            </head>
            <body>
                <div class="box">
                    <h1>Esta ETERNA aún no está disponible</h1>
                    <p>El pago todavía no se ha completado.</p>
                </div>
            </body>
            </html>
            """
        )

    phrase_1 = safe_text(order["phrase_1"])
    phrase_2 = safe_text(order["phrase_2"])
    phrase_3 = safe_text(order["phrase_3"])
    recipient_name = safe_text(order["recipient_name"])
    gift_amount = money(order["gift_amount"])

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ETERNA</title>
        <style>
            * {{
                box-sizing: border-box;
            }}

            body {{
                margin: 0;
                min-height: 100vh;
                background:
                    radial-gradient(circle at center top, rgba(255,255,255,0.10), transparent 30%),
                    linear-gradient(180deg, #050505 0%, #000000 100%);
                color: white;
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 24px;
                text-align: center;
            }}

            .experience {{
                width: 100%;
                max-width: 760px;
                padding: 40px 24px;
            }}

            .eyebrow {{
                font-size: 12px;
                letter-spacing: 2px;
                text-transform: uppercase;
                color: rgba(255,255,255,0.45);
                margin-bottom: 18px;
            }}

            h1 {{
                margin: 0 0 18px 0;
                font-size: 42px;
                line-height: 1.15;
            }}

            .recipient {{
                color: rgba(255,255,255,0.62);
                margin-bottom: 34px;
            }}

            .phrase {{
                font-size: 28px;
                line-height: 1.4;
                margin: 22px 0;
            }}

            .gift {{
                margin-top: 34px;
                font-size: 22px;
                padding: 18px 20px;
                display: inline-block;
                border-radius: 18px;
                background: rgba(255,255,255,0.06);
                border: 1px solid rgba(255,255,255,0.08);
            }}

            .buttons {{
                margin-top: 38px;
            }}

            a {{
                text-decoration: none;
            }}

            button {{
                padding: 16px 24px;
                border-radius: 999px;
                border: 0;
                background: white;
                color: black;
                font-weight: bold;
                font-size: 15px;
                cursor: pointer;
            }}
        </style>
    </head>
    <body>
        <div class="experience">
            <div class="eyebrow">ETERNA</div>
            <h1>Hay algo para ti</h1>
            <div class="recipient">Para {recipient_name}</div>

            <div class="phrase">{phrase_1}</div>
            <div class="phrase">{phrase_2}</div>
            <div class="phrase">{phrase_3}</div>

            <div class="gift">💸 Has recibido {gift_amount}€</div>

            <div class="buttons">
                <a href="/">
                    <button>Crear tu propia ETERNA ❤️</button>
                </a>
            </div>
        </div>
    </body>
    </html>
    """