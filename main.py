import os
import uuid
import urllib.parse
from typing import List, Optional

import stripe
from fastapi import FastAPI, Form, UploadFile, File, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

app = FastAPI(title="ETERNA")

# =========================
# CONFIG
# =========================
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:10000")

stripe.api_key = STRIPE_SECRET_KEY

ORDERS = {}

BASE_PRICE_EUR = 29.0
MONEY_COMMISSION_RATE = 0.05


# =========================
# HELPERS
# =========================
def clean_phone(phone: str) -> str:
    return "".join(filter(str.isdigit, phone or ""))


def whatsapp_link(phone: str, url: str) -> str:
    msg = f"Hay algo para ti ❤️\n\nÁbrelo cuando estés en un momento tranquilo.\n\n👉 {url}"
    return f"https://wa.me/{clean_phone(phone)}?text={urllib.parse.quote(msg)}"


def parse_money_amount(value: str) -> float:
    if not value:
        return 0.0

    value = value.replace("€", "").replace(",", ".").strip()

    try:
        amount = float(value)
        if amount < 0:
            return 0.0
        return amount
    except Exception:
        return 0.0


def money_html_block(order: dict) -> str:
    if order.get("money_amount", 0) > 0:
        return f'<div id="moneyReveal">+ {order["money_amount"]:.2f}€</div>'
    return ""


def money_preview_block(order: dict) -> str:
    if order.get("money_amount", 0) > 0:
        return f"""
        <p><strong>Dinero regalo:</strong> {order["money_amount"]:.2f}€</p>
        <p><strong>Comisión envío dinero (5%):</strong> {order["money_commission"]:.2f}€</p>
        """
    return "<p><strong>Dinero regalo:</strong> No</p>"


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
    send_money: str = Form("no"),
    money_amount: str = Form("0"),
    photos: Optional[List[UploadFile]] = File(None),
):
    # IMPORTANTE:
    # photos es opcional para que no dé error 422 si no envías fotos
    # o si quieres probar el flujo sin ellas.

    wants_money = str(send_money).lower() in ["si", "sí", "yes", "true", "1", "on"]

    parsed_money = parse_money_amount(money_amount) if wants_money else 0.0
    money_commission = round(parsed_money * MONEY_COMMISSION_RATE, 2)

    order_id = str(uuid.uuid4())

    photo_names = []
    if photos:
        for photo in photos:
            if photo and photo.filename:
                photo_names.append(photo.filename)

    ORDERS[order_id] = {
        "paid": False,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "recipient_name": recipient_name,
        "recipient_phone": recipient_phone,
        "phrase_1": phrase_1,
        "phrase_2": phrase_2,
        "phrase_3": phrase_3,
        "send_money": wants_money,
        "money_amount": parsed_money,
        "money_commission": money_commission,
        "photos": photo_names,
    }

    # Stripe line items
    line_items = [
        {
            "price_data": {
                "currency": "eur",
                "product_data": {"name": "ETERNA"},
                "unit_amount": int(round(BASE_PRICE_EUR * 100)),
            },
            "quantity": 1,
        }
    ]

    if parsed_money > 0:
        line_items.append(
            {
                "price_data": {
                    "currency": "eur",
                    "product_data": {"name": "Dinero regalo ETERNA"},
                    "unit_amount": int(round(parsed_money * 100)),
                },
                "quantity": 1,
            }
        )

        if money_commission > 0:
            line_items.append(
                {
                    "price_data": {
                        "currency": "eur",
                        "product_data": {"name": "Comisión envío dinero ETERNA (5%)"},
                        "unit_amount": int(round(money_commission * 100)),
                    },
                    "quantity": 1,
                }
            )

    if not STRIPE_SECRET_KEY:
        # modo simple si no hay Stripe configurado
        ORDERS[order_id]["paid"] = True
        return RedirectResponse(f"/pedido/{order_id}", status_code=303)

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


@app.post("/webhook")
async def webhook(request: Request):
    if not STRIPE_WEBHOOK_SECRET:
        return JSONResponse({"ok": True, "warning": "No webhook secret configured"})

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        order_id = session.get("metadata", {}).get("order_id")

        if order_id in ORDERS:
            ORDERS[order_id]["paid"] = True
            ORDERS[order_id]["stripe_session_id"] = session.get("id")

    return {"ok": True}


