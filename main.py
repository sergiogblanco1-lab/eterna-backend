import html
import os
import urllib.parse
import uuid

import stripe
from fastapi import FastAPI, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse

app = FastAPI(title="ETERNA V6")

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

orders: dict[str, dict] = {}

VIDEO_FOLDER = "videos"
os.makedirs(VIDEO_FOLDER, exist_ok=True)

# =========================
# HELPERS
# =========================

def safe_text(v: str) -> str:
    return html.escape(str(v or "").strip())


def money(v: float) -> str:
    return f"{float(v):.2f}"


def normalize_phone(p: str) -> str:
    return "".join(ch for ch in str(p or "") if ch.isdigit())


def reaction_video_url(order_id: str) -> str:
    return f"/video/{order_id}"


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
                Hoy usamos 3 frases como experiencia MVP.<br>
                Mañana será un vídeo emocional real.
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
                    Precio base: {money(BASE_PRICE)}€ · Si añades dinero, se suma una pequeña comisión automática.
                </div>

                <button type="submit">CREAR MI ETERNA</button>
            </form>

            <div class="footer-note">
                MVP actual: frases + reacción grabada.<br>
                Futuro: vídeo emocional real + estética más bucólica, romántica y preciosa.
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
        "reaction_video": None,
        "reaction_uploaded": False,
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
# RESUMEN REGALANTE
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

    phone = normalize_phone(order["recipient_phone"])
    whatsapp_url = f"https://wa.me/{phone}?text={mensaje}"

    reaction_block = ""
    if order.get("reaction_video") and os.path.exists(order["reaction_video"]):
        reaction_block = f"""
            <a href="/reaccion/{order_id}" target="_blank">
                <button class="light">Ver reacción grabada ❤️</button>
            </a>
        """
        video_status = "Vídeo guardado"
    else:
        video_status = "Pendiente de recibir"

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
                max-width: 720px;
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 24px;
                padding: 34px 28px;
                text-align: center;
            }}

            h1 {{
                margin-top: 0;
            }}

            p {{
                color: rgba(255,255,255,0.76);
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
            <p>
                Ya puedes enviarla a {safe_text(order["recipient_name"])} por WhatsApp.
                <br>
                Cuando vea la experiencia, aquí aparecerá su reacción grabada.
            </p>

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
                <a href="{whatsapp_url}" target="_blank">
                    <button class="whatsapp">Enviar por WhatsApp</button>
                </a>

                <a href="/pedido/{order_id}" target="_blank">
                    <button class="light">Ver experiencia ETERNA</button>
                </a>

                {reaction_block}

                <a href="/">
                    <button class="light">Crear otra ETERNA ❤️</button>
                </a>
            </div>

            <div class="soft">
                Esta página se actualiza sola cada pocos segundos para detectar la reacción.
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
    video: UploadFile = File(...)
):
    order = orders.get(order_id)

    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    filename = f"{order_id}.webm"
    filepath = os.path.join(VIDEO_FOLDER, filename)

    with open(filepath, "wb") as f:
        f.write(await video.read())

    order["reaction_video"] = filepath
    order["reaction_uploaded"] = True

    return JSONResponse({
        "status": "ok",
        "file": filepath,
        "reaction_url": f"{PUBLIC_BASE_URL}/reaccion/{order_id}"
    })


# =========================
# VIDEO FILE
# =========================

@app.get("/video/{order_id}")
def get_video(order_id: str):
    order = orders.get(order_id)

    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    filepath = order.get("reaction_video")
    if not filepath or not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Vídeo no encontrado")

    return FileResponse(filepath, media_type="video/webm", filename=f"{order_id}.webm")


# =========================
# REACCION
# =========================

@app.get("/reaccion/{order_id}", response_class=HTMLResponse)
def reaccion(order_id: str):
    order = orders.get(order_id)

    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    filepath = order.get("reaction_video")
    if not filepath or not os.path.exists(filepath):
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
                    background: black;
                    color: white;
                    font-family: Arial, sans-serif;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    padding: 24px;
                    text-align: center;
                }
                .card {
                    max-width: 680px;
                }
                p {
                    color: rgba(255,255,255,0.72);
                    line-height: 1.6;
                }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>La reacción aún no ha llegado</h1>
                <p>Esta página se actualizará sola en unos segundos.</p>
            </div>
        </body>
        </html>
        """)

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Reacción ETERNA</title>
        <style>
            body {{
                margin: 0;
                min-height: 100vh;
                background:
                    radial-gradient(circle at top, rgba(255,255,255,0.08), transparent 30%),
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
                max-width: 780px;
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 24px;
                padding: 28px;
                text-align: center;
            }}

            h1 {{
                margin-top: 0;
            }}

            p {{
                color: rgba(255,255,255,0.72);
                line-height: 1.6;
            }}

            video {{
                width: 100%;
                max-height: 70vh;
                border-radius: 20px;
                background: #111;
                margin-top: 18px;
            }}

            .actions {{
                margin-top: 18px;
                display: flex;
                flex-direction: column;
                gap: 12px;
            }}

            a {{
                text-decoration: none;
            }}

            button {{
                width: 100%;
                padding: 16px 22px;
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
        <div class="card">
            <h1>La reacción ya está aquí ❤️</h1>
            <p>
                Esto es lo más importante de ETERNA:
                el momento real de quien recibe el regalo.
            </p>

            <video controls autoplay playsinline>
                <source src="{reaction_video_url(order_id)}" type="video/webm">
                Tu navegador no puede reproducir este vídeo.
            </video>

            <div class="actions">
                <a href="/resumen/{order_id}">
                    <button>Volver al resumen</button>
                </a>
                <a href="/">
                    <button>Crear otra ETERNA ❤️</button>
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
def pedido(order_id: str):
    order = orders.get(order_id)

    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    if not order.get("paid"):
        return HTMLResponse("""
        <!DOCTYPE html>
        <html lang="es">
        <body style="background:black;color:white;text-align:center;padding-top:100px;font-family:Arial;">
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

            body {{
                margin: 0;
                background:
                    radial-gradient(circle at top, rgba(255,255,255,0.06), transparent 30%),
                    linear-gradient(180deg, #030303 0%, #000000 100%);
                color: white;
                overflow: hidden;
                font-family: Arial, sans-serif;
                text-align: center;
            }}

            .screen {{
                position: absolute;
                inset: 0;
                display: flex;
                justify-content: center;
                align-items: center;
                flex-direction: column;
                padding: 24px;
                transition: opacity 0.8s ease;
            }}

            .hidden {{
                display: none;
            }}

            .gate-card {{
                max-width: 580px;
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 24px;
                padding: 34px 28px;
            }}

            .gate-card h1 {{
                font-size: 40px;
                margin-bottom: 14px;
            }}

            .gate-card p {{
                color: rgba(255,255,255,0.72);
                line-height: 1.6;
                margin-bottom: 12px;
            }}

            .small {{
                font-size: 13px;
                color: rgba(255,255,255,0.45);
                margin-top: 10px;
            }}

            button {{
                padding: 16px 24px;
                border-radius: 999px;
                border: 0;
                background: white;
                color: black;
                font-weight: bold;
                cursor: pointer;
                margin-top: 20px;
                font-size: 15px;
            }}

            .video-preview {{
                position: fixed;
                bottom: 20px;
                right: 20px;
                width: 120px;
                height: 160px;
                border-radius: 12px;
                overflow: hidden;
                border: 2px solid rgba(255,255,255,0.2);
                display: none;
                background: #111;
                z-index: 20;
            }}

            .video-preview video {{
                width: 100%;
                height: 100%;
                object-fit: cover;
                transform: scaleX(-1);
            }}

            #experience {{
                z-index: 5;
            }}

            #content {{
                max-width: 880px;
                padding: 24px;
            }}

            #content h2 {{
                font-size: 42px;
                line-height: 1.3;
                margin: 0;
                font-weight: 600;
            }}

            #content p {{
                color: rgba(255,255,255,0.72);
                margin-top: 14px;
                line-height: 1.6;
                font-size: 17px;
            }}

            .final-card {{
                max-width: 720px;
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 28px;
                padding: 34px 28px;
            }}

            .final-card h1 {{
                font-size: 42px;
                margin-bottom: 12px;
            }}

            .final-card p {{
                color: rgba(255,255,255,0.74);
                line-height: 1.7;
                font-size: 17px;
            }}

            .final-actions {{
                margin-top: 22px;
                display: flex;
                flex-direction: column;
                gap: 12px;
            }}

            .reaction-player {{
                width: min(92vw, 420px);
                max-height: 68vh;
                border-radius: 18px;
                background: #111;
                margin-top: 18px;
            }}
        </style>
    </head>
    <body>

        <div id="start" class="screen">
            <div class="gate-card">
                <h1>Hay algo para ti</h1>
                <p>Para vivir esta experiencia completa, necesitamos encender tu cámara.</p>
                <p>Solo grabaremos este momento como parte del regalo, con tu permiso.</p>
                <div class="small">La experiencia empieza justo después de aceptar.</div>
                <button onclick="startExperience()">Aceptar y continuar</button>
            </div>
        </div>

        <div id="cameraBox" class="video-preview">
            <video id="video" autoplay muted playsinline></video>
        </div>

        <div id="experience" class="screen hidden">
            <div id="content"></div>
        </div>

        <div id="reactionScreen" class="screen hidden"></div>

        <script>
            let recorder = null;
            let chunks = [];
            let currentStream = null;
            let uploadedReactionUrl = "";
            let mediaMimeType = "video/webm";

            function show(htmlContent) {{
                document.getElementById("content").innerHTML = htmlContent;
            }}

            function hideAllExperienceScreens() {{
                document.getElementById("experience").classList.add("hidden");
                document.getElementById("reactionScreen").classList.add("hidden");
            }}

            function wait(ms) {{
                return new Promise(resolve => setTimeout(resolve, ms));
            }}

            async function sendVideo() {{
                try {{
                    if (!chunks.length) {{
                        console.log("No hay chunks para subir");
                        return null;
                    }}

                    const blob = new Blob(chunks, {{ type: mediaMimeType }});
                    const formData = new FormData();
                    formData.append("order_id", "{order_id}");
                    formData.append("video", blob, "{order_id}.webm");

                    const response = await fetch("{PUBLIC_BASE_URL}/upload-video", {{
                        method: "POST",
                        body: formData
                    }});

                    if (!response.ok) {{
                        console.log("Upload no OK:", response.status);
                        return null;
                    }}

                    const data = await response.json();
                    uploadedReactionUrl = data.reaction_url || "";
                    return data;
                }} catch (err) {{
                    console.log("Error subiendo vídeo:", err);
                    return null;
                }}
            }}

            async function stopRecordingAndUpload() {{
                if (recorder && recorder.state !== "inactive") {{
                    await new Promise((resolve) => {{
                        recorder.onstop = () => resolve();
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
                }}

                document.getElementById("cameraBox").style.display = "none";

                await wait(700);
                await sendVideo();
            }}

            function showReactionReplay() {{
                const box = document.getElementById("reactionScreen");
                box.classList.remove("hidden");

                let reactionHtml = `
                    <div class="final-card">
                        <h1>Este momento ya es ETERNA ❤️</h1>
                        <p>
                            Lo más bonito no es solo lo que recibió.<br>
                            Es cómo lo sintió.
                        </p>
                `;

                if (uploadedReactionUrl) {{
                    reactionHtml += `
                        <video class="reaction-player" controls autoplay playsinline>
                            <source src="/video/{order_id}" type="video/webm">
                            Tu navegador no puede reproducir este vídeo.
                        </video>
                    `;
                }} else {{
                    reactionHtml += `
                        <p style="margin-top:18px;color:rgba(255,255,255,0.55);">
                            La reacción se está guardando.
                        </p>
                    `;
                }}

                reactionHtml += `
                        <div class="final-actions">
                            <a href="/" style="text-decoration:none;">
                                <button>Crear otra ETERNA ❤️</button>
                            </a>
                        </div>
                    </div>
                `;

                box.innerHTML = reactionHtml;
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

                    const video = document.getElementById("video");
                    video.srcObject = stream;
                    document.getElementById("cameraBox").style.display = "block";

                    try {{
                        let options = {{}};

                        if (MediaRecorder.isTypeSupported("video/webm;codecs=vp9,opus")) {{
                            options.mimeType = "video/webm;codecs=vp9,opus";
                            mediaMimeType = "video/webm";
                        }} else if (MediaRecorder.isTypeSupported("video/webm;codecs=vp8,opus")) {{
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

                    runExperience();
                }} catch (e) {{
                    alert("Necesitamos acceso a la cámara para continuar con la experiencia.");
                }}
            }}

            async function runExperience() {{
                document.getElementById("experience").classList.remove("hidden");

                await wait(1200);
                show("<h2>Para {recipient_name}</h2>");
                await wait(2000);

                show("<h2>{phrase_1}</h2>");
                await wait(2600);

                show("<h2>{phrase_2}</h2>");
                await wait(2600);

                show("<h2>{phrase_3}</h2>");
                await wait(2600);

                show("<h2>...</h2>");
                await wait(1500);

                show("<h2>💸 Has recibido {gift_amount}€</h2><p>Este momento también forma parte del regalo.</p>");
                await wait(4000);

                await stopRecordingAndUpload();

                hideAllExperienceScreens();
                showReactionReplay();
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
    return {
        "status": "ok",
        "app": "ETERNA V6",
        "stripe_configured": bool(STRIPE_SECRET_KEY),
        "public_base_url": PUBLIC_BASE_URL
    }