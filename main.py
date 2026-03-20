import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import stripe
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

# =========================
# CONFIG
# =========================

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000")

ETERNA_BASE_PRICE_EUR = float(os.getenv("ETERNA_BASE_PRICE_EUR", "29"))
GIFT_COMMISSION_RATE = float(os.getenv("GIFT_COMMISSION_RATE", "0.05"))
ETERNA_CURRENCY = os.getenv("ETERNA_CURRENCY", "eur")

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "123456")

stripe.api_key = STRIPE_SECRET_KEY

app = FastAPI(title="ETERNA MAQUINON")

# =========================
# CARPETAS
# =========================

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
GIFT_DIR = BASE_DIR / "gift_uploads"
REACTION_DIR = BASE_DIR / "reacciones"
FINAL_DIR = BASE_DIR / "final_returns"

ORDERS_FILE = DATA_DIR / "orders.json"

STATIC_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)
GIFT_DIR.mkdir(exist_ok=True)
REACTION_DIR.mkdir(exist_ok=True)
FINAL_DIR.mkdir(exist_ok=True)

if not ORDERS_FILE.exists():
    ORDERS_FILE.write_text("{}", encoding="utf-8")

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/gift_uploads", StaticFiles(directory=str(GIFT_DIR)), name="gift_uploads")
app.mount("/reacciones", StaticFiles(directory=str(REACTION_DIR)), name="reacciones")
app.mount("/final_returns", StaticFiles(directory=str(FINAL_DIR)), name="final_returns")

# =========================
# UTILIDADES
# =========================

def now_iso() -> str:
    return datetime.utcnow().isoformat()

def euros(n: float) -> str:
    return f"{n:.2f}€".replace(".", ",")

def phone_for_wa(phone: str | None) -> str:
    if not phone:
        return ""
    return "".join(ch for ch in phone if ch.isdigit())

