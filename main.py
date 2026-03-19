import uuid
import urllib.parse
from typing import Optional

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse

app = FastAPI(title="ETERNA backend")

PEDIDOS = {}


def crear_link_whatsapp(telefono, nombre, anonimo, link_video):
    telefono = "".join(filter(str.isdigit, telefono))

    if anonimo:
        mensaje = f"""Hola ❤️

Alguien ha creado algo muy especial para ti.

Ábrelo cuando estés en un momento tranquilo.

👉 {link_video}
"""
    else:
        mensaje = f"""Hola ❤️

{nombre} ha creado algo muy especial para ti.

Ábrelo cuando estés en un momento tranquilo.

👉 {link_video}
"""

    mensaje = urllib.parse.quote(mensaje)
    return f"https://wa.me/{telefono}?text={mensaje}"


@app.get("/")
def home():
    return {"status": "ETERNA funcionando"}


@app.post("/crear-eterna", response_class=HTMLResponse)
async def crear_eterna(
    nombre_cliente: str = Form(...),
    email_cliente: str = Form(...),
    telefono_cliente: Optional[str] = Form(None),
    nombre_destinatario: str = Form(...),
    telefono_destinatario: str = Form(...),
    frase_1: str = Form(...),
    frase_2: str = Form(...),
    frase_3: str = Form(...),
    anonimo: Optional[str] = Form(None),
    consentimiento: Optional[str] = Form(None),
):
    if not consentimiento:
        return "<h1>Debes aceptar el consentimiento</h1>"

    order_id = str(uuid.uuid4())
    is_anonymous = anonimo is not None

    PEDIDOS[order_id] = {
        "nombre_cliente": nombre_cliente,
        "email_cliente": email_cliente,
        "telefono_cliente": telefono_cliente,
        "nombre_destinatario": nombre_destinatario,
        "telefono_destinatario": telefono_destinatario,
        "frase_1": frase_1,
        "frase_2": frase_2,
        "frase_3": frase_3,
        "anonimo": is_anonymous,
    }

    stripe_payment_link = "https://buy.stripe.com/XXXXXXXX"

    payment_url = f"{stripe_payment_link}?client_reference_id={urllib.parse.quote(order_id)}"

    return f"""
    <html>
        <head>
            <meta charset="UTF-8">
            <meta http-equiv="refresh" content="2; url={payment_url}" />
            <title>Redirigiendo al pago</title>
        </head>
        <body style="background:black;color:white;text-align:center;padding-top:50px;font-family:Arial;">
            <h2>Redirigiendo al pago...</h2>
            <p>Tu pedido es:</p>
            <p><b>{order_id}</b></p>
            <p>Guárdalo por si necesitas abrir luego tu página de envío:</p>
            <p>/pedido/{order_id}</p>
        </body>
    </html>
    """


@app.get("/pedido/{order_id}", response_class=HTMLResponse)
def ver_pedido(order_id: str):
    pedido = PEDIDOS.get(order_id)

    if not pedido:
        return "<h1>Pedido no encontrado</h1>"

    link_video = f"https://eterna-v2-lab.onrender.com/eterna/{order_id}"

    link_whatsapp = crear_link_whatsapp(
        telefono=pedido["telefono_destinatario"],
        nombre=pedido["nombre_cliente"],
        anonimo=pedido["anonimo"],
        link_video=link_video
    )

    return f"""
    <html>
    <head>
    <meta charset="UTF-8">
    <style>
    body {{
        background:black;
        color:white;
        text-align:center;
        padding-top:80px;
        font-family:Arial;
    }}
    a {{
        background:#25D366;
        padding:15px 25px;
        color:white;
        text-decoration:none;
        border-radius:10px;
        font-size:18px;
    }}
    </style>
    </head>
    <body>

    <h1>ETERNA lista 💔</h1>
    <p>Pedido: {order_id}</p>
    <p>Destinatario: {pedido["nombre_destinatario"]}</p>

    <a href="{link_whatsapp}" target="_blank">
    Enviar por WhatsApp
    </a>

    </body>
    </html>
    """


@app.get("/test-whatsapp", response_class=HTMLResponse)
def test_whatsapp():
    link_video = "https://eterna-v2-lab.onrender.com/demo"

    link_whatsapp = crear_link_whatsapp(
        telefono="+34600111222",
        nombre="Sergio",
        anonimo=False,
        link_video=link_video
    )

    return f"""
    <html>
    <head>
    <meta charset="UTF-8">
    <style>
    body {{
        background:black;
        color:white;
        text-align:center;
        padding-top:80px;
        font-family:Arial;
    }}
    a {{
        background:#25D366;
        padding:15px 25px;
        color:white;
        text-decoration:none;
        border-radius:10px;
        font-size:18px;
    }}
    </style>
    </head>
    <body>

    <h1>Test WhatsApp</h1>

    <a href="{link_whatsapp}" target="_blank">
    Abrir WhatsApp
    </a>

    </body>
    </html>
    """
