import html
import os
import urllib.parse
import uuid
from pathlib import Path

import boto3
import stripe
from botocore.client import Config
from fastapi import FastAPI, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse

app = FastAPI(title="ETERNA V11 R2 FULL")

# =========================
# CONFIG
# =========================

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
PUBLIC_BASE_URL = os.getenv(
    "PUBLIC_BASE_URL",
    "https://eterna-v2-lab.onrender.com",
).strip().rstrip("/")

BASE_PRICE = float(os.getenv("ETERNA_BASE_PRICE", "29"))
CURRENCY = os.getenv("ETERNA_CURRENCY", "eur").strip().lower()
COMMISSION_RATE = float(os.getenv("GIFT_COMMISSION_RATE", "0.05"))

R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY", "").strip()
R2_SECRET_KEY = os.getenv("R2_SECRET_KEY", "").strip()
R2_BUCKET = os.getenv("R2_BUCKET", "").strip()
R2_ENDPOINT = os.getenv("R2_ENDPOINT", "").strip().rstrip("/")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "").strip().rstrip("/")

MAX_VIDEO_SIZE = 30 * 1024 * 1024  # 30 MB
ALLOWED_VIDEO_TYPES = {"video/webm", "video/mp4"}

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

VIDEO_FOLDER = Path("videos")
VIDEO_FOLDER.mkdir(parents=True, exist_ok=True)

orders: dict[str, dict] = {}


# =========================
# HELPERS
# =========================

def safe_text(v: str) -> str:
    return html.escape(str(v or "").strip())


def money(v: float) -> str:
    return f"{float(v):.2f}"


def normalize_phone(p: str) -> str:
    raw = "".join(ch for ch in str(p or "") if ch.isdigit() or ch == "+")
    if raw.startswith("00"):
        raw = "+" + raw[2:]
    return "".join(ch for ch in raw if ch.isdigit())


def whatsapp_link(phone: str, message: str) -> str:
    return f"https://wa.me/{normalize_phone(phone)}?text={urllib.parse.quote(message)}"


def reaction_video_path(order_id: str) -> str:
    return str(VIDEO_FOLDER / f"{order_id}.webm")


def reaction_exists(order: dict) -> bool:
    if order.get("reaction_public_url"):
        return True
    filepath = order.get("reaction_video")
    return bool(filepath) and os.path.exists(filepath)


def get_order_or_404(order_id: str) -> dict:
    order = orders.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    return order


# =========================
# R2
# =========================

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