def load_orders() -> dict:
    try:
        return json.loads(ORDERS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_orders(orders: dict) -> None:
    ORDERS_FILE.write_text(
        json.dumps(orders, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

def get_order(order_id: str) -> dict | None:
    return load_orders().get(order_id)

def update_order(order_id: str, **fields) -> dict | None:
    orders = load_orders()
    order = orders.get(order_id)
    if not order:
        return None
    order.update(fields)
    orders[order_id] = order
    save_orders(orders)
    return order

def admin_guard(token: str | None):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="No autorizado.")

def save_upload_file(upload: UploadFile, folder: Path, forced_name: str | None = None) -> str:
    ext = Path(upload.filename or "").suffix.lower() or ".bin"
    filename = forced_name if forced_name else f"{uuid.uuid4().hex}{ext}"
    file_path = folder / filename
    with open(file_path, "wb") as f:
        f.write(upload.file.read())
    return filename

def calc_totals(gift_amount: float) -> tuple[float, float, float]:
    gift_amount = max(0.0, round(float(gift_amount or 0), 2))
    commission = round(gift_amount * GIFT_COMMISSION_RATE, 2)
    total = round(ETERNA_BASE_PRICE_EUR + gift_amount + commission, 2)
    return gift_amount, commission, total

def create_order_record(
    customer_name: str,
    customer_email: str,
    customer_phone: str,
    recipient_name: str,
    recipient_phone: str,
    phrase_1: str,
    phrase_2: str,
    phrase_3: str,
    gift_video_filename: str | None,
    gift_amount: float,
    gift_commission: float,
    total_paid: float,
) -> str:
    orders = load_orders()
    order_id = str(uuid.uuid4())[:12]

    orders[order_id] = {
        "order_id": order_id,
        "created_at": now_iso(),
        "status": "pending_payment",
        "paid": False,
        "opened_at": None,
        "reaction_uploaded_at": None,

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
        "eterna_base_price": ETERNA_BASE_PRICE_EUR,
        "total_paid": total_paid,

        "gift_video_filename": gift_video_filename,
        "reaction_video_filename": None,
        "final_return_video_filename": None,

        "stripe_session_id": None,
    }

    save_orders(orders)
    return order_id

# =========================
# HOME
# =========================

@app.get("/", response_class=HTMLResponse)
def home():
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ETERNA</title>
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                min-height: 100vh;
                background:
                    radial-gradient(circle at top, rgba(255,255,255,0.06), transparent 30%),
                    linear-gradient(180deg, #0b0b0b 0%, #000000 100%);
                color: white;
                font-family: Arial, sans-serif;
                padding: 24px;
            }}
            .wrap {{
                width: 100%;
                max-width: 760px;
                margin: 0 auto;
            }}
            .box {{
                width: 100%;
                margin: 40px auto;
                padding: 28px;
                border-radius: 24px;
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
            }}
            h1 {{
                margin: 0 0 14px;
                font-size: 44px;
                font-weight: 500;
                text-align: center;
            }}
            p.top {{
                margin: 0 0 24px;
                color: rgba(255,255,255,0.82);
                line-height: 1.6;
                text-align: center;
            }}
            .grid {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 14px;
            }}
            input {{
                width: 100%;
                padding: 14px 16px;
                margin-top: 12px;
                border-radius: 14px;
                border: 1px solid rgba(255,255,255,0.12);
                background: rgba(255,255,255,0.07);
                color: white;
                font-size: 16px;
                outline: none;
            }}
            input::placeholder {{
                color: rgba(255,255,255,0.45);
            }}
            .full {{
                grid-column: 1 / -1;
            }}
            .label {{
                margin-top: 18px;
                font-size: 14px;
                color: rgba(255,255,255,0.68);
            }}
            button {{
                width: 100%;
                padding: 16px;
                margin-top: 24px;
                border-radius: 999px;
                border: none;
                background: white;
                color: black;
                font-size: 16px;
                font-weight: bold;
                cursor: pointer;
            }}
            .mini {{
                margin-top: 14px;
                font-size: 13px;
                color: rgba(255,255,255,0.55);
                text-align: center;
            }}
            .pricebox {{
                margin-top: 18px;
                padding: 16px;
                border-radius: 18px;
                background: rgba(255,255,255,0.05);
                color: rgba(255,255,255,0.9);
                line-height: 1.7;
            }}
            @media (max-width: 700px) {{
                .grid {{
                    grid-template-columns: 1fr;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="wrap">
            <div class="box">
                <h1>ETERNA</h1>
                <p class="top">
                    No regalas solo un vídeo.
                    <br>
                    Regalas una emoción… y recibes de vuelta el impacto real que has provocado.
                </p>

                <form action="/crear-eterna" method="post" enctype="multipart/form-data">
                    <div class="grid">
                        <input name="customer_name" placeholder="Tu nombre" required>
                        <input name="customer_email" type="email" placeholder="Tu email" required>

                        <input name="customer_phone" placeholder="Tu teléfono" required>
                        <input name="recipient_name" placeholder="Nombre de quien recibe" required>

                        <input name="recipient_phone" placeholder="Teléfono de quien recibe" required class="full">

                        <input name="phrase_1" placeholder="Primera frase" required class="full">
                        <input name="phrase_2" placeholder="Segunda frase" required class="full">
                        <input name="phrase_3" placeholder="Tercera frase" required class="full">

                        <input name="gift_amount" type="number" step="0.01" min="0" placeholder="Cantidad a regalar (€)" class="full">

                        <div class="full label">Vídeo base que envías (opcional por ahora)</div>
                        <input name="gift_video" type="file" accept="video/*" class="full">
                    </div>

                    <div class="pricebox">
                        ETERNA: {euros(ETERNA_BASE_PRICE_EUR)}<br>
                        Comisión del regalo: {int(GIFT_COMMISSION_RATE * 100)}%<br>
                        El dinero regalado se suma aparte.
                    </div>

                    <button type="submit">CREAR MI ETERNA</button>
                </form>

                <div class="mini">
                    Primero se crea el pedido y el pago. Después se activa la experiencia del receptor.
                </div>
            </div>
        </div>
    </body>
    </html>
    """

# =========================
# CREAR PEDIDO + STRIPE
# =========================

@app.post("/crear-eterna")
async def crear_eterna(
    customer_name: str = Form(...),
    customer_email: str = Form(...),
    customer_phone: str = Form(""),
    recipient_name: str = Form(...),
    recipient_phone: str = Form(""),
    phrase_1: str = Form(""),
    phrase_2: str = Form(""),
    phrase_3: str = Form(""),
    gift_amount: float = Form(0),
    gift_video: UploadFile | None = File(None),
):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Falta STRIPE_SECRET_KEY.")

    gift_amount, gift_commission, total_paid = calc_totals(gift_amount)

    gift_video_filename = None
    if gift_video and gift_video.filename:
        ext = Path(gift_video.filename).suffix.lower() or ".mp4"
        gift_video_filename = save_upload_file(
            gift_video,
            GIFT_DIR,
            forced_name=f"gift_{uuid.uuid4().hex}{ext}"
        )

    order_id = create_order_record(
        customer_name=customer_name,
        customer_email=customer_email,
        customer_phone=customer_phone,
        recipient_name=recipient_name,
        recipient_phone=recipient_phone,
        phrase_1=phrase_1,
        phrase_2=phrase_2,
        phrase_3=phrase_3,
        gift_video_filename=gift_video_filename,
        gift_amount=gift_amount,
        gift_commission=gift_commission,
        total_paid=total_paid,
    )

    session = stripe.checkout.Session.create(
        mode="payment",
        client_reference_id=order_id,
        metadata={
            "order_id": order_id,
            "customer_name": customer_name,
            "recipient_name": recipient_name,
            "gift_amount": str(gift_amount),
        },
        line_items=[
            {
                "price_data": {
                    "currency": ETERNA_CURRENCY,
                    "product_data": {
                        "name": "ETERNA",
                        "description": f"Experiencia ETERNA + regalo {euros(gift_amount)} + comisión {euros(gift_commission)}",
                    },
                    "unit_amount": int(round(total_paid * 100)),
                },
                "quantity": 1,
            }
        ],
        success_url=f"{PUBLIC_BASE_URL}/post-pago?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{PUBLIC_BASE_URL}/cancelado?order_id={order_id}",
    )

    update_order(
        order_id,
        stripe_session_id=session.id,
        status="checkout_created",
    )

    return RedirectResponse(url=session.url, status_code=303)

# =========================
# POST PAGO / CANCELADO
# =========================

@app.get("/post-pago", response_class=HTMLResponse)
def post_pago(session_id: str):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Falta STRIPE_SECRET_KEY.")

    session = stripe.checkout.Session.retrieve(session_id)
    order_id = session.client_reference_id

    if not order_id:
        raise HTTPException(status_code=400, detail="No se encontró order_id.")

    order = get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")

    if order.get("paid"):
        return HTMLResponse(f"""
        <html>
        <body style="margin:0;background:black;color:white;font-family:Arial,sans-serif;display:flex;min-height:100vh;align-items:center;justify-content:center;text-align:center;padding:24px;">
            <div style="max-width:720px;">
                <h1>Pago confirmado</h1>
                <p>Tu ETERNA ya está creada.</p>

                <p>
                    Enlace del receptor:
                    <br>
                    <strong>{PUBLIC_BASE_URL}/pedido/{order_id}</strong>
                </p>

                <p>
                    Regalo: <strong>{euros(order["gift_amount"])}</strong><br>
                    Comisión regalo: <strong>{euros(order["gift_commission"])}</strong><br>
                    Total pagado: <strong>{euros(order["total_paid"])}</strong>
                </p>

                <a href="/resumen/{order_id}" style="display:inline-block;margin-top:20px;padding:14px 24px;border-radius:999px;background:white;color:black;text-decoration:none;font-weight:bold;">
                    VER RESUMEN DEL PEDIDO
                </a>
            </div>
        </body>
        </html>
        """)

    return HTMLResponse("""
    <html>
    <body style="margin:0;background:black;color:white;font-family:Arial,sans-serif;display:flex;min-height:100vh;align-items:center;justify-content:center;text-align:center;padding:24px;">
        <div>
            <h1>Estamos confirmando tu pago…</h1>
            <p>Recarga en unos segundos.</p>
        </div>
    </body>
    </html>
    """)

@app.get("/cancelado", response_class=HTMLResponse)
def cancelado(order_id: str | None = None):
    return HTMLResponse(f"""
    <html>
    <body style="margin:0;background:black;color:white;font-family:Arial,sans-serif;display:flex;min-height:100vh;align-items:center;justify-content:center;text-align:center;padding:24px;">
        <div>
            <h1>Pago cancelado</h1>
            <p>{'Pedido ' + order_id + ' cancelado.' if order_id else 'Pago cancelado.'}</p>
            <a href="/" style="display:inline-block;margin-top:24px;padding:14px 22px;border-radius:999px;background:white;color:black;text-decoration:none;font-weight:bold;">VOLVER</a>
        </div>
    </body>
    </html>
    """)

# =========================
# WEBHOOK
# =========================

@app.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Falta STRIPE_WEBHOOK_SECRET.")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=STRIPE_WEBHOOK_SECRET,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Payload inválido.")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Firma webhook inválida.")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        order_id = session.get("client_reference_id") or session.get("metadata", {}).get("order_id")

        if order_id:
            update_order(
                order_id,
                paid=True,
                status="paid",
                stripe_session_id=session.get("id"),
            )

    return {"ok": True}

# =========================
# RESUMEN PEDIDO
# =========================

@app.get("/resumen/{order_id}", response_class=HTMLResponse)
def resumen_pedido(order_id: str):
    order = get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")

    gift_link = f"/gift_uploads/{order['gift_video_filename']}" if order.get("gift_video_filename") else None
    reaction_link = f"/reacciones/{order['reaction_video_filename']}" if order.get("reaction_video_filename") else None
    final_link = f"/final_returns/{order['final_return_video_filename']}" if order.get("final_return_video_filename") else None

    wa_phone = phone_for_wa(order.get("recipient_phone"))
    wa_text = quote(
        f"Hola ❤️\n\n"
        f"Alguien ha creado algo muy especial para ti.\n\n"
        f"No es un vídeo.\nNo es un mensaje.\n\n"
        f"Es algo que solo ocurre una vez.\n\n"
        f"Ábrelo cuando estés listo.\n\n"
        f"👉 {PUBLIC_BASE_URL}/pedido/{order['order_id']}"
    )
    wa_link = f"https://wa.me/{wa_phone}?text={wa_text}" if wa_phone else "#"

    return HTMLResponse(f"""
    <html>
    <body style="margin:0;background:#000;color:#fff;font-family:Arial,sans-serif;padding:24px;">
        <div style="max-width:960px;margin:0 auto;">
            <h1>Resumen ETERNA</h1>

            <p><strong>Pedido:</strong> {order["order_id"]}</p>
            <p><strong>Estado:</strong> {order["status"]}</p>
            <p><strong>Pagado:</strong> {"Sí" if order["paid"] else "No"}</p>

            <hr style="border-color:rgba(255,255,255,0.15);margin:24px 0;">

            <p><strong>Regalante:</strong> {order["customer_name"]}</p>
            <p><strong>Email regalante:</strong> {order["customer_email"]}</p>
            <p><strong>Teléfono regalante:</strong> {order["customer_phone"]}</p>

            <p><strong>Receptor:</strong> {order["recipient_name"]}</p>
            <p><strong>Teléfono receptor:</strong> {order["recipient_phone"]}</p>

            <p><strong>Frase 1:</strong> {order["phrase_1"]}</p>
            <p><strong>Frase 2:</strong> {order["phrase_2"]}</p>
            <p><strong>Frase 3:</strong> {order["phrase_3"]}</p>

            <hr style="border-color:rgba(255,255,255,0.15);margin:24px 0;">

            <p><strong>ETERNA:</strong> {euros(order["eterna_base_price"])}</p>
            <p><strong>Regalo:</strong> {euros(order["gift_amount"])}</p>
            <p><strong>Comisión regalo:</strong> {euros(order["gift_commission"])}</p>
            <p><strong>Total pagado:</strong> {euros(order["total_paid"])}</p>

            <hr style="border-color:rgba(255,255,255,0.15);margin:24px 0;">

            <p><strong>Enlace receptor:</strong><br>{PUBLIC_BASE_URL}/pedido/{order["order_id"]}</p>

            <p><strong>Vídeo enviado por el regalante:</strong>
                {"<a style='color:#fff;' href='" + gift_link + "' target='_blank'>Ver vídeo enviado</a>" if gift_link else "Aún no subido"}
            </p>

            <p><strong>Vídeo reacción del receptor:</strong>
                {"<a style='color:#fff;' href='" + reaction_link + "' target='_blank'>Ver reacción</a>" if reaction_link else "Aún no disponible"}
            </p>

            <p><strong>Vídeo final de retorno al regalante:</strong>
                {"<a style='color:#fff;' href='" + final_link + "' target='_blank'>Ver vídeo final</a>" if final_link else "Aún no generado"}
            </p>

            <div style="margin-top:28px;display:flex;gap:12px;flex-wrap:wrap;">
                <a href="/retorno/{order["order_id"]}" style="display:inline-block;padding:14px 24px;border-radius:999px;background:white;color:black;text-decoration:none;font-weight:bold;">
                    VER TU ETERNA
                </a>

                <a href="{wa_link}" target="_blank" style="display:inline-block;padding:14px 24px;border-radius:999px;background:#25D366;color:white;text-decoration:none;font-weight:bold;">
                    ENVIAR POR WHATSAPP
                </a>
            </div>
        </div>
    </body>
    </html>
    """)

# =========================
# RETORNO REGALANTE
# =========================

@app.get("/retorno/{order_id}", response_class=HTMLResponse)
def retorno(order_id: str):
    order = get_order(order_id)

    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")

    if not order.get("paid"):
        return HTMLResponse("""
        <html>
        <body style="margin:0;background:black;color:white;font-family:Arial,sans-serif;display:flex;min-height:100vh;align-items:center;justify-content:center;text-align:center;padding:24px;">
            <div>
                <h1>No disponible</h1>
                <p>Esta ETERNA aún no está pagada.</p>
            </div>
        </body>
        </html>
        """, status_code=403)

    if not order.get("reaction_video_filename"):
        return HTMLResponse("""
        <html>
        <body style="margin:0;background:black;color:white;font-family:Arial,sans-serif;display:flex;min-height:100vh;align-items:center;justify-content:center;text-align:center;padding:24px;">
            <div>
                <h1>Aún no hay reacción</h1>
                <p>La persona todavía no ha vivido la experiencia completa.</p>
            </div>
        </body>
        </html>
        """)

    if order.get("gift_video_filename"):
        gift_video = f"""
        <video controls playsinline style="width:90%;max-width:420px;margin-top:20px;border-radius:18px;background:#000;">
            <source src="/gift_uploads/{order['gift_video_filename']}">
        </video>
        """
    else:
        gift_video = f"""
        <div style="max-width:520px;margin:20px auto 0;opacity:0.88;line-height:1.8;">
            <p>{order["phrase_1"]}</p>
            <p>{order["phrase_2"]}</p>
            <p>{order["phrase_3"]}</p>
        </div>
        """

    reaction_video = f"""
    <video controls playsinline style="width:90%;max-width:420px;margin-top:20px;border-radius:18px;background:#000;">
        <source src="/reacciones/{order['reaction_video_filename']}">
    </video>
    """

    return HTMLResponse(f"""
    <html>
    <body style="margin:0;background:black;color:white;font-family:Arial,sans-serif;text-align:center;padding:40px;">
        <div style="max-width:900px;margin:0 auto;">
            <h1 style="font-weight:500;">Tu ETERNA</h1>

            <p style="opacity:0.82;font-size:20px;margin-top:30px;">
                Esto es lo que enviaste
            </p>

            {gift_video}

            <hr style="margin:40px 0;opacity:0.2;">

            <p style="opacity:0.82;font-size:20px;">
                Esto es lo que provocaste
            </p>

            {reaction_video}
        </div>
    </body>
    </html>
    """)

# =========================
# EXPERIENCIA RECEPTOR
# =========================

@app.get("/pedido/{order_id}", response_class=HTMLResponse)
def ver_eterna(order_id: str):
    order = get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")

    if not order.get("paid"):
        return HTMLResponse("""
        <html>
        <body style="margin:0;background:black;color:white;font-family:Arial,sans-serif;display:flex;min-height:100vh;align-items:center;justify-content:center;text-align:center;padding:24px;">
            <div>
                <h1>Esta ETERNA aún no está activada</h1>
                <p>El pago todavía no figura como confirmado.</p>
            </div>
        </body>
        </html>
        """, status_code=403)

    gift_video_html = ""
    if order.get("gift_video_filename"):
        gift_video_url = f"/gift_uploads/{order['gift_video_filename']}"
        gift_video_html = f"""
        <video id="giftVideo" playsinline controls style="width:min(92vw,420px);border-radius:18px;margin-top:22px;background:#000;">
            <source src="{gift_video_url}">
        </video>
        """
    else:
        gift_video_html = f"""
        <div style="margin-top:24px;">
            <h2 style="margin:0 0 10px;font-weight:500;">Hay algo para ti</h2>
            <p style="margin:0;">{order["phrase_1"]}<br>{order["phrase_2"]}<br>{order["phrase_3"]}</p>
        </div>
        """

    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ETERNA</title>
        <style>
            * {{ box-sizing: border-box; }}
            html, body {{
                margin: 0;
                padding: 0;
                width: 100%;
                height: 100%;
                background: #000;
                color: #fff;
                font-family: Arial, sans-serif;
                overflow: hidden;
            }}
            .pantalla {{
                position: fixed;
                inset: 0;
                display: none;
                align-items: center;
                justify-content: center;
                text-align: center;
                overflow: hidden;
                background:
                    radial-gradient(circle at top, rgba(255,255,255,0.08), transparent 35%),
                    linear-gradient(180deg, #0a0a0a 0%, #000 100%);
                padding: 24px;
            }}
            .pantalla.activa {{ display: flex; }}
            .fondo {{
                position: absolute;
                inset: 0;
                width: 100%;
                height: 100%;
                object-fit: cover;
                opacity: 0;
                transition: opacity 0.8s ease;
                filter: brightness(0.45);
            }}
            .fondo.visible {{ opacity: 1; }}
            .overlay {{
                position: absolute;
                inset: 0;
                background: linear-gradient(180deg, rgba(0,0,0,0.35) 0%, rgba(0,0,0,0.55) 45%, rgba(0,0,0,0.80) 100%);
            }}
            .contenido {{
                position: relative;
                z-index: 2;
                max-width: 760px;
                width: 100%;
            }}
            h1 {{
                margin: 0 0 16px;
                font-size: clamp(34px, 6vw, 56px);
                font-weight: 500;
            }}
            p {{
                margin: 0 auto;
                max-width: 560px;
                font-size: clamp(16px, 2.5vw, 21px);
                line-height: 1.6;
                color: rgba(255,255,255,0.92);
            }}
            .micro {{
                margin-top: 18px;
                font-size: 13px;
                color: rgba(255,255,255,0.62);
            }}
            button {{
                margin-top: 28px;
                padding: 15px 26px;
                font-size: 16px;
                border: 0;
                border-radius: 999px;
                background: rgba(255,255,255,0.95);
                color: #000;
                cursor: pointer;
                min-width: 190px;
            }}
            .fila-botones {{
                display: flex;
                gap: 14px;
                justify-content: center;
                flex-wrap: wrap;
                margin-top: 28px;
            }}
            .btn-secundario {{
                background: rgba(255,255,255,0.14);
                color: #fff;
                border: 1px solid rgba(255,255,255,0.18);
            }}
            #preview {{
                position: fixed;
                right: 14px;
                bottom: 14px;
                width: 118px;
                max-width: 28vw;
                border-radius: 16px;
                overflow: hidden;
                z-index: 20;
                background: #111;
                border: 1px solid rgba(255,255,255,0.15);
                opacity: 0;
                pointer-events: none;
                transition: opacity 0.5s ease;
            }}
            #preview.visible {{ opacity: 0.82; }}
        </style>
    </head>
    <body>

        <section id="inicio" class="pantalla activa">
            <img id="imgInicio" class="fondo" src="/static/eterna_inicio.jpg" alt="ETERNA inicio">
            <div class="overlay"></div>
            <div class="contenido">
                <h1>Tu ETERNA está aquí</h1>
                <p>
                    Al continuar, aceptas vivirla tal y como fue creada.
                    <br>
                    Solo entonces podrá comenzar.
                </p>
                <div class="micro">
                    Experiencia única. Sin pausas. Sin repetirla.
                </div>
                <button onclick="iniciarExperiencia()">Aceptar ETERNA</button>
            </div>
        </section>

        <section id="experiencia" class="pantalla">
            <div class="contenido">
                {gift_video_html}
            </div>
        </section>

        <section id="final" class="pantalla">
            <img id="imgFinal" class="fondo" src="/static/eterna_final.jpg" alt="ETERNA final">
            <div class="overlay"></div>
            <div class="contenido">
                <h1>Este momento ya es tuyo</h1>
                <p>Puedes guardarlo o compartirlo.</p>
                <div class="fila-botones">
                    <button onclick="guardarVideo()">Guardar momento</button>
                    <button class="btn-secundario" onclick="compartirVideo()">Compartir momento</button>
                </div>
            </div>
        </section>

        <video id="preview" autoplay muted playsinline></video>

        <script>
            let mediaRecorder = null;
            let chunks = [];
            let videoBlob = null;
            let currentStream = null;
            const orderId = "{order_id}";
            const giftAmount = {order["gift_amount"]};

            function activarSiExiste(imgId) {{
                const img = document.getElementById(imgId);
                if (!img) return;
                img.addEventListener("load", () => img.classList.add("visible"));
                img.addEventListener("error", () => img.style.display = "none");
            }}

            activarSiExiste("imgInicio");
            activarSiExiste("imgFinal");

            function mostrarPantalla(id) {{
                ["inicio", "experiencia", "final"].forEach(x => {{
                    const el = document.getElementById(x);
                    if (el) el.classList.remove("activa");
                }});
                const el = document.getElementById(id);
                if (el) el.classList.add("activa");
            }}

            async function iniciarExperiencia() {{
                chunks = [];

                try {{
                    const stream = await navigator.mediaDevices.getUserMedia({{
                        video: true,
                        audio: true
                    }});

                    currentStream = stream;

                    const preview = document.getElementById("preview");
                    preview.srcObject = stream;
                    preview.classList.add("visible");

                    mediaRecorder = new MediaRecorder(stream);

                    mediaRecorder.ondataavailable = (e) => {{
                        if (e.data && e.data.size > 0) chunks.push(e.data);
                    }};

                    mediaRecorder.onstop = async () => {{
                        videoBlob = new Blob(chunks, {{ type: "video/webm" }});
                        await subirVideo();
                        cerrarCamara();
                        mostrarVideoFinal();
                    }};

                    mediaRecorder.start();
                    mostrarPantalla("experiencia");

                    await fetch(`/marcar-abierta/${{orderId}}`, {{
                        method: "POST"
                    }});

                    setTimeout(() => {{
                        iniciarContenido();
                    }}, 1500);

                }} catch (error) {{
                    alert("Para vivir ETERNA debes aceptar la experiencia completa.");
                }}
            }}

            function iniciarContenido() {{
                const experiencia = document.getElementById("experiencia");
                const giftVideo = document.getElementById("giftVideo");

                if (giftVideo) {{
                    giftVideo.play().catch(() => {{}});

                    giftVideo.onended = () => {{
                        experiencia.innerHTML = `
                            <div class="contenido">
                                <h1>Esto no es solo un momento</h1>
                                <p>Es algo real.</p>
                            </div>
                        `;

                        setTimeout(() => {{
                            experiencia.innerHTML = `
                                <div class="contenido">
                                    <h1>💸 Has recibido ${'{'}giftAmount.toFixed(2).replace('.', ','){'}'}€</h1>
                                    <p>Este momento también tiene forma real.</p>
                                </div>
                            `;

                            setTimeout(() => {{
                                if (mediaRecorder && mediaRecorder.state !== "inactive") {{
                                    mediaRecorder.stop();
                                }}
                            }}, 10000);
                        }}, 2500);
                    }};
                }} else {{
                    experiencia.innerHTML = `
                        <div class="contenido">
                            <h1>Esto no es solo un momento</h1>
                            <p>Es algo real.</p>
                        </div>
                    `;

                    setTimeout(() => {{
                        experiencia.innerHTML = `
                            <div class="contenido">
                                <h1>💸 Has recibido ${'{'}giftAmount.toFixed(2).replace('.', ','){'}'}€</h1>
                                <p>Este momento también tiene forma real.</p>
                            </div>
                        `;

                        setTimeout(() => {{
                            if (mediaRecorder && mediaRecorder.state !== "inactive") {{
                                mediaRecorder.stop();
                            }}
                        }}, 10000);
                    }}, 2500);
                }}
            }}

            async function subirVideo() {{
                if (!videoBlob) return false;

                const formData = new FormData();
                formData.append("video", videoBlob, `reaccion_${{orderId}}.webm`);
                formData.append("order_id", orderId);

                try {{
                    const res = await fetch("/subir-reaccion", {{
                        method: "POST",
                        body: formData
                    }});
                    return res.ok;
                }} catch (error) {{
                    console.error("Error subiendo reacción:", error);
                    return false;
                }}
            }}

            function mostrarVideoFinal() {{
                mostrarPantalla("final");

                const contenedor = document.querySelector("#final .contenido");
                const anterior = document.getElementById("videoFinalGrabado");
                if (anterior) anterior.remove();
                if (!videoBlob) return;

                const url = URL.createObjectURL(videoBlob);
                const video = document.createElement("video");
                video.id = "videoFinalGrabado";
                video.controls = true;
                video.playsInline = true;
                video.style.width = "min(92vw, 420px)";
                video.style.marginTop = "24px";
                video.style.borderRadius = "18px";
                video.style.background = "#000";
                video.src = url;

                contenedor.appendChild(video);
            }}

            function guardarVideo() {{
                if (!videoBlob) {{
                    alert("Aún no hay ningún momento guardado.");
                    return;
                }}

                const url = URL.createObjectURL(videoBlob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `eterna_${{orderId}}.webm`;
                document.body.appendChild(a);
                a.click();
                a.remove();
                setTimeout(() => URL.revokeObjectURL(url), 1000);
            }}

            async function compartirVideo() {{
                if (!videoBlob) {{
                    alert("Aún no hay ningún momento para compartir.");
                    return;
                }}

                try {{
                    const file = new File([videoBlob], `eterna_${{orderId}}.webm`, {{ type: "video/webm" }});

                    if (navigator.share && navigator.canShare && navigator.canShare({{ files: [file] }})) {{
                        await navigator.share({{
                            title: "Mi ETERNA",
                            text: "Quiero compartir este momento.",
                            files: [file]
                        }});
                    }} else {{
                        alert("Compartir no disponible en este dispositivo.");
                    }}
                }} catch (error) {{
                    console.error("Error compartiendo:", error);
                }}
            }}

            function cerrarCamara() {{
                const preview = document.getElementById("preview");
                preview.classList.remove("visible");

                if (currentStream) {{
                    currentStream.getTracks().forEach(track => track.stop());
                    currentStream = null;
                }}

                preview.srcObject = null;
            }}
        </script>
    </body>
    </html>
    """)

# =========================
# MARCAR ABIERTA
# =========================

@app.post("/marcar-abierta/{order_id}")
def marcar_abierta(order_id: str):
    order = get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")

    if not order.get("opened_at"):
        update_order(order_id, opened_at=now_iso(), status="opened")

    return {"ok": True}

# =========================
# SUBIR REACCIÓN
# =========================

@app.post("/subir-reaccion")
async def subir_reaccion(
    video: UploadFile = File(...),
    order_id: str = Form(...),
):
    order = get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")

    filename = f"reaccion_{order_id}.webm"
    file_path = REACTION_DIR / filename

    with open(file_path, "wb") as f:
        f.write(await video.read())

    update_order(
        order_id,
        reaction_video_filename=filename,
        reaction_uploaded_at=now_iso(),
        status="reaction_uploaded",
    )

    return {
        "ok": True,
        "order_id": order_id,
        "filename": filename,
    }

# =========================
# ADMIN
# =========================

@app.get("/admin", response_class=HTMLResponse)
def admin(token: str | None = None):
    admin_guard(token)
    orders = list(load_orders().values())
    orders.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    rows = ""
    for order in orders:
        rows += f"""
        <tr>
            <td style="padding:12px;border-bottom:1px solid rgba(255,255,255,0.12);">{order["order_id"]}</td>
            <td style="padding:12px;border-bottom:1px solid rgba(255,255,255,0.12);">{order["customer_name"]}</td>
            <td style="padding:12px;border-bottom:1px solid rgba(255,255,255,0.12);">{order["recipient_name"]}</td>
            <td style="padding:12px;border-bottom:1px solid rgba(255,255,255,0.12);">{"Sí" if order["paid"] else "No"}</td>
            <td style="padding:12px;border-bottom:1px solid rgba(255,255,255,0.12);">{order["status"]}</td>
            <td style="padding:12px;border-bottom:1px solid rgba(255,255,255,0.12);">{euros(order.get("gift_amount", 0))}</td>
            <td style="padding:12px;border-bottom:1px solid rgba(255,255,255,0.12);">{euros(order.get("total_paid", 0))}</td>
            <td style="padding:12px;border-bottom:1px solid rgba(255,255,255,0.12);"><a href="/resumen/{order["order_id"]}" style="color:white;">Abrir</a></td>
        </tr>
        """

    return HTMLResponse(f"""
    <html>
    <body style="margin:0;background:#000;color:#fff;font-family:Arial,sans-serif;padding:24px;">
        <div style="max-width:1200px;margin:0 auto;">
            <h1>Admin ETERNA</h1>
            <table style="width:100%;border-collapse:collapse;">
                <thead>
                    <tr>
                        <th style="text-align:left;padding:12px;border-bottom:1px solid rgba(255,255,255,0.15);">Pedido</th>
                        <th style="text-align:left;padding:12px;border-bottom:1px solid rgba(255,255,255,0.15);">Regalante</th>
                        <th style="text-align:left;padding:12px;border-bottom:1px solid rgba(255,255,255,0.15);">Receptor</th>
                        <th style="text-align:left;padding:12px;border-bottom:1px solid rgba(255,255,255,0.15);">Pagado</th>
                        <th style="text-align:left;padding:12px;border-bottom:1px solid rgba(255,255,255,0.15);">Estado</th>
                        <th style="text-align:left;padding:12px;border-bottom:1px solid rgba(255,255,255,0.15);">Regalo</th>
                        <th style="text-align:left;padding:12px;border-bottom:1px solid rgba(255,255,255,0.15);">Total</th>
                        <th style="text-align:left;padding:12px;border-bottom:1px solid rgba(255,255,255,0.15);">Resumen</th>
                    </tr>
                </thead>
                <tbody>
                    {rows if rows else "<tr><td colspan='8' style='padding:20px;'>No hay pedidos todavía.</td></tr>"}
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """)
