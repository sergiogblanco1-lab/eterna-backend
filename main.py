import uuid
import urllib.parse
from typing import Optional

from fastapi import FastAPI, Form

app = FastAPI(title="ETERNA backend")


@app.post("/crear-eterna")
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
    # Validación básica
    if not consentimiento:
        return {
            "ok": False,
            "error": "Debes aceptar el consentimiento para continuar."
        }

    # Traducción interna a variables del sistema
    customer_name = nombre_cliente
    customer_email = email_cliente
    customer_phone = telefono_cliente
    recipient_name = nombre_destinatario
    recipient_phone = telefono_destinatario
    phrase_1 = frase_1.strip()
    phrase_2 = frase_2.strip()
    phrase_3 = frase_3.strip()
    is_anonymous = anonimo is not None

    # Nombre que verá el destinatario
    sender_name = "Alguien" if is_anonymous else customer_name

    # Crear ID único del pedido
    order_id = str(uuid.uuid4())

    # Aquí luego guardarás en base de datos si quieres
    pedido = {
        "order_id": order_id,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "customer_phone": customer_phone,
        "recipient_name": recipient_name,
        "recipient_phone": recipient_phone,
        "phrase_1": phrase_1,
        "phrase_2": phrase_2,
        "phrase_3": phrase_3,
        "is_anonymous": is_anonymous,
        "sender_name": sender_name,
        "paid": False,
    }

    # Tu link de pago real de Stripe
    stripe_payment_link = "https://buy.stripe.com/TU_LINK_REAL"

    # Pasamos el order_id en la URL para identificar el pago
    payment_url = f"{stripe_payment_link}?client_reference_id={urllib.parse.quote(order_id)}"

    return {
        "ok": True,
        "message": "Pedido creado correctamente",
        "pedido": pedido,
        "payment_url": payment_url
    }