def upload_video_to_r2(local_path: str, remote_name: str) -> str | None:
    client = get_r2_client()
    if not client:
        return None

    client.upload_file(
        local_path,
        R2_BUCKET,
        remote_name,
        ExtraArgs={"ContentType": "video/webm"},
    )
    return f"{R2_PUBLIC_URL}/{remote_name}"


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
                max-width: 680px;
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 24px;
                padding: 28px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.35);
            }}

            h1 {{
                margin: 0 0 10px 0;
                font-size: 40px;
                letter-spacing: 2px;
                text-align: center;
            }}

            .subtitle {{
                text-align: center;
                color: rgba(255,255,255,0.75);
                margin-bottom: 28px;
                line-height: 1.5;
            }}

            .section-title {{
                margin: 22px 0 10px 0;
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

            button {{
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
            }}

            .footer-note {{
                margin-top: 18px;
                text-align: center;
                color: rgba(255,255,255,0.40);
                font-size: 12px;
                line-height: 1.5;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>ETERNA</h1>

            <div class="subtitle">
                Convierte emoción en un regalo inolvidable.<br>
                MVP actual: 3 frases + dinero + reacción grabada.
            </div>

            <form action="/crear-eterna" method="post">
                <div class="section-title">Tus datos</div>
                <input name="customer_name" placeholder="Tu nombre" required>
                <input name="customer_email" type="email" placeholder="Tu email" required>
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

                <button type="submit">CREAR MI ETERNA</button>
            </form>

            <div class="footer-note">
                Futuro: sustituiremos las frases por un vídeo emocional real.<br>
                El core actual ya es la reacción grabada + envío.
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
        "reaction_video": None,
        "reaction_uploaded": False,
        "cashout_completed": False,
        "reaction_public_url": None,
    }

    if not STRIPE_SECRET_KEY:
        return RedirectResponse(url=f"{PUBLIC_BASE_URL}/post-pago/{order_id}", status_code=303)

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
    order = get_order_or_404(order_id)
    order["paid"] = True
    return RedirectResponse(url=f"/resumen/{order_id}", status_code=303)


# =========================
# RESUMEN REGALANTE
# =========================

@app.get("/resumen/{order_id}", response_class=HTMLResponse)
def resumen(order_id: str):
    order = get_order_or_404(order_id)

    experiencia_url = f"{PUBLIC_BASE_URL}/pedido/{order_id}"
    whatsapp_experiencia_url = whatsapp_link(
        order["recipient_phone"],
        (
            f"Hola ❤️\n\n"
            f"{order['customer_name']} te ha enviado algo especial.\n\n"
            f"Ábrelo aquí:\n{experiencia_url}"
        ),
    )

    has_reaction = reaction_exists(order)

    if has_reaction:
        reaction_share_target = f"{PUBLIC_BASE_URL}/reaccion/{order_id}"

        regalante_whatsapp_url = whatsapp_link(
            order["customer_phone"],
            (
                f"No sé cómo explicarlo... pero este momento ya forma parte de ETERNA ❤️\n\n"
                f"Mira la reacción aquí:\n{reaction_share_target}"
            ),
        )

        main_cta = f"""
            <a href="{regalante_whatsapp_url}" target="_blank">
                <button class="light main-btn">Enviar reacción al regalante ❤️</button>
            </a>
            <a href="/reaccion/{order_id}" target="_blank">
                <button class="ghost main-btn">Ver emoción final</button>
            </a>
        """
        subtitle = "La emoción ya ha quedado guardada."
        video_status = "Vídeo guardado"
        soft_text = "Ya puedes enviarla al regalante o abrirla ahora."
    else:
        main_cta = f"""
            <a href="{whatsapp_experiencia_url}" target="_blank">
                <button class="whatsapp main-btn">Enviar ETERNA por WhatsApp</button>
            </a>
        """
        subtitle = "Ahora empieza lo importante: su reacción."
        video_status = "Pendiente de recibir"
        soft_text = "Esta página se actualiza sola cada pocos segundos para detectar la reacción."

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta http-equiv="refresh" content="8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Resumen ETERNA</title>
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
                max-width: 720px;
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 24px;
                padding: 34px 28px;
                text-align: center;
            }}
            h1 {{
                margin: 0 0 12px 0;
            }}
            p {{
                color: rgba(255,255,255,0.76);
                line-height: 1.6;
            }}
            .stats {{
                margin-top: 24px;
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
                margin-top: 30px;
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
            .main-btn {{
                padding: 18px 22px;
                font-size: 16px;
            }}
            .whatsapp {{
                background: #25D366;
                color: white;
            }}
            .light {{
                background: white;
                color: black;
            }}
            .ghost {{
                background: rgba(255,255,255,0.10);
                color: white;
                border: 1px solid rgba(255,255,255,0.10);
            }}
            .soft {{
                color: rgba(255,255,255,0.45);
                font-size: 13px;
                margin-top: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Tu ETERNA está lista ❤️</h1>
            <p>{safe_text(subtitle)}</p>

            <div class="stats">
                <div class="stat">
                    <div class="stat-label">Regalo</div>
                    <div class="stat-value">{money(order["gift_amount"])}€</div>
                </div>
                <div class="stat">
                    <div class="stat-label">Total cobrado</div>
                    <div class="stat-value">{money(order["total"])}€</div>
                </div>
                <div class="stat">
                    <div class="stat-label">Reacción</div>
                    <div class="stat-value">{video_status}</div>
                </div>
            </div>

            <div class="buttons">
                {main_cta}
            </div>

            <div class="soft">
                {safe_text(soft_text)}
            </div>
        </div>
    </body>
    </html>
    """


# =========================
# SUBIR VIDEO
# =========================

@app.post("/upload-video")
async def upload_video(
    order_id: str = Form(...),
    video: UploadFile = File(...),
):
    order = get_order_or_404(order_id)

    if video.content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(status_code=400, detail="Formato de vídeo no permitido")

    filepath = reaction_video_path(order_id)
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

        order["reaction_video"] = filepath
        order["reaction_uploaded"] = True

        public_video_url = None
        try:
            public_video_url = upload_video_to_r2(filepath, f"{order_id}.webm")
        except Exception as e:
            print(f"Error subiendo a R2: {e}")

        order["reaction_public_url"] = public_video_url

        return JSONResponse(
            {
                "status": "ok",
                "file": filepath,
                "reaction_url": f"{PUBLIC_BASE_URL}/reaccion/{order_id}",
                "cashout_url": f"{PUBLIC_BASE_URL}/cobrar/{order_id}",
                "public_video_url": public_video_url,
            }
        )
    finally:
        await video.close()


# =========================
# VIDEO FILE
# =========================

@app.get("/video/{order_id}")
def get_video(order_id: str):
    order = get_order_or_404(order_id)

    filepath = order.get("reaction_video")
    if not filepath or not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Vídeo no encontrado")

    return FileResponse(filepath, media_type="video/webm", filename=f"{order_id}.webm")


# =========================
# REACCION FINAL
# =========================

@app.get("/reaccion/{order_id}", response_class=HTMLResponse)
def reaccion(order_id: str):
    order = get_order_or_404(order_id)

    if not reaction_exists(order):
        return HTMLResponse("""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta http-equiv="refresh" content="5">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Reacción pendiente</title>
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
                <h1>La reacción aún no ha llegado</h1>
                <p>Esta página se actualizará sola en unos segundos.</p>
            </div>
        </body>
        </html>
        """)

    if not order.get("cashout_completed"):
        return RedirectResponse(url=f"/cobrar/{order_id}", status_code=303)

    share_url = f"{PUBLIC_BASE_URL}/reaccion/{order_id}"
    whatsapp_share = f"https://wa.me/?text={urllib.parse.quote('No sé cómo explicarlo... pero este momento ya forma parte de ETERNA ❤️ ' + share_url)}"

    video_source = order.get("reaction_public_url") or f"/video/{order_id}"

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Reacción ETERNA</title>
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
            }}
            .card {{
                width: 100%;
                max-width: 820px;
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 24px;
                padding: 28px;
                text-align: center;
            }}
            h1 {{
                margin: 0 0 10px 0;
                font-size: 34px;
            }}
            p {{
                color: rgba(255,255,255,0.72);
                line-height: 1.6;
                margin-bottom: 18px;
            }}
            video {{
                width: 100%;
                max-height: 72vh;
                border-radius: 20px;
                background: #111;
                display: block;
            }}
            .actions {{
                margin-top: 18px;
                display: grid;
                gap: 12px;
            }}
            button, a.btn {{
                width: 100%;
                padding: 16px 22px;
                border-radius: 999px;
                border: 0;
                background: white;
                color: black;
                font-weight: bold;
                font-size: 15px;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
            }}
            .btn-dark {{
                background: rgba(255,255,255,0.10);
                color: white;
                border: 1px solid rgba(255,255,255,0.10);
            }}
            .soft {{
                margin-top: 16px;
                color: rgba(255,255,255,0.42);
                font-size: 13px;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Tu momento ya forma parte de ETERNA ❤️</h1>
            <p>Ahora puedes volver a verlo, guardarlo o compartirlo.</p>

            <video id="reactionVideo" controls autoplay playsinline>
                <source src="{video_source}" type="video/webm">
                Tu navegador no puede reproducir este vídeo.
            </video>

            <div class="actions">
                <button onclick="replayVideo()">Volver a verlo ❤️</button>
                <a class="btn btn-dark" href="{video_source}" target="_blank">Abrir vídeo</a>
                <a class="btn btn-dark" href="{whatsapp_share}" target="_blank">Compartir por WhatsApp</a>
                <button class="btn-dark" onclick="copyLink()">Copiar enlace</button>
            </div>

            <div class="soft" id="copyMsg">
                Gracias por formar parte de ETERNA.
            </div>
        </div>

        <script>
            function replayVideo() {{
                const video = document.getElementById("reactionVideo");
                if (!video) return;
                video.currentTime = 0;
                video.play().catch(() => {{}});
            }}

            async function copyLink() {{
                try {{
                    await navigator.clipboard.writeText("{share_url}");
                    document.getElementById("copyMsg").textContent = "Enlace copiado.";
                }} catch (e) {{
                    document.getElementById("copyMsg").textContent = "No se pudo copiar el enlace.";
                }}
            }}

            window.addEventListener("load", () => {{
                const video = document.getElementById("reactionVideo");
                if (!video) return;
                video.play().catch(() => {{}});
            }});
        </script>
    </body>
    </html>
    """


# =========================
# COBRAR
# =========================

@app.get("/cobrar/{order_id}", response_class=HTMLResponse)
def cobrar(order_id: str):
    order = get_order_or_404(order_id)

    if not reaction_exists(order):
        return RedirectResponse(url=f"/pedido/{order_id}", status_code=303)

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Cobrar regalo</title>
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
            h1 {{
                margin-top: 0;
                font-size: 40px;
                line-height: 1.2;
            }}
            p {{
                color: rgba(255,255,255,0.72);
                line-height: 1.7;
                font-size: 17px;
            }}
            .money-box {{
                margin-top: 22px;
                padding: 20px;
                border-radius: 18px;
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.06);
            }}
            .money-label {{
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 1.2px;
                color: rgba(255,255,255,0.50);
                margin-bottom: 6px;
            }}
            .money-value {{
                font-size: 36px;
                font-weight: bold;
            }}
            .btn {{
                display: inline-block;
                width: 100%;
                margin-top: 24px;
                padding: 16px 22px;
                border-radius: 999px;
                border: 0;
                background: white;
                color: black;
                font-weight: bold;
                font-size: 15px;
                cursor: pointer;
                text-decoration: none;
            }}
            .soft {{
                margin-top: 18px;
                color: rgba(255,255,255,0.46);
                font-size: 14px;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Cobra tu dinero 💸</h1>
            <p>
                Tu momento ya ha quedado guardado.<br>
                Ahora puedes completar el proceso para cobrar tu regalo.
            </p>
            <div class="money-box">
                <div class="money-label">Importe recibido</div>
                <div class="money-value">{money(order["gift_amount"])}€</div>
            </div>
            <a class="btn" href="/iniciar-cobro/{order_id}">Cobrar ahora</a>
            <div class="soft">
                Cuando termines, podrás volver a verlo, guardarlo o compartirlo.
            </div>
        </div>
    </body>
    </html>
    """


@app.get("/iniciar-cobro/{order_id}")
def iniciar_cobro(order_id: str):
    get_order_or_404(order_id)
    return RedirectResponse(url=f"/cobro-completado/{order_id}", status_code=303)


@app.get("/cobro-completado/{order_id}")
def cobro_completado(order_id: str):
    order = get_order_or_404(order_id)
    order["cashout_completed"] = True
    return RedirectResponse(url=f"/reaccion/{order_id}", status_code=303)


# =========================
# EXPERIENCIA
# =========================

@app.get("/pedido/{order_id}", response_class=HTMLResponse)
def pedido(order_id: str):
    order = get_order_or_404(order_id)

    if not order.get("paid"):
        return HTMLResponse("""
        <!DOCTYPE html>
        <html lang="es">
        <body style="background:#000;color:white;text-align:center;padding-top:100px;font-family:Arial;">
            <h1>Esta ETERNA aún no está disponible</h1>
            <p>El pago todavía no se ha completado.</p>
        </body>
        </html>
        """)

    recipient_name = safe_text(order["recipient_name"])
    phrase_1 = safe_text(order["phrase_1"])
    phrase_2 = safe_text(order["phrase_2"])
    phrase_3 = safe_text(order["phrase_3"])
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
            .lead {{
                color: rgba(255,255,255,0.86);
                font-size: 18px;
                line-height: 1.7;
                margin-bottom: 18px;
            }}
            .ritual-box {{
                margin-top: 12px;
                padding: 18px;
                border-radius: 20px;
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.08);
            }}
            .ritual-text {{
                color: rgba(255,255,255,0.68);
                font-size: 15px;
                line-height: 1.8;
            }}
            .consent-row {{
                margin-top: 22px;
                display: flex;
                align-items: flex-start;
                gap: 10px;
                text-align: left;
                color: rgba(255,255,255,0.82);
                font-size: 14px;
                line-height: 1.6;
                cursor: pointer;
                user-select: none;
            }}
            .consent-row input {{
                width: 22px;
                height: 22px;
                margin-top: 2px;
                accent-color: white;
                flex: 0 0 auto;
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
            }}
            #startBtn:disabled {{
                opacity: 0.45;
                cursor: not-allowed;
            }}
            #experience {{
                background: #000;
            }}
            #content {{
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
            .loader {{
                margin-top: 18px;
                color: rgba(255,255,255,0.55);
                font-size: 14px;
            }}
            @media (max-width: 640px) {{
                .gate-card h1 {{
                    font-size: 32px;
                }}
                .lead {{
                    font-size: 16px;
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

                <p class="lead">
                    Antes de empezar, busca un momento tranquilo solo para ti.
                </p>

                <div class="ritual-box">
                    <div class="ritual-text">
                        Tu experiencia será vivida y compartida con la persona que te hizo este regalo.
                        <br><br>
                        Al continuar, aceptas vivirla en un entorno adecuado y que este momento forme parte de ETERNA.
                    </div>
                </div>

                <label class="consent-row" for="consentCheck">
                    <input type="checkbox" id="consentCheck">
                    <span>He entendido y quiero continuar</span>
                </label>

                <button id="startBtn" type="button" onclick="startExperience()" disabled>
                    Vivir mi ETERNA ❤️
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

            const scenes = [
                {{
                    html: "<h2>Para {recipient_name}</h2>",
                    duration: 2200
                }},
                {{
                    html: "<h2>{phrase_1}</h2>",
                    duration: 2600
                }},
                {{
                    html: "<h2>{phrase_2}</h2>",
                    duration: 2600
                }},
                {{
                    html: "<h2>{phrase_3}</h2>",
                    duration: 2600
                }},
                {{
                    html: "<h2>...</h2>",
                    duration: 1400
                }},
                {{
                    html: "<h2>💸 Te llega un regalo de {gift_amount}€</h2><p>En unos segundos podrás cobrarlo.</p>",
                    duration: 5000
                }}
            ];

            function wait(ms) {{
                return new Promise(resolve => setTimeout(resolve, ms));
            }}

            document.addEventListener("DOMContentLoaded", () => {{
                const consentCheck = document.getElementById("consentCheck");
                const startBtn = document.getElementById("startBtn");

                if (consentCheck && startBtn) {{
                    consentCheck.addEventListener("change", () => {{
                        startBtn.disabled = !consentCheck.checked;
                    }});
                }}
            }});

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
                        console.log("No hay chunks para subir");
                        return null;
                    }}

                    const blob = new Blob(chunks, {{ type: mediaMimeType }});

                    if (!blob || blob.size === 0) {{
                        console.log("Blob vacío");
                        return null;
                    }}

                    const formData = new FormData();
                    formData.append("order_id", "{order_id}");
                    formData.append("video", blob, "{order_id}.webm");

                    const response = await fetch("/upload-video", {{
                        method: "POST",
                        body: formData
                    }});

                    if (!response.ok) {{
                        console.log("Upload no OK:", response.status);
                        return null;
                    }}

                    return await response.json();
                }} catch (err) {{
                    console.log("Error subiendo vídeo:", err);
                    return null;
                }}
            }}

            async function stopRecordingAndUpload() {{
                if (recorder && recorder.state !== "inactive") {{
                    await new Promise((resolve) => {{
                        const oldOnStop = recorder.onstop;

                        recorder.onstop = (event) => {{
                            if (oldOnStop) {{
                                try {{
                                    oldOnStop(event);
                                }} catch (e) {{
                                    console.log(e);
                                }}
                            }}
                            resolve();
                        }};

                        try {{
                            recorder.stop();
                        }} catch (e) {{
                            console.log("Error stopping recorder:", e);
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

            async function startExperience() {{
                try {{
                    const stream = await navigator.mediaDevices.getUserMedia({{
                        video: true,
                        audio: true
                    }});

                    currentStream = stream;
                    chunks = [];

                    document.getElementById("start").classList.add("hidden");
                    document.getElementById("experience").classList.remove("hidden");

                    try {{
                        let options = {{}};

                        if (window.MediaRecorder && MediaRecorder.isTypeSupported("video/webm;codecs=vp9,opus")) {{
                            options.mimeType = "video/webm;codecs=vp9,opus";
                            mediaMimeType = "video/webm";
                        }} else if (window.MediaRecorder && MediaRecorder.isTypeSupported("video/webm;codecs=vp8,opus")) {{
                            options.mimeType = "video/webm;codecs=vp8,opus";
                            mediaMimeType = "video/webm";
                        }} else {{
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
                        console.log("No se pudo iniciar la grabación:", err);
                        recorder = null;
                    }}

                    await runExperience();
                }} catch (e) {{
                    console.log(e);
                    alert("Necesitamos acceso a cámara y micrófono para continuar con la experiencia.");
                }}
            }}

            async function runExperience() {{
                await runCountdown();
                await wait(250);

                for (const scene of scenes) {{
                    await showScene(scene.html, scene.duration);
                }}

                const content = document.getElementById("content");
                content.classList.remove("visible");
                await wait(120);
                content.innerHTML = "<h2>Preparando tu cobro...</h2><p>Guardando este momento.</p><div class='loader'>Subiendo reacción...</div>";
                await wait(30);
                content.classList.add("visible");

                const uploadResult = await stopRecordingAndUpload();

                if (uploadResult && uploadResult.cashout_url) {{
                    window.location.href = uploadResult.cashout_url;
                    return;
                }}

                window.location.href = "/cobrar/{order_id}";
            }}
        </script>
    </body>
    </html>
    """


# =========================
# STATUS SIMPLE
# =========================

@app.get("/health")
def health():
    return {{
        "status": "ok",
        "app": "ETERNA V11 R2 FULL",
        "stripe_configured": bool(STRIPE_SECRET_KEY),
        "r2_configured": r2_enabled(),
        "public_base_url": PUBLIC_BASE_URL,
        "orders": len(orders),
    }