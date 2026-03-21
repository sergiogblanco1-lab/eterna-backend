import html
import os
import urllib.parse
import uuid

import stripe
from fastapi import FastAPI, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

app = FastAPI(title="ETERNA V4")

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
            * { box-sizing: border-box; }

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

    phone = normalize_phone(order["recipient_phone"])
    whatsapp_url = f"https://wa.me/{phone}?text={mensaje}"

    video_status = "No guardado todavía"
    if order.get("reaction_video"):
        video_status = "Vídeo guardado"

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
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
                max-width: 700px;
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 24px;
                padding: 34px 28px;
                text-align: center;
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
            <p>Ya puedes enviarla a {safe_text(order["recipient_name"])} por WhatsApp.</p>

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

                <a href="/">
                    <button class="light">Crear otra ETERNA ❤️</button>
                </a>
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

    return JSONResponse({"status": "ok", "file": filepath})

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
            body {{
                margin: 0;
                background: black;
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
            }}

            .hidden {{
                display: none;
            }}

            .gate-card {{
                max-width: 560px;
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
            }}

            .video-preview video {{
                width: 100%;
                height: 100%;
                object-fit: cover;
                transform: scaleX(-1);
            }}

            #content {{
                max-width: 800px;
                padding: 24px;
            }}

            #content h2 {{
                font-size: 40px;
                line-height: 1.3;
                margin: 0;
            }}

            .small {{
                font-size: 13px;
                color: rgba(255,255,255,0.45);
                margin-top: 10px;
            }}
        </style>
    </head>
    <body>

        <div id="start" class="screen">
            <div class="gate-card">
                <h1>Hay algo para ti</h1>
                <p>Para vivir esta experiencia completa, necesitamos encender tu cámara.</p>
                <p>Al continuar, aceptas que este momento forme parte de la experiencia.</p>
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

        <script>
            let recorder = null;
            let chunks = [];
            let currentStream = null;

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
                        recorder = new MediaRecorder(stream);

                        recorder.ondataavailable = (e) => {{
                            if (e.data && e.data.size > 0) {{
                                chunks.push(e.data);
                            }}
                        }};

                        recorder.onstop = async () => {{
                            try {{
                                console.log("VIDEO STOP -> enviando...");
                                console.log("Chunks:", chunks.length);

                                const blob = new Blob(chunks, {{ type: "video/webm" }});
                                const formData = new FormData();
                                formData.append("order_id", "{order_id}");
                                formData.append("video", blob, "{order_id}.webm");

                                const response = await fetch("{PUBLIC_BASE_URL}/upload-video", {{
                                    method: "POST",
                                    body: formData
                                }});

                                console.log("Upload status:", response.status);
                            }} catch (err) {{
                                console.log("Error subiendo vídeo:", err);
                            }}

                            if (currentStream) {{
                                currentStream.getTracks().forEach(track => track.stop());
                            }}
                        }};

                        recorder.start();
                    }} catch (err) {{
                        console.log("No se pudo iniciar la grabación:", err);
                    }}

                    runExperience();
                }} catch (e) {{
                    alert("Necesitamos acceso a la cámara para continuar con la experiencia.");
                }}
            }}

            function show(text) {{
                document.getElementById("content").innerHTML = "<h2>" + text + "</h2>";
            }}

            async function wait(ms) {{
                return new Promise(resolve => setTimeout(resolve, ms));
            }}

            async function runExperience() {{
                document.getElementById("experience").classList.remove("hidden");

                await wait(1200);
                show("Para {recipient_name}");
                await wait(1800);

                show("{phrase_1}");
                await wait(2400);

                show("{phrase_2}");
                await wait(2400);

                show("{phrase_3}");
                await wait(2400);

                show("...");
                await wait(1400);

                show("💸 Has recibido {gift_amount}€");
                await wait(3000);

                if (recorder) {{
                    try {{
                        recorder.stop();
                    }} catch (e) {{
                        console.log("Error stopping recorder:", e);
                    }}
                }}
            }}
        </script>
    </body>
    </html>
    """