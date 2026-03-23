import html
import json
import os
import secrets
import sqlite3
import urllib.parse
import uuid
from datetime import datetime
from pathlib import Path

import boto3
import stripe
from botocore.client import Config
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

app = FastAPI(title="ETERNA V21.1 CLEAN SAFE")

# =========================================================
# CONFIG
# =========================================================

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()

PUBLIC_BASE_URL = os.getenv(
    "PUBLIC_BASE_URL",
    "https://eterna-v2-lab.onrender.com",
).strip().rstrip("/")

BASE_PRICE = float(os.getenv("ETERNA_BASE_PRICE", "29"))
CURRENCY = os.getenv("ETERNA_CURRENCY", "eur").strip().lower()
COMMISSION_RATE = float(os.getenv("GIFT_COMMISSION_RATE", "0.05"))

DEFAULT_GIFT_VIDEO_URL = os.getenv("DEFAULT_GIFT_VIDEO_URL", "").strip()

# R2
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY", "").strip()
R2_SECRET_KEY = os.getenv("R2_SECRET_KEY", "").strip()
R2_BUCKET = os.getenv("R2_BUCKET", "").strip()
R2_ENDPOINT = os.getenv("R2_ENDPOINT", "").strip().rstrip("/")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "").strip().rstrip("/")

MAX_VIDEO_SIZE = 30 * 1024 * 1024  # 30 MB
ALLOWED_VIDEO_TYPES = {
    "video/webm",
    "video/mp4",
    "application/octet-stream",
}

DATA_FOLDER = Path("data")
DATA_FOLDER.mkdir(parents=True, exist_ok=True)

VIDEO_FOLDER = Path("videos")
VIDEO_FOLDER.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_FOLDER / "eterna.db"

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# =========================================================
# DB
# =========================================================

