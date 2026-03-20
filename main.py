import uuid
import urllib.parse
from typing import Optional

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse

app = FastAPI(title="ETERNA backend")


# =========================
# FAKE DB (temporal)
# =========================

ORDERS = {}


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
):

    order_id = str(uuid.uuid4())

    ORDERS[order_id] = {
        "customer_name": customer_name,
        "customer_email": customer_email,
        "customer_phone": customer_phone,

        "recipient_name": recipient_name,
        "recipient_phone": recipient_phone,

        "phrase_1": phrase_1,
        "phrase_2": phrase_2,
        "phrase_3": phrase_3,

        "paid": True  # 🔥 simulado (Stripe ya lo tienes funcionando)
    }

    return {
        "status": "ok",
        "order_id": order_id,
        "url": f"/pedido/{order_id}"
    }


# =========================
# PEDIDO
# =========================

@app.get("/pedido/{order_id}", response_class=HTMLResponse)
def ver_pedido(order_id: str):

    order = ORDERS.get(order_id)

    if not order:
        return "<h1>Pedido no encontrado</h1>"

    if not order["paid"]:
        return "<h1>Pago pendiente...</h1>"

    # =========================
    # 📱 LIMPIAR TELÉFONO
    # =========================

    telefono_original = order["recipient_phone"]
    telefono = "".join(filter(str.isdigit, telefono_original))

    if telefono.startswith("00"):
        telefono = telefono[2:]

    if telefono.startswith("0"):
        telefono = telefono[1:]

    # 👉 FORZAMOS ESPAÑA
    if not telefono.startswith("34"):
        telefono = "34" + telefono

    # =========================
    # 💬 MENSAJE
    # =========================

    mensaje = (
        "Hola ❤️\n\n"
        "Alguien ha creado algo muy especial para ti.\n\n"
        "Ábrelo cuando estés en un momento tranquilo.\n\n"
        f"👉 https://eterna-v2-lab.onrender.com/pedido/{order_id}\n\n"
        "No es un vídeo cualquiera..."
    )

    mensaje_encoded = urllib.parse.quote(mensaje)

    link_whatsapp = f"https://wa.me/{telefono}?text={mensaje_encoded}"

    # DEBUG (por si algo falla)
    print("📱 Teléfono original:", telefono_original)
    print("📱 Teléfono limpio:", telefono)
    print("📱 Link WhatsApp:", link_whatsapp)

    # =========================
    # HTML
    # =========================

    return f"""
    <html>
    <body style="background:black;color:white;text-align:center;padding-top:100px;font-family:Arial;">

        <h1>ETERNA lista ❤️</h1>

        <br><br>

        <a href="{link_whatsapp}" target="_blank">
            <button style="
                background:#25D366;
                color:white;
                border:none;
                padding:20px 40px;
                font-size:20px;
                border-radius:10px;
                cursor:pointer;
            ">
                Enviar por WhatsApp
            </button>
        </a>

    </body>
    </html>
    """
