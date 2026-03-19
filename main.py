import uuid
import urllib.parse
from typing import Optional

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse

app = FastAPI(title="ETERNA backend")


@app.get("/")
def home():
    return {
        "status": "ETERNA backend activo",
        "endpoint_formulario": "/crear-eterna"
    }


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
    # Validación mínima
    if not consentimiento:
        return """
        <html>
            <body style="background:black;color:white;font-family:Arial;text-align:center;padding-top:60px;">
                <h1>Falta el consentimiento</h1>
                <p>Debes aceptar que este contenido será enviado a la persona indicada.</p>
            </body>
        </html>
        """

    # Traducción interna a variables del sistema
    customer_name = nombre_cliente.strip()
    customer_email = email_cliente.strip()
    customer_phone = telefono_cliente.strip() if telefono_cliente else None

    recipient_name = nombre_destinatario.strip()
    recipient_phone = telefono_destinatario.strip()

    phrase_1_clean = frase_1.strip()
    phrase_2_clean = frase_2.strip()
    phrase_3_clean = frase_3.strip()

    is_anonymous = anonimo is not None
    sender_name = "Alguien" if is_anonymous else customer_name

    # Crear pedido
    order_id = str(uuid.uuid4())

    # Aquí, más adelante, podrás guardar en base de datos
    order_data = {
        "order_id": order_id,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "customer_phone": customer_phone,
        "recipient_name": recipient_name,
        "recipient_phone": recipient_phone,
        "phrase_1": phrase_1_clean,
        "phrase_2": phrase_2_clean,
        "phrase_3": phrase_3_clean,
        "is_anonymous": is_anonymous,
        "sender_name": sender_name,
        "paid": False,
    }

    print("Nuevo pedido ETERNA:")
    print(order_data)

    # TU LINK REAL DE STRIPE
    stripe_payment_link = "https://buy.stripe.com/TU_LINK_REAL"

    # Añadimos el order_id para identificar el pago
    payment_url = f"{stripe_payment_link}?client_reference_id={urllib.parse.quote(order_id)}"

    # Redirección automática a Stripe
    return f"""
    <html>
        <head>
            <meta charset="UTF-8">
            <meta http-equiv="refresh" content="0; url={payment_url}" />
            <title>Redirigiendo al pago</title>
            <style>
                body {{
                    background: #000000;
                    color: #ffffff;
                    font-family: Arial, sans-serif;
                    text-align: center;
                    padding-top: 80px;
                }}
                .box {{
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 30px;
                    border: 1px solid #222;
                    border-radius: 16px;
                    background: #0d0d0d;
                }}
                a {{
                    color: #ffffff;
                }}
            </style>
        </head>
        <body>
            <div class="box">
                <h1>Redirigiendo al pago...</h1>
                <p>En unos segundos se abrirá Stripe.</p>
                <p>Si no ocurre automáticamente, pulsa aquí:</p>
                <p><a href="{payment_url}">Ir al pago</a></p>
            </div>
        </body>
    </html>
    """
