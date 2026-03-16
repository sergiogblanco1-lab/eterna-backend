import os
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app.config import APP_NAME, BASE_URL, MAX_PHOTOS, MIN_PHONE_LENGTH, ORDER_STATES
from app.database import Base, engine, get_db
from app.models import Customer, Recipient, EternaOrder
from app.schemas import HealthResponse
from app.services.storage_service import StorageService
from app.services.video_service import VideoService
from app.utils import (
    valid_email,
    valid_phone,
    normalize_phone,
    now_utc,
    new_slug,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="ETERNA")

storage_service = StorageService()
video_service = VideoService()


def upsert_customer(db: Session, name: str, email: str, phone: str) -> Customer:
    existing = db.query(Customer).filter(Customer.email == email).first()
    if existing:
        existing.name = name
        existing.phone = phone
        return existing

    customer = Customer(
        name=name,
        email=email,
        phone=phone,
    )
    db.add(customer)
    db.flush()
    return customer


def create_recipient(db: Session, name: str, phone: str, consent_confirmed: bool) -> Recipient:
    recipient = Recipient(
        name=name,
        phone=phone,
        consent_confirmed=consent_confirmed,
    )
    db.add(recipient)
    db.flush()
    return recipient


def render_home() -> str:
    return """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>ETERNA</title>
    <style>
        * { box-sizing: border-box; }
        html, body { margin: 0; padding: 0; }
        body {
            font-family: Inter, Arial, sans-serif;
            background: #0b0b0b;
            color: #fff;
        }

        .hero {
            min-height: 52vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 56px 20px 90px;
            text-align: center;
            background:
                linear-gradient(180deg, rgba(0,0,0,.38), rgba(0,0,0,.75)),
                radial-gradient(circle at top, rgba(231,194,125,.16), transparent 40%),
                url('https://images.unsplash.com/photo-1517457373958-b7bdd4587205?auto=format&fit=crop&w=1400&q=80') center/cover no-repeat;
        }

        .hero-inner {
            max-width: 760px;
        }

        .eyebrow {
            color: #e7c27d;
            letter-spacing: 2px;
            font-size: 12px;
            text-transform: uppercase;
            margin-bottom: 12px;
        }

        h1 {
            margin: 0;
            font-size: 42px;
            line-height: 1.12;
            font-weight: 600;
        }

        .sub {
            max-width: 650px;
            margin: 18px auto 0;
            color: rgba(255,255,255,.84);
            font-size: 18px;
            line-height: 1.6;
        }

        .shell {
            max-width: 860px;
            margin: -48px auto 80px;
            padding: 0 18px;
        }

        .card {
            background: rgba(18,18,18,.96);
            border: 1px solid #242424;
            border-radius: 26px;
            padding: 28px;
            box-shadow: 0 18px 60px rgba(0,0,0,.38);
            backdrop-filter: blur(8px);
        }

        .topline {
            display: flex;
            justify-content: space-between;
            gap: 20px;
            align-items: center;
            margin-bottom: 20px;
        }

        .topline h2 {
            margin: 0;
            font-size: 24px;
            font-weight: 600;
        }

        .badge {
            font-size: 12px;
            color: #0b0b0b;
            background: linear-gradient(180deg, #e7c27d 0%, #cfa25a 100%);
            border-radius: 999px;
            padding: 8px 12px;
            font-weight: 700;
        }

        .section {
            margin-top: 22px;
        }

        .section:first-of-type {
            margin-top: 0;
        }

        .section-title {
            font-size: 13px;
            color: #e7c27d;
            text-transform: uppercase;
            letter-spacing: 1.8px;
            margin: 0 0 12px;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 14px;
        }

        .full {
            grid-column: 1 / -1;
        }

        label {
            display: block;
            font-size: 14px;
            margin: 0 0 7px;
            color: rgba(255,255,255,.92);
        }

        input, textarea {
            width: 100%;
            border: 1px solid #2d2d2d;
            border-radius: 14px;
            background: #191919;
            color: #fff;
            padding: 14px;
            font-size: 15px;
            outline: none;
        }

        textarea {
            min-height: 100px;
            resize: vertical;
        }

        input:focus, textarea:focus {
            border-color: #cfa25a;
            box-shadow: 0 0 0 3px rgba(207,162,90,.12);
        }

        .hint {
            margin-top: 7px;
            font-size: 13px;
            color: rgba(255,255,255,.58);
        }

        .consent {
            display: flex;
            gap: 10px;
            align-items: flex-start;
            background: #151515;
            border: 1px solid #292929;
            border-radius: 16px;
            padding: 14px;
        }

        .consent input {
            width: auto;
            margin-top: 4px;
        }

        button {
            width: 100%;
            border: none;
            border-radius: 999px;
            background: linear-gradient(180deg, #e7c27d 0%, #cfa25a 100%);
            color: #0b0b0b;
            font-weight: 700;
            font-size: 16px;
            padding: 16px 18px;
            cursor: pointer;
            margin-top: 22px;
        }

        .status {
            margin-top: 14px;
            font-size: 14px;
        }

        .ok { color: #9de2ae; }
        .error { color: #ffabab; }

        @media (max-width: 700px) {
            h1 { font-size: 32px; }
            .sub { font-size: 16px; }
            .grid { grid-template-columns: 1fr; }
            .topline { flex-direction: column; align-items: flex-start; }
            .card { padding: 20px; }
        }
    </style>
</head>
<body>
    <section class="hero">
        <div class="hero-inner">
            <div class="eyebrow">ETERNA</div>
            <h1>Hay momentos que merecen quedarse para siempre.</h1>
            <p class="sub">
                Convierte 6 fotos y 3 frases en un recuerdo emocional que alguien nunca olvidará.
            </p>
        </div>
    </section>

    <main class="shell">
        <section class="card">
            <div class="topline">
                <h2>Crea tu ETERNA</h2>
                <div class="badge">MVP serio</div>
            </div>

            <form id="eternaForm">
                <div class="section">
                    <div class="section-title">Tu información</div>
                    <div class="grid">
                        <div>
                            <label for="name">Tu nombre</label>
                            <input id="name" name="name" required />
                        </div>
                        <div>
                            <label for="email">Tu email</label>
                            <input id="email" name="email" type="email" required />
                        </div>
                        <div class="full">
                            <label for="customer_phone">Tu teléfono</label>
                            <input id="customer_phone" name="customer_phone" required />
                        </div>
                    </div>
                </div>

                <div class="section">
                    <div class="section-title">Destinatario</div>
                    <div class="grid">
                        <div>
                            <label for="recipient_name">Nombre del destinatario</label>
                            <input id="recipient_name" name="recipient_name" required />
                        </div>
                        <div>
                            <label for="recipient_phone">Teléfono del destinatario</label>
                            <input id="recipient_phone" name="recipient_phone" required />
                        </div>
                    </div>
                </div>

                <div class="section">
                    <div class="section-title">Frases</div>
                    <div class="grid">
                        <div class="full">
                            <label for="phrase_1">Frase 1</label>
                            <textarea id="phrase_1" name="phrase_1" required></textarea>
                        </div>
                        <div class="full">
                            <label for="phrase_2">Frase 2</label>
                            <textarea id="phrase_2" name="phrase_2" required></textarea>
                        </div>
                        <div class="full">
                            <label for="phrase_3">Frase 3</label>
                            <textarea id="phrase_3" name="phrase_3" required></textarea>
                        </div>
                    </div>
                </div>

                <div class="section">
                    <div class="section-title">Multimedia</div>
                    <div class="grid">
                        <div class="full">
                            <label for="photos">Sube exactamente 6 fotos</label>
                            <input id="photos" name="photos" type="file" accept="image/*" multiple required />
                            <div class="hint">Formatos permitidos: jpg, jpeg, png, webp.</div>
                        </div>
                        <div class="full">
                            <label for="sender_video">Vídeo del regalante (opcional)</label>
                            <input id="sender_video" name="sender_video" type="file" accept="video/*" />
                            <div class="hint">Preparado para mensaje emocional del regalante.</div>
                        </div>
                    </div>
                </div>

                <div class="section">
                    <div class="section-title">Permiso</div>
                    <div class="consent">
                        <input id="consent_confirmed" name="consent_confirmed" type="checkbox" required />
                        <label for="consent_confirmed" style="margin:0;">
                            Confirmo que el destinatario acepta recibir esta sorpresa y que ETERNA no enviará nada sin permiso.
                        </label>
                    </div>
                </div>

                <button type="submit">Crear mi ETERNA</button>
                <div id="status" class="status"></div>
            </form>
        </section>
    </main>

    <script>
        const form = document.getElementById("eternaForm");
        const statusEl = document.getElementById("status");

        form.addEventListener("submit", async (e) => {
            e.preventDefault();

            statusEl.className = "status";
            statusEl.textContent = "Creando tu ETERNA...";

            const photos = document.getElementById("photos").files;
            if (!photos || photos.length !== 6) {
                statusEl.className = "status error";
                statusEl.textContent = "Debes subir exactamente 6 fotos.";
                return;
            }

            const data = new FormData(form);

            try {
                const response = await fetch("/orders", {
                    method: "POST",
                    body: data
                });

                const json = await response.json();

                if (!response.ok) {
                    statusEl.className = "status error";
                    statusEl.textContent = json.detail || "Ha ocurrido un error.";
                    return;
                }

                statusEl.className = "status ok";
                statusEl.textContent =
                    "ETERNA creada. ID: " + json.order_id + " | Estado: " + json.state;

                form.reset();
            } catch (error) {
                statusEl.className = "status error";
                statusEl.textContent = "No se pudo conectar con el servidor.";
            }
        });
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def home():
    return render_home()


@app.get("/health", response_model=HealthResponse)
def health():
    return {"status": "ok", "service": APP_NAME}


@app.post("/orders")
async def create_order(
    name: str = Form(...),
    email: str = Form(...),
    customer_phone: str = Form(...),
    recipient_name: str = Form(...),
    recipient_phone: str = Form(...),
    phrase_1: str = Form(...),
    phrase_2: str = Form(...),
    phrase_3: str = Form(...),
    consent_confirmed: bool = Form(...),
    photos: List[UploadFile] = File(...),
    sender_video: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    name = name.strip()
    email = email.strip().lower()
    customer_phone = normalize_phone(customer_phone)
    recipient_name = recipient_name.strip()
    recipient_phone = normalize_phone(recipient_phone)
    phrase_1 = phrase_1.strip()
    phrase_2 = phrase_2.strip()
    phrase_3 = phrase_3.strip()

    if not name:
        raise HTTPException(status_code=400, detail="Tu nombre es obligatorio.")

    if not recipient_name:
        raise HTTPException(status_code=400, detail="El nombre del destinatario es obligatorio.")

    if not valid_email(email):
        raise HTTPException(status_code=400, detail="El email no es válido.")

    if not valid_phone(customer_phone, MIN_PHONE_LENGTH):
        raise HTTPException(status_code=400, detail="El teléfono del regalante no es válido.")

    if not valid_phone(recipient_phone, MIN_PHONE_LENGTH):
        raise HTTPException(status_code=400, detail="El teléfono del destinatario no es válido.")

    if len(photos) != MAX_PHOTOS:
        raise HTTPException(status_code=400, detail="Debes subir exactamente 6 fotos.")

    if not phrase_1 or not phrase_2 or not phrase_3:
        raise HTTPException(status_code=400, detail="Las 3 frases son obligatorias.")

    try:
        customer = upsert_customer(db, name, email, customer_phone)
        recipient = create_recipient(db, recipient_name, recipient_phone, consent_confirmed)

        order = EternaOrder(
            customer_id=customer.id,
            recipient_id=recipient.id,
            phrase_1=phrase_1,
            phrase_2=phrase_2,
            phrase_3=phrase_3,
            photos_json="[]",
            sender_video_path=None,
            final_video_path=None,
            reaction_video_path=None,
            public_slug=new_slug(),
            state="uploaded",
            created_at=now_utc(),
            updated_at=now_utc(),
        )
        db.add(order)
        db.flush()

        saved_photos = storage_service.save_photos(order.id, photos)
        saved_sender_video = storage_service.save_sender_video(order.id, sender_video)

        order.photos_json = storage_service.photos_json(saved_photos)
        order.sender_video_path = saved_sender_video
        order.updated_at = now_utc()

        db.commit()

        return {
            "ok": True,
            "order_id": order.id,
            "public_url": f"{BASE_URL}/e/{order.public_slug}",
            "state": order.state,
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@app.get("/orders")
def list_orders(db: Session = Depends(get_db)):
    orders = db.query(EternaOrder).order_by(EternaOrder.created_at.desc()).all()

    items = []
    for order in orders:
        items.append({
            "id": order.id,
            "state": order.state,
            "customer_name": order.customer.name,
            "customer_email": order.customer.email,
            "customer_phone": order.customer.phone,
            "recipient_name": order.recipient.name,
            "recipient_phone": order.recipient.phone,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "public_slug": order.public_slug,
            "sender_video_path": order.sender_video_path,
            "final_video_path": order.final_video_path,
            "reaction_video_path": order.reaction_video_path,
        })

    return {"total": len(items), "items": items}


@app.get("/orders/{order_id}")
def get_order(order_id: str, db: Session = Depends(get_db)):
    order = db.query(EternaOrder).filter(EternaOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")

    return {
        "id": order.id,
        "state": order.state,
        "customer": {
            "id": order.customer.id,
            "name": order.customer.name,
            "email": order.customer.email,
            "phone": order.customer.phone,
        },
        "recipient": {
            "id": order.recipient.id,
            "name": order.recipient.name,
            "phone": order.recipient.phone,
            "consent_confirmed": order.recipient.consent_confirmed,
        },
        "phrases": [order.phrase_1, order.phrase_2, order.phrase_3],
        "photos": storage_service.photos_from_json(order.photos_json),
        "sender_video_path": order.sender_video_path,
        "final_video_path": order.final_video_path,
        "reaction_video_path": order.reaction_video_path,
        "public_slug": order.public_slug,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
    }


@app.post("/orders/{order_id}/generate-video")
def generate_video(order_id: str, db: Session = Depends(get_db)):
    order = db.query(EternaOrder).filter(EternaOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")

    order.state = "processing"
    order.updated_at = datetime.utcnow()
    db.commit()

    try:
        output_path = storage_service.order_final_video_path(order.id)
        final_path = video_service.generate_placeholder_video(output_path)

        order.final_video_path = final_path
        order.state = "video_generated"
        order.updated_at = datetime.utcnow()
        db.commit()

        return {
            "ok": True,
            "order_id": order.id,
            "state": order.state,
            "final_video_path": final_path,
        }
    except Exception as e:
        order.state = "error"
        order.error_message = str(e)
        order.updated_at = datetime.utcnow()
        db.commit()
        raise HTTPException(status_code=500, detail=f"No se pudo generar el vídeo: {str(e)}")


@app.get("/e/{public_slug}", response_class=HTMLResponse)
def public_page(public_slug: str, db: Session = Depends(get_db)):
    order = db.query(EternaOrder).filter(EternaOrder.public_slug == public_slug).first()
    if not order:
        raise HTTPException(status_code=404, detail="ETERNA no encontrada.")

    if order.state == "sent" and not order.opened_at:
        order.opened_at = datetime.utcnow()
        order.state = "opened"
        order.updated_at = datetime.utcnow()
        db.commit()

    recipient_name = order.recipient.name

    return f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>ETERNA</title>
    <style>
        body {{
            margin: 0;
            background: #0b0b0b;
            color: white;
            font-family: Arial, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 24px;
            text-align: center;
        }}
        .box {{
            max-width: 700px;
            background: #121212;
            border: 1px solid #242424;
            border-radius: 24px;
            padding: 34px 22px;
        }}
        .eyebrow {{
            color: #e7c27d;
            letter-spacing: 2px;
            text-transform: uppercase;
            font-size: 12px;
            margin-bottom: 12px;
        }}
        h1 {{
            margin: 0 0 10px;
            font-size: 36px;
        }}
        p {{
            color: rgba(255,255,255,.8);
            line-height: 1.6;
        }}
    </style>
</head>
<body>
    <div class="box">
        <div class="eyebrow">ETERNA</div>
        <h1>Para {recipient_name}</h1>
        <p>Esta es la página privada donde después verá su recuerdo, el vídeo final y la reacción.</p>
        <p>Ahora mismo ya está preparada la estructura seria del sistema.</p>
    </div>
</body>
</html>
"""
