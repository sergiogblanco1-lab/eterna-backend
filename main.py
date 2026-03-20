import json
import os
import uuid
from pathlib import Path

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

# Precio en céntimos. Ej: 4900 = 49,00 €
ETERNA_PRICE_CENTS = int(os.getenv("ETERNA_PRICE_CENTS", "4900"))
ETERNA_CURRENCY = os.getenv("ETERNA_CURRENCY", "eur")

stripe.api_key = STRIPE_SECRET_KEY

app = FastAPI(title="ETERNA")

# =========================
# CARPETAS
# =========================

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
REACTIONS_DIR = BASE_DIR / "reacciones"
DATA_DIR = BASE_DIR / "data"
ORDERS_FILE = DATA_DIR / "orders.json"

STATIC_DIR.mkdir(exist_ok=True)
REACTIONS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

if not ORDERS_FILE.exists():
    ORDERS_FILE.write_text("{}", encoding="utf-8")

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# =========================
# UTILIDADES PEDIDOS
# =========================

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


def create_order(customer_name: str) -> str:
    orders = load_orders()
    order_id = str(uuid.uuid4())[:12]
    orders[order_id] = {
        "order_id": order_id,
        "customer_name": customer_name,
        "paid": False,
        "stripe_session_id": None,
        "reaction_filename": None,
    }
    save_orders(orders)
    return order_id


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
                    radial-gradient(circle at top, rgba(255,255,255,0.06), transparent 30%),
                    linear-gradient(180deg, #0b0b0b 0%, #000000 100%);
                color: white;
                font-family: Arial, sans-serif;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 24px;
            }

            .box {
                width: 100%;
                max-width: 460px;
                text-align: center;
                padding: 30px 24px;
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 24px;
                backdrop-filter: blur(6px);
            }

            h1 {
                margin: 0 0 14px;
                font-size: 42px;
                font-weight: 500;
                letter-spacing: 0.5px;
            }

            p {
                margin: 0 0 22px;
                color: rgba(255,255,255,0.82);
                line-height: 1.5;
            }

            input {
                width: 100%;
                padding: 14px 16px;
                margin-top: 12px;
                border-radius: 14px;
                border: 1px solid rgba(255,255,255,0.12);
                background: rgba(255,255,255,0.07);
                color: white;
                font-size: 16px;
                outline: none;
            }

            input::placeholder {
                color: rgba(255,255,255,0.45);
            }

            button {
                width: 100%;
                padding: 15px 16px;
                margin-top: 18px;
                border-radius: 999px;
                border: none;
                background: white;
                color: black;
                font-size: 16px;
                font-weight: bold;
                cursor: pointer;
            }

            .mini {
                margin-top: 16px;
                font-size: 13px;
                color: rgba(255,255,255,0.55);
            }
        </style>
    </head>
    <body>
        <div class="box">
            <h1>ETERNA</h1>
            <p>
                No es un vídeo. No es un mensaje.
                <br>
                Es un instante creado para alguien.
            </p>

            <form action="/crear-eterna" method="post">
                <input type="text" name="customer_name" placeholder="Tu nombre" required>
                <button type="submit">CREAR MI ETERNA</button>
            </form>

            <div class="mini">
                Primero pago. Después experiencia.
            </div>
        </div>
    </body>
    </html>
    """


# =========================
# CREAR ETERNA -> STRIPE
# =========================

@app.post("/crear-eterna")
async def crear_eterna(customer_name: str = Form(...)):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=500,
            detail="Falta STRIPE_SECRET_KEY en variables de entorno."
        )

    order_id = create_order(customer_name=customer_name)

    session = stripe.checkout.Session.create(
        mode="payment",
        client_reference_id=order_id,
        metadata={
            "order_id": order_id,
            "customer_name": customer_name,
        },
        line_items=[
            {
                "price_data": {
                    "currency": ETERNA_CURRENCY,
                    "product_data": {
                        "name": "ETERNA",
                        "description": "Experiencia emocional ETERNA",
                    },
                    "unit_amount": ETERNA_PRICE_CENTS,
                },
                "quantity": 1,
            }
        ],
        success_url=f"{PUBLIC_BASE_URL}/post-pago?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{PUBLIC_BASE_URL}/cancelado?order_id={order_id}",
    )

    update_order(order_id, stripe_session_id=session.id)

    return RedirectResponse(url=session.url, status_code=303)


# =========================
# POST PAGO
# =========================

@app.get("/post-pago", response_class=HTMLResponse)
def post_pago(session_id: str):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Falta STRIPE_SECRET_KEY.")

    session = stripe.checkout.Session.retrieve(session_id)
    order_id = session.client_reference_id

    if not order_id:
        raise HTTPException(status_code=400, detail="No se encontró el pedido.")

    order = get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")

    if order.get("paid"):
        return RedirectResponse(url=f"/pedido/{order_id}", status_code=303)

    return HTMLResponse(
        """
        <html>
        <body style="margin:0;background:black;color:white;font-family:Arial,sans-serif;display:flex;min-height:100vh;align-items:center;justify-content:center;text-align:center;padding:24px;">
            <div>
                <h1>Estamos confirmando tu pago…</h1>
                <p>Recarga en unos segundos si aún no entra.</p>
            </div>
        </body>
        </html>
        """
    )


@app.get("/cancelado", response_class=HTMLResponse)
def cancelado(order_id: str | None = None):
    txt = f"Pedido {order_id} cancelado." if order_id else "Pago cancelado."
    return HTMLResponse(
        f"""
        <html>
        <body style="margin:0;background:black;color:white;font-family:Arial,sans-serif;display:flex;min-height:100vh;align-items:center;justify-content:center;text-align:center;padding:24px;">
            <div>
                <h1>Pago cancelado</h1>
                <p>{txt}</p>
                <a href="/" style="display:inline-block;margin-top:24px;padding:14px 22px;border-radius:999px;background:white;color:black;text-decoration:none;font-weight:bold;">Volver</a>
            </div>
        </body>
        </html>
        """
    )


# =========================
# WEBHOOK STRIPE
# =========================

@app.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Falta STRIPE_WEBHOOK_SECRET en variables de entorno."
        )

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
                stripe_session_id=session.get("id"),
            )

    return {"ok": True}


# =========================
# EXPERIENCIA ETERNA
# =========================

@app.get("/pedido/{order_id}", response_class=HTMLResponse)
def ver_eterna(order_id: str):
    order = get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")

    if not order.get("paid"):
        return HTMLResponse(
            """
            <html>
            <body style="margin:0;background:black;color:white;font-family:Arial,sans-serif;display:flex;min-height:100vh;align-items:center;justify-content:center;text-align:center;padding:24px;">
                <div>
                    <h1>Esta ETERNA aún no está activada</h1>
                    <p>El pago todavía no figura como confirmado.</p>
                </div>
            </body>
            </html>
            """,
            status_code=403,
        )

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

            #experiencia.activa {{ display: flex; }}

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
                from {{ opacity: 0; transform: translateY(8px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
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

        <section id="experiencia">
            <div class="regalo">
                <h2>Hay algo para ti</h2>
                <p>Vívelo por completo.</p>
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

            function activarSiExiste(imgId) {{
                const img = document.getElementById(imgId);
                img.addEventListener("load", () => img.classList.add("visible"));
                img.addEventListener("error", () => img.style.display = "none");
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
                        if (e.data && e.data.size > 0) chunks.push(e.data);
                    }};

                    mediaRecorder.onstop = async () => {{
                        videoBlob = new Blob(chunks, {{ type: "video/webm" }});
                        await subirVideo();
                        cerrarCamara();
                        mostrarPantalla("final");
                    }};

                    mediaRecorder.start();
                    mostrarPantalla("experiencia");

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
    order_id: str = Form(None)
):
    order = get_order(order_id) if order_id else None
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")

    filename = video.filename or f"reaccion_{order_id}.webm"
    file_path = REACTIONS_DIR / filename

    with open(file_path, "wb") as f:
        f.write(await video.read())

    update_order(order_id, reaction_filename=filename)

    return {
        "ok": True,
        "order_id": order_id,
        "filename": filename
    }
