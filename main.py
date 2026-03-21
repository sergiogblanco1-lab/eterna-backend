<<<<<<< HEAD
from pathlib import Path
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
=======
import os
import uuid
import urllib.parse

import stripe
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
>>>>>>> b5a204b81288caa1efd9beada1ed7b9889f98fd5

app = FastAPI(title="ETERNA")

# =========================
<<<<<<< HEAD
# CARPETAS
# =========================

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
REACTIONS_DIR = BASE_DIR / "reacciones"

STATIC_DIR.mkdir(exist_ok=True)
REACTIONS_DIR.mkdir(exist_ok=True)

# Montar archivos estáticos
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# =========================
# HOME SIMPLE
=======
# CONFIG
# =========================

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000").strip()

BASE_PRICE = float(os.getenv("ETERNA_BASE_PRICE", "29"))
CURRENCY = os.getenv("ETERNA_CURRENCY", "eur").strip().lower()
COMMISSION_RATE = float(os.getenv("GIFT_COMMISSION_RATE", "0.05"))

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# memoria temporal
orders: dict[str, dict] = {}

# =========================
# HOME
>>>>>>> b5a204b81288caa1efd9beada1ed7b9889f98fd5
# =========================

@app.get("/", response_class=HTMLResponse)
def home():
    return """
<<<<<<< HEAD
    <html>
=======
    <!DOCTYPE html>
    <html lang="es">
>>>>>>> b5a204b81288caa1efd9beada1ed7b9889f98fd5
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ETERNA</title>
        <style>
<<<<<<< HEAD
            body{
                margin:0;
                min-height:100vh;
                display:flex;
                align-items:center;
                justify-content:center;
                background:#000;
                color:#fff;
                font-family:Arial, sans-serif;
                text-align:center;
                padding:20px;
            }
            a{
                color:#fff;
                text-decoration:none;
                border:1px solid rgba(255,255,255,0.25);
                padding:14px 22px;
                border-radius:999px;
                display:inline-block;
                margin-top:20px;
=======
            body {
                background: #000;
                color: #fff;
                font-family: Arial, sans-serif;
                padding: 40px;
                text-align: center;
            }
            input {
                width: min(420px, 90vw);
                padding: 12px;
                margin: 8px 0;
                border-radius: 10px;
                border: 1px solid #333;
                background: #111;
                color: white;
            }
            button {
                padding: 14px 22px;
                border-radius: 999px;
                border: 0;
                background: white;
                color: black;
                font-weight: bold;
                cursor: pointer;
                margin-top: 12px;
>>>>>>> b5a204b81288caa1efd9beada1ed7b9889f98fd5
            }
        </style>
    </head>
    <body>
<<<<<<< HEAD
        <div>
            <h1>ETERNA</h1>
            <p>Prueba la experiencia aquí:</p>
            <a href="/pedido/test123">Abrir ETERNA de prueba</a>
        </div>
=======
        <h1>ETERNA</h1>

        <form action="/crear-eterna" method="post">
            <input name="customer_name" placeholder="Tu nombre" required><br>
            <input name="customer_email" placeholder="Tu email" required><br>
            <input name="customer_phone" placeholder="Tu teléfono" required><br>

            <input name="recipient_name" placeholder="Nombre receptor" required><br>
            <input name="recipient_phone" placeholder="Teléfono receptor" required><br>

            <input name="phrase_1" placeholder="Frase 1" required><br>
            <input name="phrase_2" placeholder="Frase 2" required><br>
            <input name="phrase_3" placeholder="Frase 3" required><br>

            <input name="gift_amount" placeholder="Dinero a regalar (€)" type="number" step="0.01" min="0" value="0"><br>

            <button type="submit">CREAR MI ETERNA</button>
        </form>
>>>>>>> b5a204b81288caa1efd9beada1ed7b9889f98fd5
    </body>
    </html>
    """

<<<<<<< HEAD

# =========================
# EXPERIENCIA ETERNA
=======
# =========================
# CREAR ETERNA
# =========================

from fastapi import Form, UploadFile, File
from typing import List, Optional

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

    gift_amount: int = Form(...),

    # 🔥 FIX ANÓNIMO
    anonimo: Optional[str] = Form(None),

    photos: List[UploadFile] = File(...)
):
    # 🔥 AQUÍ VA LA LÓGICA
    is_anonimo = anonimo is not None

    print("Anonimo:", is_anonimo)
    print("Regalo:", gift_amount)

    # 👉 EJEMPLO (tu lógica sigue igual debajo)
    # Aquí sigue TODO tu código actual:
    # - guardar datos
    # - crear order_id
    # - stripe checkout
    # - redirect

    return {
        "status": "ok",
        "anonimo": is_anonimo,
        "gift_amount": gift_amount
    }

