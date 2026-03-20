import uuid
import urllib.parse
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse

# =========================
# APP
# =========================

app = FastAPI(title="ETERNA")

# =========================
# BASE SIMPLE (MEMORIA)
# =========================

ORDERS = {}

# =========================
# HOME
# =========================

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
    <body style="background:black;color:white;text-align:center;padding-top:80px;font-family:Arial;">
        <h1>ETERNA</h1>
        <p>Crear experiencia</p>

        <form action="/crear-eterna" method="post">
            <input name="phrase_1" placeholder="Frase 1"><br><br>
            <input name="phrase_2" placeholder="Frase 2"><br><br>
            <input name="phrase_3" placeholder="Frase 3"><br><br>
            <input name="amount" placeholder="Dinero (€)"><br><br>

            <button type="submit">Crear</button>
        </form>
    </body>
    </html>
    """

# =========================
# CREAR ETERNA
# =========================

@app.post("/crear-eterna")
def crear_eterna(
    phrase_1: str = Form(...),
    phrase_2: str = Form(...),
    phrase_3: str = Form(...),
    amount: float = Form(...)
):
    order_id = str(uuid.uuid4())

    # 💰 CONFIGURACIÓN
    PRECIO_VIDEO = 5
    COMISION = 0.05

    # cálculo correcto
    comision = amount * COMISION
    total = amount + comision + PRECIO_VIDEO

    ORDERS[order_id] = {
        "phrase_1": phrase_1,
        "phrase_2": phrase_2,
        "phrase_3": phrase_3,
        "amount": amount,
        "comision": round(comision, 2),
        "precio_video": PRECIO_VIDEO,
        "total": round(total, 2),
        "paid": True  # simulamos pago
    }

    return RedirectResponse(url=f"/ver/{order_id}", status_code=303)

# =========================
# VER ETERNA
# =========================

@app.get("/ver/{order_id}", response_class=HTMLResponse)
def ver_eterna(order_id: str):
    order = ORDERS.get(order_id)

    if not order:
        return HTMLResponse("<h1>No existe</h1>")

    return HTMLResponse(f"""
    <html>
    <body style="background:black;color:white;text-align:center;font-family:Arial;padding-top:80px;">

        <h1>ETERNA</h1>

        <p>Esto se está viviendo contigo ❤️</p>

        <div style="margin-top:40px;font-size:24px;">
            <p>{order["phrase_1"]}</p>
            <p>{order["phrase_2"]}</p>
            <p>{order["phrase_3"]}</p>
        </div>

        <h2 style="margin-top:60px;color:#00ff88;">
            Has recibido {order["amount"]}€
        </h2>

        <p style="margin-top:20px;">
            Comisión: {order["comision"]}€
        </p>

        <p>
            Vídeo ETERNA: {order["precio_video"]}€
        </p>

        <h3 style="margin-top:20px;">
            Total pagado: {order["total"]}€
        </h3>

        <p style="margin-top:40px;">
            Tu momento ha sido vivido ❤️
        </p>

    </body>
    </html>
    """)

# =========================
# TEST
# =========================

@app.get("/test")
def test():
    return {"status": "ok"}
