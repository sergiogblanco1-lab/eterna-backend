import html
import os
import urllib.parse
import uuid

from fastapi import FastAPI, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse

app = FastAPI(title="ETERNA V9")

# =========================
# CONFIG
# =========================

PUBLIC_BASE_URL = os.getenv(
    "PUBLIC_BASE_URL",
    "https://eterna-v2-lab.onrender.com"
).strip().rstrip("/")

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

def reaction_video_path(order_id: str) -> str:
    return os.path.join(VIDEO_FOLDER, f"{order_id}.webm")

def reaction_exists(order: dict) -> bool:
    filepath = order.get("reaction_video")
    return bool(filepath) and os.path.exists(filepath)

def whatsapp_link(phone: str, message: str) -> str:
    return f"https://wa.me/{normalize_phone(phone)}?text={urllib.parse.quote(message)}"

def get_order_or_404(order_id: str) -> dict:
    order = orders.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    return order

# =========================
# HOME
# =========================

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
    <body style="background:#000;color:white;text-align:center;padding-top:100px;font-family:Arial;">
        <h1>ETERNA</h1>
        <form action="/crear-eterna" method="post">
            <input name="customer_name" placeholder="Tu nombre" required><br><br>
            <input name="customer_phone" placeholder="Tu teléfono" required><br><br>

            <input name="recipient_name" placeholder="Nombre destinatario" required><br><br>
            <input name="recipient_phone" placeholder="Teléfono destinatario" required><br><br>

            <input name="phrase_1" placeholder="Frase 1" required><br><br>
            <input name="phrase_2" placeholder="Frase 2" required><br><br>
            <input name="phrase_3" placeholder="Frase 3" required><br><br>

            <input name="gift_amount" type="number" value="0"><br><br>

            <button type="submit">CREAR ETERNA</button>
        </form>
    </body>
    </html>
    """

# =========================
# CREAR
# =========================

@app.post("/crear-eterna")
def crear_eterna(
    customer_name: str = Form(...),
    customer_phone: str = Form(...),
    recipient_name: str = Form(...),
    recipient_phone: str = Form(...),
    phrase_1: str = Form(...),
    phrase_2: str = Form(...),
    phrase_3: str = Form(...),
    gift_amount: float = Form(0),
):
    order_id = str(uuid.uuid4())[:12]

    orders[order_id] = {
        "order_id": order_id,
        "customer_name": customer_name,
        "recipient_name": recipient_name,
        "recipient_phone": recipient_phone,
        "phrase_1": phrase_1,
        "phrase_2": phrase_2,
        "phrase_3": phrase_3,
        "gift_amount": gift_amount,
        "reaction_video": None,
        "cashout_completed": False
    }

    return RedirectResponse(url=f"/resumen/{order_id}", status_code=303)

# =========================
# RESUMEN
# =========================

@app.get("/resumen/{order_id}", response_class=HTMLResponse)
def resumen(order_id: str):
    order = get_order_or_404(order_id)

    message = (
        f"Hola ❤️\\n\\n"
        f"{order['customer_name']} te ha enviado algo especial.\\n\\n"
        f"Ábrelo aquí:\\n"
        f"{PUBLIC_BASE_URL}/pedido/{order_id}"
    )

    link = whatsapp_link(order["recipient_phone"], message)

    return f"""
    <html>
    <body style="background:#000;color:white;text-align:center;padding-top:100px;">
        <h1>Enviar ETERNA</h1>
        <a href="{link}" target="_blank">
            <button>Enviar por WhatsApp</button>
        </a>
    </body>
    </html>
    """

# =========================
# EXPERIENCIA
# =========================

@app.get("/pedido/{order_id}", response_class=HTMLResponse)
def pedido(order_id: str):
    order = get_order_or_404(order_id)

    return f"""
    <html>
    <body style="background:#000;color:white;text-align:center;padding-top:100px;">
        <h1>ETERNA</h1>

        <script>
        setTimeout(() => {{
            window.location.href = "/cobrar/{order_id}";
        }}, 8000);
        </script>

        <h2>{order["phrase_1"]}</h2>
        <h2>{order["phrase_2"]}</h2>
        <h2>{order["phrase_3"]}</h2>

        <h2>💸 Has recibido {money(order["gift_amount"])}€</h2>
    </body>
    </html>
    """

# =========================
# COBRAR
# =========================

@app.get("/cobrar/{order_id}", response_class=HTMLResponse)
def cobrar(order_id: str):
    order = get_order_or_404(order_id)

    return f"""
    <html>
    <body style="background:#000;color:white;text-align:center;padding-top:100px;">
        <h1>Cobra tu dinero 💸</h1>
        <p>Has recibido {money(order["gift_amount"])}€</p>

        <a href="/reaccion/{order_id}">
            <button style="padding:16px 30px;border-radius:30px;">Continuar</button>
        </a>
    </body>
    </html>
    """

# =========================
# VIDEO
# =========================

@app.post("/upload-video")
async def upload_video(order_id: str = Form(...), video: UploadFile = File(...)):
    order = get_order_or_404(order_id)

    filepath = reaction_video_path(order_id)

    content = await video.read()
    with open(filepath, "wb") as f:
        f.write(content)

    order["reaction_video"] = filepath

    return JSONResponse({
        "cashout_url": f"/cobrar/{order_id}"
    })

@app.get("/video/{order_id}")
def get_video(order_id: str):
    return FileResponse(reaction_video_path(order_id))

# =========================
# FINAL
# =========================

@app.get("/reaccion/{order_id}", response_class=HTMLResponse)
def reaccion(order_id: str):
    return f"""
    <html>
    <body style="background:#000;color:white;text-align:center;padding-top:100px;">
        <h1>Tu momento ya es ETERNA ❤️</h1>

        <video controls width="300">
            <source src="/video/{order_id}" type="video/webm">
        </video>
    </body>
    </html>
    """

# =========================
# HEALTH
# =========================

@app.get("/health")
def health():
    return {
        "status": "ok",
        "app": "ETERNA V9"
    }