# =========================
# WEBHOOK
# =========================

@app.post("/webhook")
async def webhook(request: Request):
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Falta STRIPE_WEBHOOK_SECRET.")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=STRIPE_WEBHOOK_SECRET,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Payload inválido")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Firma inválida")

    print("DEBUG webhook event:", event["type"])

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        order_id = session.get("client_reference_id") or session.get("metadata", {}).get("order_id")

        print("DEBUG webhook order_id:", order_id)

        if order_id and order_id in orders:
            orders[order_id]["paid"] = True
            orders[order_id]["stripe_session_id"] = session.get("id")

    return {"ok": True}

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
        f"👉 {PUBLIC_BASE_URL}/pedido/{order_id}"
    )

    telefono = "".join(ch for ch in order["recipient_phone"] if ch.isdigit())
    whatsapp_url = f"https://wa.me/{telefono}?text={mensaje}"

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Resumen ETERNA</title>
        <style>
            body {{
                background: black;
                color: white;
                font-family: Arial, sans-serif;
                padding: 40px;
            }}
            button {{
                padding: 14px 22px;
                border-radius: 999px;
                border: 0;
                font-weight: bold;
                cursor: pointer;
                margin-right: 10px;
            }}
        </style>
    </head>
    <body>
        <h1>Resumen ETERNA</h1>

        <p><b>Estado:</b> {"Pagado" if order["paid"] else "Pendiente"}</p>

        <hr>

        <p><b>Regalante:</b> {order["customer_name"]}</p>
        <p><b>Receptor:</b> {order["recipient_name"]}</p>

        <p>Frase 1: {order["phrase_1"]}</p>
        <p>Frase 2: {order["phrase_2"]}</p>
        <p>Frase 3: {order["phrase_3"]}</p>

        <hr>

        <p>ETERNA: {BASE_PRICE:.2f}€</p>
        <p>Regalo: {order["gift_amount"]:.2f}€</p>
        <p>Comisión: {order["gift_commission"]:.2f}€</p>
        <p><b>Total: {order["total"]:.2f}€</b></p>

        <br>

        <a href="/pedido/{order_id}">
            <button>VER TU ETERNA</button>
        </a>

        <a href="{whatsapp_url}" target="_blank">
            <button style="background:green;color:white;">ENVIAR POR WHATSAPP</button>
        </a>
    </body>
    </html>
    """

# =========================
# EXPERIENCIA
>>>>>>> b5a204b81288caa1efd9beada1ed7b9889f98fd5
# =========================

@app.get("/pedido/{order_id}", response_class=HTMLResponse)
def ver_eterna(order_id: str):
<<<<<<< HEAD
    inicio_img = "/static/eterna_inicio.jpg"
    final_img = "/static/eterna_final.jpg"

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
            width: 100%;
            height: 100%;
            display: none;
            align-items: center;
            justify-content: center;
            text-align: center;
            overflow: hidden;
            background:
                radial-gradient(circle at top, rgba(255,255,255,0.08), transparent 35%),
                linear-gradient(180deg, #0a0a0a 0%, #000 100%);
        }}

        .pantalla.activa {{
            display: flex;
        }}

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

        .fondo.visible {{
            opacity: 1;
        }}

        .overlay {{
            position: absolute;
            inset: 0;
            background: linear-gradient(
                180deg,
                rgba(0,0,0,0.35) 0%,
                rgba(0,0,0,0.55) 45%,
                rgba(0,0,0,0.80) 100%
            );
        }}

        .contenido {{
            position: relative;
            z-index: 2;
            max-width: 760px;
            padding: 28px;
        }}

        h1 {{
            margin: 0 0 16px;
            font-size: clamp(34px, 6vw, 56px);
            font-weight: 500;
            letter-spacing: 0.5px;
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

        button:hover {{
            transform: scale(1.02);
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

        #preview.visible {{
            opacity: 0.82;
        }}

        #experiencia {{
            position: fixed;
            inset: 0;
            display: none;
            align-items: center;
            justify-content: center;
            text-align: center;
            z-index: 8;
            background:
                radial-gradient(circle at center, rgba(255,255,255,0.05), transparent 35%),
                #000;
            padding: 30px;
        }}

        #experiencia.activa {{
            display: flex;
        }}

        .regalo {{
            animation: aparecer 1.2s ease forwards;
            opacity: 0;
        }}

        .regalo h2 {{
            margin: 0 0 12px;
            font-size: clamp(28px, 7vw, 60px);
            font-weight: 500;
        }}

        .regalo p {{
            font-size: clamp(16px, 3vw, 22px);
            color: rgba(255,255,255,0.86);
        }}

        @keyframes aparecer {{
            from {{
                opacity: 0;
                transform: translateY(8px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}
    </style>
</head>
<body>

    <!-- INICIO -->
    <section id="inicio" class="pantalla activa">
        <img id="imgInicio" class="fondo" src="{inicio_img}" alt="ETERNA inicio">
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

    <!-- EXPERIENCIA -->
    <section id="experiencia">
        <div class="regalo">
            <h2>Hay algo para ti</h2>
            <p>Vívelo por completo.</p>
        </div>
    </section>

    <!-- FINAL -->
    <section id="final" class="pantalla">
        <img id="imgFinal" class="fondo" src="{final_img}" alt="ETERNA final">
        <div class="overlay"></div>

        <div class="contenido">
            <h1>Este momento ya es tuyo</h1>
            <p>
                Puedes guardarlo o compartirlo.
            </p>

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

        function activarSiExiste(imgId) {{
            const img = document.getElementById(imgId);
            img.addEventListener("load", () => {{
                img.classList.add("visible");
            }});
            img.addEventListener("error", () => {{
                img.style.display = "none";
            }});
        }}

        activarSiExiste("imgInicio");
        activarSiExiste("imgFinal");

        function mostrarPantalla(id) {{
            document.getElementById("inicio").classList.remove("activa");
            document.getElementById("final").classList.remove("activa");
            document.getElementById("experiencia").classList.remove("activa");

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
                    if (e.data && e.data.size > 0) {{
                        chunks.push(e.data);
                    }}
                }};

                mediaRecorder.onstop = async () => {{
                    videoBlob = new Blob(chunks, {{ type: "video/webm" }});
                    await subirVideo();
                    cerrarCamara();
                    mostrarPantalla("final");
                }};

                mediaRecorder.start();
                mostrarPantalla("experiencia");

                // 2 segundos antes del momento principal
                setTimeout(() => {{
                    mostrarMomento();
                }}, 2000);

            }} catch (error) {{
                alert("Para vivir ETERNA debes aceptar la experiencia completa.");
            }}
        }}

        function mostrarMomento() {{
            const experiencia = document.getElementById("experiencia");
            experiencia.innerHTML = `
                <div class="regalo">
                    <h2>💸 Has recibido un regalo</h2>
                    <p>Este instante es solo tuyo.</p>
                </div>
            `;

            // cortar 10 segundos después
            setTimeout(() => {{
                if (mediaRecorder && mediaRecorder.state !== "inactive") {{
                    mediaRecorder.stop();
                }}
            }}, 10000);
        }}

        async function subirVideo() {{
            if (!videoBlob) return;

            const formData = new FormData();
            formData.append("video", videoBlob, `reaccion_${{orderId}}.webm`);
            formData.append("order_id", orderId);

            try {{
                await fetch("/subir-reaccion", {{
                    method: "POST",
                    body: formData
                }});
            }} catch (error) {{
                console.error("Error subiendo reacción:", error);
            }}
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
    """


# =========================
# SUBIR REACCIÓN
# =========================

@app.post("/subir-reaccion")
async def subir_reaccion(
    video: UploadFile = File(...),
    order_id: str = File(None)
):
    filename = video.filename or "reaccion.webm"
    file_path = REACTIONS_DIR / filename

    with open(file_path, "wb") as f:
        f.write(await video.read())

    return {
        "ok": True,
        "order_id": order_id,
        "filename": filename
    }
=======
    order = orders.get(order_id)

    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ETERNA</title>
    </head>
    <body style="background:black;color:white;text-align:center;padding-top:100px;font-family:Arial;">
        <h1>Hay algo para ti</h1>
        <p>{order['phrase_1']}</p>
        <p>{order['phrase_2']}</p>
        <p>{order['phrase_3']}</p>
        <p style="margin-top:30px;">💸 Has recibido {order['gift_amount']:.2f}€</p>
    </body>
    </html>
    """
>>>>>>> b5a204b81288caa1efd9beada1ed7b9889f98fd5