@app.get("/pedido/{order_id}", response_class=HTMLResponse)
def pedido(order_id: str):
    order = ORDERS.get(order_id)

    if not order:
        return HTMLResponse("<h1 style='font-family:Arial'>No existe</h1>", status_code=404)

    if not order.get("paid"):
        return HTMLResponse("""
        <html>
        <head><meta charset="utf-8"><title>Pago pendiente</title></head>
        <body style="background:black;color:white;text-align:center;padding-top:100px;font-family:Arial;">
            <h1>Pago pendiente...</h1>
            <p>Cuando Stripe confirme el pago, esta página se activará.</p>
        </body>
        </html>
        """)

    recipient_url = f"{PUBLIC_BASE_URL}/ver/{order_id}"
    link = whatsapp_link(order["recipient_phone"], recipient_url)

    return HTMLResponse(f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>ETERNA lista</title>
    </head>
    <body style="background:black;color:white;text-align:center;padding:60px 20px;font-family:Arial;">
        <h1>ETERNA lista</h1>
        <p><strong>Destinatario:</strong> {order["recipient_name"]}</p>
        <p><strong>Frase 1:</strong> {order["phrase_1"]}</p>
        <p><strong>Frase 2:</strong> {order["phrase_2"]}</p>
        <p><strong>Frase 3:</strong> {order["phrase_3"]}</p>
        {money_preview_block(order)}
        <br>
        <p>Enlace directo:</p>
        <p><a href="{recipient_url}" style="color:#9ad1ff;">{recipient_url}</a></p>
        <br>
        <a href="{link}">
            <button style="padding:20px;background:green;color:white;border:none;border-radius:12px;font-size:18px;cursor:pointer;">
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
        return HTMLResponse("<h1 style='font-family:Arial'>No existe esta ETERNA</h1>", status_code=404)

    if not order.get("paid"):
        return HTMLResponse("""
        <html>
        <head><meta charset="utf-8"><title>No disponible</title></head>
        <body style="background:black;color:white;text-align:center;padding-top:100px;font-family:Arial;">
            <h1>Esta ETERNA aún no está disponible</h1>
        </body>
        </html>
        """)

    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>ETERNA</title>
        <style>
            * {{
                box-sizing: border-box;
            }}

            body {{
                margin: 0;
                background: #050505;
                color: white;
                font-family: Arial, sans-serif;
                overflow-x: hidden;
            }}

            .screen {{
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                padding: 24px;
                text-align: center;
            }}

            .hidden {{
                display: none !important;
            }}

            .box {{
                width: 100%;
                max-width: 760px;
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 24px;
                padding: 28px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.35);
            }}

            h1 {{
                margin: 0 0 12px 0;
                font-size: 40px;
                letter-spacing: 1px;
            }}

            p {{
                line-height: 1.6;
                opacity: 0.95;
            }}

            button {{
                margin-top: 20px;
                padding: 16px 26px;
                border: none;
                border-radius: 14px;
                background: white;
                color: black;
                font-size: 18px;
                font-weight: bold;
                cursor: pointer;
            }}

            #cameraPreview {{
                width: 180px;
                height: 240px;
                object-fit: cover;
                border-radius: 18px;
                margin-top: 18px;
                border: 1px solid rgba(255,255,255,0.12);
                background: #111;
            }}

            #countdown {{
                font-size: 90px;
                font-weight: bold;
                margin: 18px 0;
            }}

            .phrase {{
                font-size: 28px;
                margin: 16px 0;
                opacity: 0;
                transform: translateY(12px);
                transition: all 0.8s ease;
            }}

            .phrase.show {{
                opacity: 1;
                transform: translateY(0);
            }}

            #moneyReveal {{
                margin-top: 34px;
                font-size: 64px;
                font-weight: bold;
                opacity: 0;
                transform: scale(0.9);
                transition: all 0.6s ease;
            }}

            #moneyReveal.show {{
                opacity: 1;
                transform: scale(1);
            }}

            #statusText {{
                margin-top: 18px;
                font-size: 14px;
                opacity: 0.7;
            }}

            #finalText {{
                margin-top: 32px;
                font-size: 22px;
                opacity: 0;
                transition: opacity 1s ease;
            }}

            #finalText.show {{
                opacity: 1;
            }}
        </style>
    </head>
    <body>

        <div id="gateScreen" class="screen">
            <div class="box">
                <h1>ETERNA</h1>
                <p>Hay algo para ti ❤️</p>
                <p>Pero necesito verte cuando lo abras.</p>
                <button id="openBtn">Abrir ETERNA</button>
                <div id="gateError" style="margin-top:18px;color:#ff9b9b;"></div>
            </div>
        </div>

        <div id="blockedScreen" class="screen hidden">
            <div class="box">
                <h1>No puedo entregártelo</h1>
                <p>Sin aceptar la cámara no puedes ver el regalo ni el dinero.</p>
                <button id="retryBtn">Intentar de nuevo</button>
            </div>
        </div>

        <div id="experienceScreen" class="screen hidden">
            <div class="box">
                <h1>ETERNA</h1>
                <p>Esto se está viviendo contigo ❤️</p>

                <video id="cameraPreview" autoplay muted playsinline></video>

                <div id="countdownWrap">
                    <div id="countdown">3</div>
                    <p id="statusText">Preparando tu momento...</p>
                </div>

                <div id="revealWrap" class="hidden">
                    <div id="phrase1" class="phrase">{order["phrase_1"]}</div>
                    <div id="phrase2" class="phrase">{order["phrase_2"]}</div>
                    <div id="phrase3" class="phrase">{order["phrase_3"]}</div>
                    {money_html_block(order)}
                    <div id="finalText">Tu momento ha sido vivido ❤️</div>
                </div>
            </div>
        </div>

        <script>
            let mediaStream = null;

            const gateScreen = document.getElementById("gateScreen");
            const blockedScreen = document.getElementById("blockedScreen");
            const experienceScreen = document.getElementById("experienceScreen");

            const openBtn = document.getElementById("openBtn");
            const retryBtn = document.getElementById("retryBtn");
            const gateError = document.getElementById("gateError");

            const cameraPreview = document.getElementById("cameraPreview");
            const countdown = document.getElementById("countdown");
            const countdownWrap = document.getElementById("countdownWrap");
            const revealWrap = document.getElementById("revealWrap");

            const phrase1 = document.getElementById("phrase1");
            const phrase2 = document.getElementById("phrase2");
            const phrase3 = document.getElementById("phrase3");
            const moneyReveal = document.getElementById("moneyReveal");
            const finalText = document.getElementById("finalText");

            function wait(ms) {{
                return new Promise(resolve => setTimeout(resolve, ms));
            }}

            async function askForCameraAndStart() {{
                gateError.textContent = "";

                try {{
                    mediaStream = await navigator.mediaDevices.getUserMedia({{
                        video: {{
                            facingMode: "user",
                            width: {{ ideal: 720 }},
                            height: {{ ideal: 1280 }}
                        }},
                        audio: false
                    }});

                    cameraPreview.srcObject = mediaStream;

                    gateScreen.classList.add("hidden");
                    blockedScreen.classList.add("hidden");
                    experienceScreen.classList.remove("hidden");

                    await startCountdownAndReveal();
                }} catch (error) {{
                    gateScreen.classList.add("hidden");
                    blockedScreen.classList.remove("hidden");
                }}
            }}

            async function startCountdownAndReveal() {{
                countdown.textContent = "3";
                await wait(1000);
                countdown.textContent = "2";
                await wait(1000);
                countdown.textContent = "1";
                await wait(1000);

                countdownWrap.classList.add("hidden");
                revealWrap.classList.remove("hidden");

                phrase1.classList.add("show");
                await wait(1800);

                phrase2.classList.add("show");
                await wait(1800);

                phrase3.classList.add("show");
                await wait(1800);

                if (moneyReveal) {{
                    moneyReveal.classList.add("show");
                    await wait(10000);
                }} else {{
                    await wait(3000);
                }}

                if (finalText) {{
                    finalText.classList.add("show");
                }}
            }}

            openBtn.addEventListener("click", askForCameraAndStart);

            retryBtn.addEventListener("click", async () => {{
                blockedScreen.classList.add("hidden");
                gateScreen.classList.remove("hidden");
                await askForCameraAndStart();
            }});
        </script>
    </body>
    </html>
    """)