def db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS senders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT,
        phone TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS recipients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id TEXT PRIMARY KEY,
        sender_id INTEGER NOT NULL,
        recipient_id INTEGER NOT NULL,

        phrase_1 TEXT NOT NULL,
        phrase_2 TEXT NOT NULL,
        phrase_3 TEXT NOT NULL,

        gift_amount REAL NOT NULL DEFAULT 0,
        gift_commission REAL NOT NULL DEFAULT 0,
        total_amount REAL NOT NULL DEFAULT 0,

        paid INTEGER NOT NULL DEFAULT 0,
        delivered_to_recipient INTEGER NOT NULL DEFAULT 0,
        reaction_uploaded INTEGER NOT NULL DEFAULT 0,
        cashout_completed INTEGER NOT NULL DEFAULT 0,
        sender_notified INTEGER NOT NULL DEFAULT 0,

        stripe_session_id TEXT,
        stripe_payment_status TEXT,

        recipient_token TEXT NOT NULL UNIQUE,
        sender_token TEXT NOT NULL UNIQUE,

        reaction_video_local TEXT,
        reaction_video_public_url TEXT,
        gift_video_url TEXT,

        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,

        FOREIGN KEY(sender_id) REFERENCES senders(id),
        FOREIGN KEY(recipient_id) REFERENCES recipients(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT NOT NULL,
        asset_type TEXT NOT NULL,
        file_url TEXT NOT NULL,
        storage_provider TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(order_id) REFERENCES orders(id)
    )
    """)

    conn.commit()
    conn.close()


init_db()

# =========================================================
# HELPERS
# =========================================================

def now_iso() -> str:
    return datetime.utcnow().isoformat()


def safe_text(v: str) -> str:
    return html.escape(str(v or "").strip())


def safe_attr(v: str) -> str:
    return html.escape(str(v or "").strip(), quote=True)


def money(v: float) -> str:
    return f"{float(v):.2f}"


def format_amount_display(value) -> str:
    try:
        return f"{float(value):.2f} €".replace(".", ",")
    except Exception:
        return "0,00 €"


def normalize_phone(p: str) -> str:
    raw = str(p or "").strip()
    raw = raw.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if raw.startswith("00"):
        raw = raw[2:]
    if raw.startswith("+"):
        raw = raw[1:]
    return "".join(ch for ch in raw if ch.isdigit())


def whatsapp_link(phone: str, message: str) -> str:
    return f"https://wa.me/{normalize_phone(phone)}?text={urllib.parse.quote(message)}"


def new_order_id() -> str:
    return uuid.uuid4().hex[:12]


def new_token() -> str:
    return secrets.token_urlsafe(24)


def reaction_video_path(order_id: str) -> str:
    return str(VIDEO_FOLDER / f"{order_id}.webm")


def r2_enabled() -> bool:
    return all([R2_ACCESS_KEY, R2_SECRET_KEY, R2_BUCKET, R2_ENDPOINT, R2_PUBLIC_URL])


def get_r2_client():
    if not r2_enabled():
        return None

    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def upload_video_to_r2(local_path: str, remote_name: str, content_type: str = "video/webm") -> str | None:
    client = get_r2_client()
    if not client:
        return None

    client.upload_file(
        local_path,
        R2_BUCKET,
        remote_name,
        ExtraArgs={"ContentType": content_type},
    )
    return f"{R2_PUBLIC_URL}/{remote_name}"


def insert_asset(order_id: str, asset_type: str, file_url: str, storage_provider: str):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO assets (order_id, asset_type, file_url, storage_provider, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (order_id, asset_type, file_url, storage_provider, now_iso()))
    conn.commit()
    conn.close()


def get_order_by_id(order_id: str):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            o.*,
            s.name AS sender_name,
            s.email AS sender_email,
            s.phone AS sender_phone,
            r.name AS recipient_name,
            r.phone AS recipient_phone
        FROM orders o
        JOIN senders s ON s.id = o.sender_id
        JOIN recipients r ON r.id = o.recipient_id
        WHERE o.id = ?
    """, (order_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    return dict(row)


def get_order_by_recipient_token_or_404(token: str):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            o.*,
            s.name AS sender_name,
            s.email AS sender_email,
            s.phone AS sender_phone,
            r.name AS recipient_name,
            r.phone AS recipient_phone
        FROM orders o
        JOIN senders s ON s.id = o.sender_id
        JOIN recipients r ON r.id = o.recipient_id
        WHERE o.recipient_token = ?
    """, (token,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Experiencia no encontrada")
    return dict(row)


def get_order_by_sender_token_or_404(token: str):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            o.*,
            s.name AS sender_name,
            s.email AS sender_email,
            s.phone AS sender_phone,
            r.name AS recipient_name,
            r.phone AS recipient_phone
        FROM orders o
        JOIN senders s ON s.id = o.sender_id
        JOIN recipients r ON r.id = o.recipient_id
        WHERE o.sender_token = ?
    """, (token,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Sender pack no encontrado")
    return dict(row)


def update_order(order_id: str, **fields):
    if not fields:
        return

    fields["updated_at"] = now_iso()
    columns = ", ".join([f"{k} = ?" for k in fields.keys()])
    values = list(fields.values()) + [order_id]

    conn = db_conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE orders SET {columns} WHERE id = ?", values)
    conn.commit()
    conn.close()


def reaction_exists(order: dict) -> bool:
    if order.get("reaction_video_public_url"):
        return True
    local_path = order.get("reaction_video_local")
    return bool(local_path) and os.path.exists(local_path)


def sender_pack_url_from_order(order: dict) -> str:
    return f"{PUBLIC_BASE_URL}/sender/{order['sender_token']}"


def recipient_experience_url_from_order(order: dict) -> str:
    return f"{PUBLIC_BASE_URL}/pedido/{order['recipient_token']}"


def get_assets_count() -> int:
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM assets")
    row = cur.fetchone()
    conn.close()
    return int(row["c"])


def get_orders_count() -> int:
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM orders")
    row = cur.fetchone()
    conn.close()
    return int(row["c"])

# =========================================================
# WHATSAPP READY (STUBS)
# =========================================================

def build_recipient_message(order: dict) -> str:
    return (
        f"Hola {order['recipient_name']} ❤️\n\n"
        f"Hay algo para ti.\n\n"
        f"Aquí:\n{recipient_experience_url_from_order(order)}"
    )


def build_sender_ready_message(order: dict) -> str:
    return (
        f"Lo que creaste… volvió a ti ❤️\n\n"
        f"Aquí:\n{sender_pack_url_from_order(order)}"
    )


def send_whatsapp_recipient(phone: str, link: str, message: str):
    print("WA RECIPIENT READY")
    print("PHONE:", phone)
    print("LINK:", link)
    print("MESSAGE:", message)


def send_whatsapp_sender(phone: str, link: str, message: str):
    print("WA SENDER READY")
    print("PHONE:", phone)
    print("LINK:", link)
    print("MESSAGE:", message)

# =========================================================
# RENDER CREATE FORM
# =========================================================

def render_create_form() -> str:
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Crear ETERNA</title>
        <style>
            * {{
                box-sizing: border-box;
            }}
            html, body {{
                margin: 0;
                min-height: 100%;
                background: #000;
            }}
            body {{
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
                max-width: 760px;
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 24px;
                padding: 28px;
            }}
            h1 {{
                margin: 0 0 10px 0;
                font-size: 38px;
                letter-spacing: 2px;
                text-align: center;
            }}
            .subtitle {{
                text-align: center;
                color: rgba(255,255,255,0.75);
                margin-bottom: 26px;
                line-height: 1.5;
            }}
            .section-title {{
                margin: 20px 0 10px 0;
                font-size: 14px;
                text-transform: uppercase;
                letter-spacing: 1.5px;
                color: rgba(255,255,255,0.65);
            }}
            input {{
                width: 100%;
                padding: 14px 16px;
                margin: 8px 0;
                border-radius: 14px;
                border: 1px solid rgba(255,255,255,0.10);
                background: rgba(255,255,255,0.06);
                color: white;
                outline: none;
                font-size: 15px;
            }}
            input::placeholder {{
                color: rgba(255,255,255,0.45);
            }}
            .hint {{
                margin-top: 8px;
                font-size: 13px;
                color: rgba(255,255,255,0.5);
                line-height: 1.4;
            }}
            .buttons {{
                display: grid;
                gap: 12px;
                margin-top: 22px;
            }}
            button, .ghost {{
                width: 100%;
                padding: 16px 22px;
                border-radius: 999px;
                border: 0;
                font-weight: bold;
                font-size: 15px;
                cursor: pointer;
                text-decoration: none;
                text-align: center;
                display: inline-block;
            }}
            button {{
                background: white;
                color: black;
            }}
            .ghost {{
                background: rgba(255,255,255,0.10);
                color: white;
                border: 1px solid rgba(255,255,255,0.10);
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>CREAR ETERNA</h1>

            <div class="subtitle">
                Hay momentos que merecen quedarse para siempre
            </div>

            <form action="/crear" method="post">
                <div class="section-title">Tus datos</div>
                <input name="customer_name" placeholder="Tu nombre" required>
                <input name="customer_email" type="email" placeholder="Tu email">
                <input name="customer_phone" placeholder="Tu teléfono / WhatsApp" required>

                <div class="section-title">Persona que recibe</div>
                <input name="recipient_name" placeholder="Nombre de la persona" required>
                <input name="recipient_phone" placeholder="Teléfono / WhatsApp de la persona" required>

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
                    Precio base: {money(BASE_PRICE)}€ · Si añades dinero, se suma una pequeña comisión automática.
                </div>

                <div class="buttons">
                    <button type="submit">CONTINUAR</button>
                    <a class="ghost" href="/">Volver</a>
                </div>
            </form>
        </div>
    </body>
    </html>
    """


def create_order_and_redirect(
    customer_name: str,
    customer_email: str,
    customer_phone: str,
    recipient_name: str,
    recipient_phone: str,
    phrase_1: str,
    phrase_2: str,
    phrase_3: str,
    gift_amount: float,
):
    order_id = new_order_id()
    recipient_token = new_token()
    sender_token = new_token()

    gift_amount = max(0.0, round(float(gift_amount or 0), 2))
    gift_commission = round(gift_amount * COMMISSION_RATE, 2)
    total_amount = round(BASE_PRICE + gift_amount + gift_commission, 2)

    created_at = now_iso()

    conn = db_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO senders (name, email, phone, created_at)
        VALUES (?, ?, ?, ?)
    """, (
        (customer_name or "").strip(),
        (customer_email or "").strip(),
        (customer_phone or "").strip(),
        created_at,
    ))
    sender_id = cur.lastrowid

    cur.execute("""
        INSERT INTO recipients (name, phone, created_at)
        VALUES (?, ?, ?)
    """, (
        (recipient_name or "").strip(),
        (recipient_phone or "").strip(),
        created_at,
    ))
    recipient_id = cur.lastrowid

    cur.execute("""
        INSERT INTO orders (
            id, sender_id, recipient_id,
            phrase_1, phrase_2, phrase_3,
            gift_amount, gift_commission, total_amount,
            paid, delivered_to_recipient, reaction_uploaded, cashout_completed, sender_notified,
            stripe_session_id, stripe_payment_status,
            recipient_token, sender_token,
            reaction_video_local, reaction_video_public_url, gift_video_url,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        order_id, sender_id, recipient_id,
        (phrase_1 or "").strip(), (phrase_2 or "").strip(), (phrase_3 or "").strip(),
        gift_amount, gift_commission, total_amount,
        0, 0, 0, 0, 0,
        None, None,
        recipient_token, sender_token,
        None, None, DEFAULT_GIFT_VIDEO_URL or None,
        created_at, created_at
    ))

    conn.commit()
    conn.close()

    if not STRIPE_SECRET_KEY:
        update_order(order_id, paid=1, stripe_payment_status="test_no_stripe")
        order = get_order_by_id(order_id)
        try:
            send_whatsapp_recipient(
                phone=order["recipient_phone"],
                link=recipient_experience_url_from_order(order),
                message=build_recipient_message(order),
            )
        except Exception as e:
            print("WA recipient stub error:", e)

        return RedirectResponse(url=f"/post-pago/{order_id}", status_code=303)

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
                        "unit_amount": int(round(total_amount * 100)),
                    },
                    "quantity": 1,
                }
            ],
            success_url=f"{PUBLIC_BASE_URL}/checkout-exito/{order_id}",
            cancel_url=f"{PUBLIC_BASE_URL}/crear",
            client_reference_id=order_id,
            metadata={
                "order_id": order_id,
            },
        )
        update_order(order_id, stripe_session_id=session.id, stripe_payment_status="created")
        return RedirectResponse(url=session.url, status_code=303)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando checkout Stripe: {e}")

# =========================================================
# HOME / CREAR
# =========================================================

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
            html, body {
                margin: 0;
                min-height: 100%;
                background: #000;
            }
            body {
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
                max-width: 760px;
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 28px;
                padding: 42px 30px;
                text-align: center;
            }
            h1 {
                margin: 0 0 10px 0;
                font-size: 48px;
                letter-spacing: 3px;
            }
            .subtitle {
                color: rgba(255,255,255,0.80);
                font-size: 20px;
                line-height: 1.8;
                margin-top: 18px;
            }
            .soft {
                margin-top: 24px;
                color: rgba(255,255,255,0.50);
                font-size: 15px;
                line-height: 1.7;
            }
            .buttons {
                display: grid;
                gap: 14px;
                margin-top: 30px;
            }
            .btn {
                width: 100%;
                padding: 18px 24px;
                border-radius: 999px;
                border: 0;
                font-weight: bold;
                font-size: 16px;
                cursor: pointer;
                text-decoration: none;
                text-align: center;
                display: inline-block;
                background: white;
                color: black;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>ETERNA</h1>

            <div class="subtitle">
                Hay momentos que merecen quedarse para siempre
            </div>

            <div class="soft">
                No es un vídeo. Es un momento.
            </div>

            <div class="buttons">
                <a class="btn" href="/crear">CREAR MI ETERNA</a>
            </div>
        </div>
    </body>
    </html>
    """


@app.get("/crear", response_class=HTMLResponse)
def crear_get():
    return render_create_form()


@app.post("/crear")
def crear_post(
    customer_name: str = Form(...),
    customer_email: str = Form(""),
    customer_phone: str = Form(...),
    recipient_name: str = Form(...),
    recipient_phone: str = Form(...),
    phrase_1: str = Form(...),
    phrase_2: str = Form(...),
    phrase_3: str = Form(...),
    gift_amount: float = Form(0),
):
    return create_order_and_redirect(
        customer_name=customer_name,
        customer_email=customer_email,
        customer_phone=customer_phone,
        recipient_name=recipient_name,
        recipient_phone=recipient_phone,
        phrase_1=phrase_1,
        phrase_2=phrase_2,
        phrase_3=phrase_3,
        gift_amount=gift_amount,
    )


@app.post("/crear-eterna")
def crear_eterna_legacy(
    customer_name: str = Form(...),
    customer_email: str = Form(""),
    customer_phone: str = Form(...),
    recipient_name: str = Form(...),
    recipient_phone: str = Form(...),
    phrase_1: str = Form(...),
    phrase_2: str = Form(...),
    phrase_3: str = Form(...),
    gift_amount: float = Form(0),
):
    return create_order_and_redirect(
        customer_name=customer_name,
        customer_email=customer_email,
        customer_phone=customer_phone,
        recipient_name=recipient_name,
        recipient_phone=recipient_phone,
        phrase_1=phrase_1,
        phrase_2=phrase_2,
        phrase_3=phrase_3,
        gift_amount=gift_amount,
    )

# =========================================================
# CHECKOUT / WEBHOOK STRIPE
# =========================================================

@app.get("/checkout-exito/{order_id}", response_class=HTMLResponse)
def checkout_exito(order_id: str):
    order = get_order_by_id(order_id)
    is_paid = bool(order["paid"])

    refresh = '<meta http-equiv="refresh" content="4">' if not is_paid else ""
    redirect_script = f"""
        setTimeout(function() {{
            window.location.href = "/post-pago/{order_id}";
        }}, 3500);
    """ if is_paid else ""

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        {refresh}
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ETERNA</title>
        <style>
            html, body {{
                margin: 0;
                min-height: 100%;
                background: #000;
            }}
            body {{
                min-height: 100vh;
                background:
                    radial-gradient(circle at top, rgba(255,255,255,0.08), transparent 30%),
                    linear-gradient(180deg, #050505 0%, #000000 100%);
                color: white;
                font-family: Arial, sans-serif;
                display: flex;
                align-items: center;
                justify-content: center;
                text-align: center;
                padding: 24px;
            }}
            .card {{
                max-width: 680px;
                opacity: 0;
                transform: translateY(10px);
                animation: fadeIn 1.2s ease forwards;
            }}
            h1 {{
                font-size: 42px;
                margin-bottom: 18px;
                letter-spacing: 2px;
            }}
            .text {{
                font-size: 20px;
                line-height: 1.8;
                color: rgba(255,255,255,0.85);
            }}
            .soft {{
                margin-top: 24px;
                font-size: 14px;
                color: rgba(255,255,255,0.4);
            }}
            @keyframes fadeIn {{
                to {{
                    opacity: 1;
                    transform: translateY(0);
                }}
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Todo ya está en camino</h1>

            <div class="text">
                En unos instantes,<br>
                alguien va a vivir algo que no espera
            </div>

            <div class="soft">
                Y cuando ocurra… volverá a ti
            </div>
        </div>

        <script>
            {redirect_script}
        </script>
    </body>
    </html>
    """


@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=sig_header,
                secret=STRIPE_WEBHOOK_SECRET,
            )
        else:
            event = json.loads(payload.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook inválido: {e}")

    event_type = event.get("type")

    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        order_id = session.get("metadata", {}).get("order_id") or session.get("client_reference_id")
        if order_id:
            update_order(
                order_id,
                paid=1,
                stripe_payment_status="paid",
                stripe_session_id=session.get("id"),
            )

            try:
                order = get_order_by_id(order_id)
                send_whatsapp_recipient(
                    phone=order["recipient_phone"],
                    link=recipient_experience_url_from_order(order),
                    message=build_recipient_message(order),
                )
            except Exception as e:
                print("WA recipient stub error:", e)

    return {"received": True}

# =========================================================
# POST PAGO
# =========================================================

@app.get("/post-pago/{order_id}")
def post_pago(order_id: str):
    order = get_order_by_id(order_id)

    if not order["paid"]:
        return RedirectResponse(url=f"/checkout-exito/{order_id}", status_code=303)

    return RedirectResponse(url=f"/resumen/{order_id}", status_code=303)

# =========================================================
# RESUMEN REGALANTE
# =========================================================

@app.get("/resumen/{order_id}", response_class=HTMLResponse)
def resumen(order_id: str):
    order = get_order_by_id(order_id)

    sender_pack_url = sender_pack_url_from_order(order)

    recipient_whatsapp = whatsapp_link(
        order["recipient_phone"],
        build_recipient_message(order),
    )

    reaction_ready = reaction_exists(order)

    if reaction_ready:
        status_line = "Lo que creaste… volvió a ti"
        soft_line = "Tu enlace privado ya está listo."
        main_button = f"""
            <a href="{safe_attr(sender_pack_url)}" target="_blank" rel="noopener noreferrer">
                <button class="primary">Abrir mi ETERNA</button>
            </a>
        """
        extra_block = f"""
            <div class="private-link-box">
                <div class="private-link-label">Enlace privado</div>
                <div class="private-link-url">{safe_text(sender_pack_url)}</div>
            </div>

            <div class="buttons secondary-buttons">
                <button class="ghost" type="button" onclick="copySenderLink()">
                    Copiar enlace
                </button>
            </div>

            <script>
                async function copySenderLink() {{
                    const value = "{safe_attr(sender_pack_url)}";
                    const msg = document.getElementById("copyMsg");

                    try {{
                        await navigator.clipboard.writeText(value);
                        if (msg) msg.textContent = "Enlace copiado ❤️";
                    }} catch (err) {{
                        if (msg) msg.textContent = "No se pudo copiar ahora.";
                    }}
                }}
            </script>
        """
    else:
        status_line = "Ahora solo queda dejar que ocurra"
        soft_line = "Cuando todo pase, volverá aquí."
        main_button = f"""
            <a href="{safe_attr(recipient_whatsapp)}" target="_blank" rel="noopener noreferrer">
                <button class="whatsapp">Enviar ETERNA por WhatsApp</button>
            </a>
        """
        extra_block = ""

    estado_texto = "Volvió a ti" if reaction_ready else "Todavía en camino"

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta http-equiv="refresh" content="8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Resumen ETERNA</title>
        <style>
            * {{ box-sizing: border-box; }}
            html, body {{ margin: 0; min-height: 100%; background: #000; }}
            body {{
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
                max-width: 760px;
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 24px;
                padding: 32px 28px;
                text-align: center;
            }}
            .stats {{
                display: grid;
                gap: 12px;
                margin-top: 24px;
            }}
            .stat {{
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: 16px;
                padding: 16px;
            }}
            .label {{
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 1.2px;
                color: rgba(255,255,255,0.5);
            }}
            .value {{
                font-size: 22px;
                font-weight: bold;
                margin-top: 6px;
            }}
            .buttons {{
                display: grid;
                gap: 14px;
                margin-top: 28px;
            }}
            .secondary-buttons {{
                margin-top: 14px;
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
            .primary {{
                background: white;
                color: black;
            }}
            .ghost {{
                background: rgba(255,255,255,0.10);
                color: white;
                border: 1px solid rgba(255,255,255,0.10);
            }}
            a {{ text-decoration: none; }}
            .private-link-box {{
                margin-top: 18px;
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 16px;
                padding: 16px;
                text-align: left;
                word-break: break-word;
            }}
            .private-link-label {{
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 1.2px;
                color: rgba(255,255,255,0.5);
                margin-bottom: 8px;
            }}
            .private-link-url {{
                color: rgba(255,255,255,0.88);
                font-size: 14px;
                line-height: 1.6;
            }}
            .soft {{
                margin-top: 14px;
                color: rgba(255,255,255,0.45);
                font-size: 13px;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Tu ETERNA está lista</h1>
            <p>{safe_text(status_line)}</p>

            <div class="stats">
                <div class="stat">
                    <div class="label">Regalo</div>
                    <div class="value">{money(order["gift_amount"])}€</div>
                </div>
                <div class="stat">
                    <div class="label">Total</div>
                    <div class="value">{money(order["total_amount"])}€</div>
                </div>
                <div class="stat">
                    <div class="label">Estado</div>
                    <div class="value">{safe_text(estado_texto)}</div>
                </div>
            </div>

            <div class="buttons">
                {main_button}
            </div>

            {extra_block}

            <div class="soft" id="copyMsg">
                {safe_text(soft_line)}
            </div>
        </div>
    </body>
    </html>
    """

# =========================================================
# EXPERIENCIA DEL REGALADO
# =========================================================

@app.get("/pedido/{recipient_token}", response_class=HTMLResponse)
def pedido(recipient_token: str):
    order = get_order_by_recipient_token_or_404(recipient_token)

    if not order["paid"]:
        return HTMLResponse("""
        <!DOCTYPE html>
        <html lang="es">
        <body style="background:#000;color:white;text-align:center;padding-top:100px;font-family:Arial;">
            <h1>Esta ETERNA aún no está disponible</h1>
        </body>
        </html>
        """)

    update_order(order["id"], delivered_to_recipient=1)

    recipient_name = safe_text(order["recipient_name"])
    phrase_1 = safe_text(order["phrase_1"])
    phrase_2 = safe_text(order["phrase_2"])
    phrase_3 = safe_text(order["phrase_3"])
    gift_amount = money(order["gift_amount"])
    gift_video_url = (order.get("gift_video_url") or "").strip()

    gift_video_block = ""
    if gift_video_url:
        safe_gift_video = safe_attr(gift_video_url)
        gift_video_block = f"""
                {{
                    html: `
                        <div style="margin-top:18px;">
                            <video controls autoplay playsinline style="width:100%;max-width:780px;border-radius:18px;background:#111;">
                                <source src="{safe_gift_video}" type="video/mp4">
                                <source src="{safe_gift_video}" type="video/webm">
                                Tu navegador no puede reproducir este vídeo.
                            </video>
                        </div>
                    `,
                    duration: 32000
                }},
        """
    else:
        gift_video_block = f"""
                {{
                    html: "<h2>{phrase_1}</h2>",
                    duration: 10667
                }},
                {{
                    html: "<h2>{phrase_2}</h2>",
                    duration: 10667
                }},
                {{
                    html: "<h2>{phrase_3}</h2>",
                    duration: 10666
                }},
        """

    return f"""
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
                width: 100%;
                min-height: 100%;
                background: #000;
            }}
            body {{
                background: #000;
                color: white;
                font-family: Arial, sans-serif;
                text-align: center;
                overflow-y: auto;
                -webkit-overflow-scrolling: touch;
            }}
            .screen {{
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                flex-direction: column;
                padding: 24px;
                background: #000;
            }}
            .hidden {{
                display: none;
            }}
            .gate-card {{
                width: 100%;
                max-width: 620px;
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 28px;
                padding: 38px 30px;
                text-align: center;
            }}
            .gate-card h1 {{
                font-size: 42px;
                margin-bottom: 18px;
            }}
            .consent-row {{
                margin-top: 22px;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 12px;
                color: rgba(255,255,255,0.88);
                font-size: 14px;
                line-height: 1.7;
                cursor: pointer;
                user-select: none;
                opacity: 0.95;
            }}
            .consent-row input {{
                width: 24px;
                height: 24px;
                margin-top: 0;
                accent-color: #00ff88;
                cursor: pointer;
            }}
            #startBtn {{
                width: 100%;
                padding: 16px 24px;
                border-radius: 999px;
                border: 0;
                background: white;
                color: black;
                font-weight: bold;
                cursor: pointer;
                margin-top: 20px;
                font-size: 15px;
                -webkit-appearance: none;
                appearance: none;
                opacity: 0.45;
            }}
            #startBtn.enabled {{
                opacity: 1;
            }}
            #experience {{
                background: #000;
            }}
            #content {{
                width: 100%;
                max-width: 920px;
                padding: 24px;
                opacity: 0;
                transform: translateY(10px);
                transition: opacity 0.6s ease, transform 0.6s ease;
            }}
            #content.visible {{
                opacity: 1;
                transform: translateY(0);
            }}
            #content h2 {{
                font-size: 44px;
                line-height: 1.3;
                margin: 0;
                font-weight: 600;
                color: white;
                white-space: pre-line;
            }}
            #content p {{
                color: rgba(255,255,255,0.78);
                margin-top: 16px;
                line-height: 1.6;
                font-size: 18px;
            }}
            @media (max-width: 640px) {{
                .gate-card h1 {{
                    font-size: 32px;
                }}
                #content h2 {{
                    font-size: 34px;
                }}
                #content p {{
                    font-size: 16px;
                }}
            }}
        </style>
    </head>
    <body>

        <div id="start" class="screen">
            <div class="gate-card">
                <h1>Hay algo para ti</h1>

                <label class="consent-row" id="consentLabel" for="consentCheck">
                    <input type="checkbox" id="consentCheck">
                    <span>Continúa cuando quieras</span>
                </label>

                <button id="startBtn" type="button" onclick="startExperience()" disabled>
                    Vivirlo
                </button>
            </div>
        </div>

        <div id="experience" class="screen hidden">
            <div id="content"></div>
        </div>

        <script>
            let recorder = null;
            let chunks = [];
            let currentStream = null;
            let mediaMimeType = "video/webm";
            let autoStopped = false;

            document.addEventListener("DOMContentLoaded", () => {{
                const consentCheck = document.getElementById("consentCheck");
                const startBtn = document.getElementById("startBtn");

                let ready = false;

                function updateButton() {{
                    const enabled = consentCheck.checked && ready;
                    startBtn.disabled = !enabled;

                    if (enabled) {{
                        startBtn.classList.add("enabled");
                    }} else {{
                        startBtn.classList.remove("enabled");
                    }}
                }}

                setTimeout(() => {{
                    ready = true;
                    updateButton();
                }}, 1200);

                consentCheck.addEventListener("change", updateButton);
                updateButton();
            }});

            const scenes = [
                {{
                    html: "<h2>Para ti</h2>",
                    duration: 1800
                }},
                {{
                    html: "<h2>…</h2>",
                    duration: 1200
                }},
                {{
                    html: "<h2>Esto no es casualidad</h2>",
                    duration: 2200
                }},
                {gift_video_block}
                {{
                    html: "<h2>💸</h2><h2>Alguien ha querido cuidarte<br>con este regalo en dinero</h2><p>{gift_amount}€</p>",
                    duration: 5000
                }}
            ];

            function wait(ms) {{
                return new Promise(resolve => setTimeout(resolve, ms));
            }}

            async function showScene(htmlContent, duration) {{
                const content = document.getElementById("content");
                content.classList.remove("visible");
                await wait(120);
                content.innerHTML = htmlContent;
                await wait(30);
                content.classList.add("visible");
                await wait(duration);
            }}

            async function runCountdown() {{
                const content = document.getElementById("content");
                const steps = ["3", "2", "1"];

                for (let step of steps) {{
                    content.classList.remove("visible");
                    await wait(100);
                    content.innerHTML = "<h2>" + step + "</h2>";
                    await wait(30);
                    content.classList.add("visible");
                    await wait(700);
                }}
            }}

            async function sendVideo() {{
                try {{
                    if (!chunks.length) {{
                        return null;
                    }}

                    const blob = new Blob(chunks, {{ type: mediaMimeType }});
                    if (!blob || blob.size === 0) {{
                        return null;
                    }}

                    const formData = new FormData();
                    formData.append("recipient_token", "{safe_attr(order['recipient_token'])}");
                    formData.append("video", blob, "{safe_attr(order['id'])}.webm");

                    const response = await fetch("/upload-video", {{
                        method: "POST",
                        body: formData
                    }});

                    if (!response.ok) {{
                        return null;
                    }}

                    return await response.json();
                }} catch (err) {{
                    console.log("Error subiendo vídeo:", err);
                    return null;
                }}
            }}

            async function stopRecordingAndUpload() {{
                if (autoStopped) {{
                    return null;
                }}
                autoStopped = true;

                if (recorder && recorder.state !== "inactive") {{
                    await new Promise((resolve) => {{
                        const oldOnStop = recorder.onstop;

                        recorder.onstop = (event) => {{
                            if (oldOnStop) {{
                                try {{
                                    oldOnStop(event);
                                }} catch (e) {{}}
                            }}
                            resolve();
                        }};

                        try {{
                            recorder.stop();
                        }} catch (e) {{
                            resolve();
                        }}
                    }});
                }}

                if (currentStream) {{
                    currentStream.getTracks().forEach(track => track.stop());
                    currentStream = null;
                }}

                await wait(500);
                return await sendVideo();
            }}

            async function autoStopAndGo() {{
                const content = document.getElementById("content");
                content.classList.remove("visible");
                await wait(120);
                content.innerHTML = "<h2>…</h2>";
                await wait(30);
                content.classList.add("visible");

                const uploadResult = await stopRecordingAndUpload();

                if (uploadResult && uploadResult.cashout_url) {{
                    window.location.href = uploadResult.cashout_url;
                    return;
                }}

                window.location.href = "/cobrar/{safe_attr(order['recipient_token'])}";
            }}

            async function startExperience() {{
                try {{
                    const stream = await navigator.mediaDevices.getUserMedia({{
                        video: {{
                            width: 640,
                            height: 480,
                            facingMode: "user"
                        }},
                        audio: true
                    }});

                    currentStream = stream;
                    chunks = [];
                    autoStopped = false;

                    document.getElementById("start").classList.add("hidden");
                    document.getElementById("experience").classList.remove("hidden");

                    try {{
                        let options = {{}};

                        if (window.MediaRecorder && MediaRecorder.isTypeSupported("video/webm;codecs=vp8,opus")) {{
                            options = {{
                                mimeType: "video/webm;codecs=vp8,opus",
                                videoBitsPerSecond: 900000,
                                audioBitsPerSecond: 64000
                            }};
                            mediaMimeType = "video/webm";
                        }} else if (window.MediaRecorder && MediaRecorder.isTypeSupported("video/webm")) {{
                            options = {{
                                mimeType: "video/webm",
                                videoBitsPerSecond: 900000,
                                audioBitsPerSecond: 64000
                            }};
                            mediaMimeType = "video/webm";
                        }} else {{
                            options = {{}};
                            mediaMimeType = "video/webm";
                        }}

                        recorder = new MediaRecorder(stream, options);

                        recorder.ondataavailable = (e) => {{
                            if (e.data && e.data.size > 0) {{
                                chunks.push(e.data);
                            }}
                        }};

                        recorder.start(300);
                    }} catch (err) {{
                        recorder = null;
                    }}

                    await runExperience();
                }} catch (e) {{
                    alert("Necesitamos acceso a cámara y micrófono para continuar.");
                }}
            }}

            async function runExperience() {{
                await runCountdown();

                for (const scene of scenes) {{
                    await showScene(scene.html, scene.duration);
                }}

                await wait(5000);
                await autoStopAndGo();
            }}
        </script>
    </body>
    </html>
    """

# =========================================================
# SUBIR VIDEO
# =========================================================

@app.post("/upload-video")
async def upload_video(
    recipient_token: str = Form(...),
    video: UploadFile = File(...),
):
    order = get_order_by_recipient_token_or_404(recipient_token)

    if not order["paid"]:
        raise HTTPException(status_code=403, detail="Pedido no pagado")

    content_type = (video.content_type or "").lower().strip()
    filename = (video.filename or "").lower().strip()

    is_allowed_type = content_type in ALLOWED_VIDEO_TYPES
    is_allowed_name = filename.endswith(".webm") or filename.endswith(".mp4")

    if not is_allowed_type and not is_allowed_name:
        raise HTTPException(status_code=400, detail="Formato de vídeo no permitido")

    filepath = reaction_video_path(order["id"])
    total_size = 0

    try:
        with open(filepath, "wb") as f:
            while True:
                chunk = await video.read(1024 * 1024)
                if not chunk:
                    break

                total_size += len(chunk)
                if total_size > MAX_VIDEO_SIZE:
                    f.close()
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    raise HTTPException(status_code=400, detail="Vídeo demasiado grande")

                f.write(chunk)

        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            raise HTTPException(status_code=400, detail="Vídeo vacío")

        public_video_url = None
        try:
            public_video_url = upload_video_to_r2(filepath, f"{order['id']}.webm", "video/webm")
        except Exception as e:
            print("Error subiendo a R2:", e)

        update_order(
            order["id"],
            reaction_video_local=filepath,
            reaction_video_public_url=public_video_url,
            reaction_uploaded=1,
        )

        if public_video_url:
            insert_asset(order["id"], "reaction_video", public_video_url, "r2")
        else:
            insert_asset(order["id"], "reaction_video", f"{PUBLIC_BASE_URL}/video/{order['id']}", "local")

        updated_order = get_order_by_id(order["id"])

        try:
            send_whatsapp_sender(
                phone=updated_order["sender_phone"],
                link=sender_pack_url_from_order(updated_order),
                message=build_sender_ready_message(updated_order),
            )
        except Exception as e:
            print("WA sender stub error:", e)

        return JSONResponse({
            "status": "ok",
            "reaction_url": f"{PUBLIC_BASE_URL}/reaccion/{updated_order['recipient_token']}",
            "cashout_url": f"{PUBLIC_BASE_URL}/cobrar/{updated_order['recipient_token']}",
            "public_video_url": updated_order.get("reaction_video_public_url"),
            "sender_pack_url": sender_pack_url_from_order(updated_order),
        })
    finally:
        await video.close()

# =========================================================
# VIDEO FILE
# =========================================================

@app.get("/video/{order_id}")
def get_video(order_id: str):
    order = get_order_by_id(order_id)

    filepath = order.get("reaction_video_local")
    if not filepath or not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Vídeo no encontrado")

    return FileResponse(filepath, media_type="video/webm", filename=f"{order_id}.webm")

# =========================================================
# COBRAR
# =========================================================

@app.get("/cobrar/{recipient_token}", response_class=HTMLResponse)
def cobrar(recipient_token: str):
    order = get_order_by_recipient_token_or_404(recipient_token)

    if not reaction_exists(order):
        return RedirectResponse(url=f"/pedido/{recipient_token}", status_code=303)

    amount_text = format_amount_display(order["gift_amount"])

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Cobrar regalo</title>
        <style>
            * {{
                box-sizing: border-box;
            }}
            html, body {{
                margin: 0;
                min-height: 100%;
                background: #000;
            }}
            body {{
                min-height: 100vh;
                background:
                    radial-gradient(circle at top, rgba(255,255,255,0.08), transparent 35%),
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
                max-width: 760px;
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 28px;
                padding: 40px 28px;
                text-align: center;
            }}
            .eyebrow {{
                font-size: 12px;
                letter-spacing: 0.22em;
                text-transform: uppercase;
                color: rgba(255,255,255,0.50);
                margin-bottom: 14px;
            }}
            h1 {{
                margin: 0 0 16px 0;
                font-size: 40px;
                line-height: 1.15;
            }}
            .lead {{
                max-width: 520px;
                margin: 0 auto;
                color: rgba(255,255,255,0.84);
                font-size: 18px;
                line-height: 1.8;
            }}
            .money-box {{
                margin-top: 24px;
                padding: 24px 20px;
                border-radius: 22px;
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.08);
            }}
            .money-label {{
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 1.2px;
                color: rgba(255,255,255,0.50);
                margin-bottom: 8px;
            }}
            .money-value {{
                font-size: 42px;
                font-weight: bold;
                line-height: 1;
                margin-bottom: 10px;
            }}
            .actions {{
                display: grid;
                gap: 12px;
                margin-top: 24px;
            }}
            .btn {{
                display: inline-block;
                width: 100%;
                padding: 16px 22px;
                border-radius: 999px;
                border: 0;
                font-weight: bold;
                font-size: 15px;
                cursor: pointer;
                text-decoration: none;
                text-align: center;
            }}
            .btn-primary {{
                background: white;
                color: black;
            }}
            .btn-secondary {{
                background: rgba(255,255,255,0.10);
                color: white;
                border: 1px solid rgba(255,255,255,0.10);
            }}
            .soft {{
                margin-top: 20px;
                color: rgba(255,255,255,0.46);
                font-size: 14px;
                line-height: 1.7;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="eyebrow">ETERNA</div>

            <h1>Aquí está lo que te han dejado</h1>

            <div class="lead">
                Y lo que sentiste… ya no se pierde
            </div>

            <div class="money-box">
                <div class="money-label">Regalo</div>
                <div class="money-value">{amount_text}</div>
            </div>

            <div class="actions">
                <a class="btn btn-primary" href="/iniciar-cobro/{safe_attr(recipient_token)}">
                    Recibirlo
                </a>

                <a class="btn btn-secondary" href="/reaccion/{safe_attr(recipient_token)}">
                    Ver cierre
                </a>
            </div>

            <div class="soft">
                …
            </div>
        </div>
    </body>
    </html>
    """


@app.get("/iniciar-cobro/{recipient_token}", response_class=HTMLResponse)
def iniciar_cobro(recipient_token: str):
    order = get_order_by_recipient_token_or_404(recipient_token)

    if not reaction_exists(order):
        return RedirectResponse(url=f"/pedido/{recipient_token}", status_code=303)

    amount_text = format_amount_display(order["gift_amount"])

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Iniciar cobro</title>
        <style>
            * {{
                box-sizing: border-box;
            }}
            html, body {{
                margin: 0;
                min-height: 100%;
                background: #000;
            }}
            body {{
                min-height: 100vh;
                background:
                    radial-gradient(circle at top, rgba(255,255,255,0.08), transparent 35%),
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
                max-width: 760px;
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 28px;
                padding: 40px 28px;
                text-align: center;
            }}
            .eyebrow {{
                font-size: 12px;
                letter-spacing: 0.22em;
                text-transform: uppercase;
                color: rgba(255,255,255,0.50);
                margin-bottom: 14px;
            }}
            h1 {{
                margin: 0 0 16px 0;
                font-size: 38px;
                line-height: 1.15;
            }}
            .lead {{
                max-width: 540px;
                margin: 0 auto;
                color: rgba(255,255,255,0.84);
                font-size: 17px;
                line-height: 1.8;
            }}
            .amount-box {{
                margin-top: 24px;
                padding: 24px 20px;
                border-radius: 22px;
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.08);
            }}
            .amount-label {{
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 1.2px;
                color: rgba(255,255,255,0.50);
                margin-bottom: 8px;
            }}
            .amount-value {{
                font-size: 40px;
                font-weight: bold;
                line-height: 1;
            }}
            .actions {{
                display: grid;
                gap: 12px;
                margin-top: 24px;
            }}
            .btn {{
                display: inline-block;
                width: 100%;
                padding: 16px 22px;
                border-radius: 999px;
                border: 0;
                font-weight: bold;
                font-size: 15px;
                cursor: pointer;
                text-decoration: none;
                text-align: center;
            }}
            .btn-primary {{
                background: white;
                color: black;
            }}
            .btn-secondary {{
                background: rgba(255,255,255,0.10);
                color: white;
                border: 1px solid rgba(255,255,255,0.10);
            }}
            .soft {{
                margin-top: 18px;
                color: rgba(255,255,255,0.46);
                font-size: 14px;
                line-height: 1.7;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="eyebrow">ETERNA</div>

            <h1>Tu cobro estará listo aquí</h1>

            <div class="lead">
                El siguiente paso ya está preparado
            </div>

            <div class="amount-box">
                <div class="amount-label">Importe preparado</div>
                <div class="amount-value">{amount_text}</div>
            </div>

            <div class="actions">
                <a class="btn btn-primary" href="/cobro-completado/{safe_attr(recipient_token)}">
                    Continuar
                </a>

                <a class="btn btn-secondary" href="/cobrar/{safe_attr(recipient_token)}">
                    Volver
                </a>
            </div>

            <div class="soft">
                …
            </div>
        </div>
    </body>
    </html>
    """


@app.get("/cobro-completado/{recipient_token}")
def cobro_completado(recipient_token: str):
    order = get_order_by_recipient_token_or_404(recipient_token)
    update_order(order["id"], cashout_completed=1)
    return RedirectResponse(url=f"/reaccion/{recipient_token}", status_code=303)

# =========================================================
# CIERRE DEL REGALADO
# =========================================================

@app.get("/reaccion/{recipient_token}", response_class=HTMLResponse)
def reaccion(recipient_token: str):
    order = get_order_by_recipient_token_or_404(recipient_token)

    if not reaction_exists(order):
        return HTMLResponse("""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta http-equiv="refresh" content="5">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>ETERNA</title>
            <style>
                body {
                    margin: 0;
                    min-height: 100vh;
                    background: #000;
                    color: white;
                    font-family: Arial, sans-serif;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    padding: 24px;
                    text-align: center;
                }
            </style>
        </head>
        <body>
            <div>
                <h1>…</h1>
            </div>
        </body>
        </html>
        """)

    if not order.get("cashout_completed"):
        return RedirectResponse(url=f"/cobrar/{recipient_token}", status_code=303)

    gift_video_url = (order.get("gift_video_url") or "").strip()
    video_block = ""
    share_block = ""

    if gift_video_url:
        safe_gift_video_url = safe_attr(gift_video_url)
        share_text = "No sé cómo explicarte esto... solo míralo ❤️"
        full_share_text = share_text + "\n\n" + gift_video_url
        whatsapp_fallback = f"https://wa.me/?text={urllib.parse.quote(full_share_text)}"

        video_block = f"""
        <div class="video-wrap">
            <video controls playsinline preload="metadata">
                <source src="{safe_gift_video_url}" type="video/mp4">
                <source src="{safe_gift_video_url}" type="video/webm">
                Tu navegador no puede reproducir este vídeo.
            </video>
        </div>
        """

        share_block = f"""
        <div class="actions">
            <button class="btn primary" type="button" onclick="shareGiftVideo()">
                Compartir
            </button>
        </div>

        <script>
            async function shareGiftVideo() {{
                const url = "{safe_attr(gift_video_url)}";
                const shareText = "No sé cómo explicarte esto... solo míralo ❤️";
                const fullText = shareText + "\\n\\n" + url;
                const whatsappFallback = "{safe_attr(whatsapp_fallback)}";
                const msg = document.getElementById("copyMsg");

                try {{
                    if (navigator.share) {{
                        await navigator.share({{
                            title: "ETERNA",
                            text: shareText,
                            url: url
                        }});
                        return;
                    }}
                }} catch (err) {{
                    if (String(err).toLowerCase().includes("abort")) {{
                        return;
                    }}
                }}

                try {{
                    window.location.href = whatsappFallback;
                    return;
                }} catch (err) {{}}

                try {{
                    await navigator.clipboard.writeText(fullText);
                    if (msg) {{
                        msg.textContent = "Enlace copiado ❤️";
                    }}
                }} catch (err) {{
                    if (msg) {{
                        msg.textContent = "No se pudo compartir ahora.";
                    }}
                }}
            }}
        </script>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ETERNA</title>
        <style>
            html, body {{
                margin: 0;
                min-height: 100%;
                background: #000;
            }}
            body {{
                min-height: 100vh;
                background:
                    radial-gradient(circle at top, rgba(255,255,255,0.06), transparent 30%),
                    linear-gradient(180deg, #050505 0%, #000000 100%);
                color: white;
                font-family: Arial, sans-serif;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 24px;
                text-align: center;
            }}
            .card {{
                width: 100%;
                max-width: 760px;
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 28px;
                padding: 42px 30px;
            }}
            h1 {{
                margin: 0 0 18px 0;
                font-size: 40px;
                letter-spacing: 1px;
            }}
            .lead {{
                color: rgba(255,255,255,0.84);
                line-height: 1.8;
                font-size: 20px;
                margin: 0;
            }}
            .video-wrap {{
                margin-top: 26px;
            }}
            video {{
                width: 100%;
                border-radius: 18px;
                background: #111;
                display: block;
            }}
            .actions {{
                display: grid;
                gap: 12px;
                margin-top: 22px;
            }}
            .btn {{
                width: 100%;
                padding: 16px 22px;
                border-radius: 999px;
                border: 0;
                font-weight: bold;
                font-size: 15px;
                cursor: pointer;
            }}
            .primary {{
                background: white;
                color: black;
            }}
            .soft {{
                margin-top: 24px;
                color: rgba(255,255,255,0.42);
                font-size: 14px;
                line-height: 1.7;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Este momento ya es tuyo</h1>

            <div class="lead">
                Y también de quien lo creó
            </div>

            {video_block}

            {share_block}

            <div class="soft" id="copyMsg">
                Si quieres… puedes compartirlo
            </div>
        </div>
    </body>
    </html>
    """

# =========================================================
# SENDER PACK
# =========================================================

@app.get("/sender/{sender_token}", response_class=HTMLResponse)
def sender_pack(sender_token: str):
    order = get_order_by_sender_token_or_404(sender_token)

    gift_video_url = (order.get("gift_video_url") or "").strip()
    reaction_video_url = order.get("reaction_video_public_url") or (
        f"/video/{order['id']}" if reaction_exists(order) else None
    )

    if not reaction_video_url:
        return HTMLResponse("""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta http-equiv="refresh" content="5">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>ETERNA</title>
            <style>
                body {
                    margin: 0;
                    min-height: 100vh;
                    background: #000;
                    color: white;
                    font-family: Arial, sans-serif;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    padding: 24px;
                    text-align: center;
                }
            </style>
        </head>
        <body>
            <div>
                <h1>…</h1>
            </div>
        </body>
        </html>
        """)

    safe_gift = safe_attr(gift_video_url or "")
    safe_reaction = safe_attr(reaction_video_url)

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Sender Pack ETERNA</title>
        <style>
            * {{ box-sizing: border-box; }}
            html, body {{
                margin: 0;
                min-height: 100%;
                background: #000;
            }}
            body {{
                min-height: 100vh;
                background:
                    radial-gradient(circle at top, rgba(255,255,255,0.06), transparent 30%),
                    linear-gradient(180deg, #050505 0%, #000000 100%);
                color: white;
                font-family: Arial, sans-serif;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 24px;
            }}
            .card {{
                width: 100%;
                max-width: 760px;
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 24px;
                padding: 28px;
            }}
            h1 {{
                margin: 0 0 22px 0;
                text-align: center;
                font-size: 34px;
            }}
            .video-stack {{
                display: grid;
                gap: 16px;
            }}
            .video-block {{
                width: 100%;
            }}
            video {{
                width: 100%;
                aspect-ratio: 16 / 9;
                object-fit: cover;
                border-radius: 16px;
                background: #111;
                display: block;
            }}
            .buttons {{
                display: grid;
                gap: 12px;
                margin-top: 22px;
            }}
            .btn {{
                width: 100%;
                padding: 16px 22px;
                border-radius: 999px;
                border: 0;
                font-weight: bold;
                font-size: 15px;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                text-align: center;
            }}
            .ghost {{
                background: rgba(255,255,255,0.10);
                color: white;
                border: 1px solid rgba(255,255,255,0.10);
            }}
            .soft {{
                margin-top: 16px;
                text-align: center;
                color: rgba(255,255,255,0.42);
                font-size: 13px;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Lo que hiciste ya es para siempre</h1>

            <div class="video-stack">
                {f'''
                <div class="video-block">
                    <video id="giftVideo" playsinline controls preload="metadata">
                        <source src="{safe_gift}" type="video/mp4">
                        <source src="{safe_gift}" type="video/webm">
                        Tu navegador no puede reproducir este vídeo.
                    </video>
                </div>
                ''' if gift_video_url else ""}

                <div class="video-block">
                    <video id="reactionVideo" playsinline controls preload="metadata" autoplay>
                        <source src="{safe_reaction}" type="video/webm">
                        <source src="{safe_reaction}" type="video/mp4">
                        Tu navegador no puede reproducir este vídeo.
                    </video>
                </div>
            </div>

            <div class="buttons">
                <a class="btn ghost" href="/">Crear otra ETERNA</a>
            </div>

            <div class="soft">
                Lo que creaste… volvió a ti
            </div>
        </div>

        <script>
            const giftVideo = document.getElementById("giftVideo");
            const reactionVideo = document.getElementById("reactionVideo");

            function syncPlay() {{
                if (giftVideo) {{
                    try {{
                        giftVideo.currentTime = 0;
                    }} catch (e) {{}}
                }}
                if (reactionVideo) {{
                    try {{
                        reactionVideo.currentTime = 0;
                    }} catch (e) {{}}
                }}

                if (giftVideo) {{
                    giftVideo.play().catch(() => {{}});
                }}
                if (reactionVideo) {{
                    reactionVideo.play().catch(() => {{}});
                }}
            }}

            window.addEventListener("load", () => {{
                syncPlay();
            }});
        </script>
    </body>
    </html>
    """

# =========================================================
# DEMO
# =========================================================

@app.get("/upload-demo/{order_id}")
def upload_demo(order_id: str):
    order = get_order_by_id(order_id)

    demo_url = "https://samplelib.com/lib/preview/mp4/sample-5s.mp4"
    update_order(
        order["id"],
        reaction_video_public_url=demo_url,
        reaction_uploaded=1,
    )
    insert_asset(order["id"], "reaction_video", demo_url, "demo")

    updated = get_order_by_id(order_id)
    return RedirectResponse(url=f"/sender/{updated['sender_token']}", status_code=303)

# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
def health():
    return {
        "status": "ok",
        "app": "ETERNA V21.1 CLEAN SAFE",
        "stripe_configured": bool(STRIPE_SECRET_KEY),
        "stripe_webhook_configured": bool(STRIPE_WEBHOOK_SECRET),
        "r2_configured": r2_enabled(),
        "public_base_url": PUBLIC_BASE_URL,
        "orders": get_orders_count(),
        "assets": get_assets_count(),
    }

# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 10000))

    print(f"🚀 Starting server on port {port}")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
    )