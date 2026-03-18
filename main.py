import os
import uuid
from pathlib import Path
from typing import List

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Customer, Recipient, EternaOrder
from schemas import HealthResponse, EternaCreateResponse
from storage_service import StorageService
from video_engine import VideoEngine


app = FastAPI(title="ETERNA backend")

Base.metadata.create_all(bind=engine)

storage = StorageService()
video_engine = VideoEngine()

# Asegura carpeta storage
Path("storage").mkdir(parents=True, exist_ok=True)

# Sirve archivos guardados
app.mount("/media", StaticFiles(directory="storage"), name="media")


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", service="ETERNA backend")


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    base_url = str(request.base_url).rstrip("/")

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>ETERNA</title>
        <style>
            * {{
                box-sizing: border-box;
            }}
            body {{
                margin: 0;
                font-family: Arial, sans-serif;
                background: #0b0b0b;
                color: white;
            }}
            .wrap {{
                max-width: 760px;
                margin: 0 auto;
                padding: 40px 20px 80px;
            }}
            .brand {{
                text-align: center;
                margin-bottom: 30px;
            }}
            .brand h1 {{
                font-size: 48px;
                margin: 0;
                letter-spacing: 6px;
            }}
            .brand p {{
                color: #cfcfcf;
                margin-top: 10px;
                font-size: 18px;
            }}
            .card {{
                background: #141414;
                border: 1px solid #222;
                border-radius: 24px;
                padding: 24px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.35);
            }}
            label {{
                display: block;
                margin: 16px 0 8px;
                font-weight: bold;
            }}
            input, textarea {{
                width: 100%;
                padding: 14px;
                border-radius: 14px;
                border: 1px solid #333;
                background: #0f0f0f;
                color: white;
                font-size: 16px;
            }}
            textarea {{
                min-height: 90px;
                resize: vertical;
            }}
            input[type="file"] {{
                padding: 10px;
                background: #111;
            }}
            button {{
                width: 100%;
                margin-top: 24px;
                padding: 16px;
                border: none;
                border-radius: 16px;
                background: white;
                color: black;
                font-size: 17px;
                font-weight: bold;
                cursor: pointer;
            }}
            button:hover {{
                opacity: 0.92;
            }}
            .result {{
                margin-top: 24px;
                padding: 16px;
                border-radius: 16px;
                background: #101820;
                border: 1px solid #213240;
                display: none;
                white-space: pre-wrap;
            }}
            .small {{
                font-size: 14px;
                color: #b9b9b9;
                margin-top: 10px;
            }}
            a {{
                color: #9fd3ff;
            }}
        </style>
    </head>
    <body>
        <div class="wrap">
            <div class="brand">
                <h1>ETERNA</h1>
                <p>Transforma 6 fotos y 3 frases en un recuerdo emocional.</p>
            </div>

            <div class="card">
                <form id="eternaForm">
                    <label>Tu nombre</label>
                    <input type="text" name="customer_name" required />

                    <label>Tu email</label>
                    <input type="email" name="customer_email" required />

                    <label>Nombre de la persona que recibe la ETERNA</label>
                    <input type="text" name="recipient_name" required />

                    <label>Teléfono del destinatario (opcional)</label>
                    <input type="text" name="recipient_phone" />

                    <label>Email del destinatario (opcional)</label>
                    <input type="email" name="recipient_email" />

                    <label>Frase 1</label>
                    <textarea name="phrase1" required></textarea>

                    <label>Frase 2</label>
                    <textarea name="phrase2" required></textarea>

                    <label>Frase 3</label>
                    <textarea name="phrase3" required></textarea>

                    <label>Sube entre 1 y 6 fotos</label>
                    <input type="file" name="photos" accept="image/*" multiple required />

                    <div class="small">Consejo: usa fotos verticales o bonitas para que el vídeo quede más emotivo.</div>

                    <button type="submit">Crear mi ETERNA</button>
                </form>

                <div class="result" id="resultBox"></div>
            </div>
        </div>

        <script>
            const form = document.getElementById("eternaForm");
            const resultBox = document.getElementById("resultBox");

            form.addEventListener("submit", async (e) => {{
                e.preventDefault();

                resultBox.style.display = "block";
                resultBox.textContent = "Creando tu ETERNA...";

                const formData = new FormData();

                formData.append("customer_name", form.customer_name.value);
                formData.append("customer_email", form.customer_email.value);
                formData.append("recipient_name", form.recipient_name.value);
                formData.append("recipient_phone", form.recipient_phone.value);
                formData.append("recipient_email", form.recipient_email.value);
                formData.append("phrase1", form.phrase1.value);
                formData.append("phrase2", form.phrase2.value);
                formData.append("phrase3", form.phrase3.value);

                const files = form.photos.files;
                for (let i = 0; i < files.length; i++) {{
                    formData.append("photos", files[i]);
                }}

                try {{
                    const res = await fetch("/crear-eterna", {{
                        method: "POST",
                        body: formData
                    }});

                    const data = await res.json();

                    if (!res.ok) {{
                        resultBox.textContent = "Error: " + (data.detail || "No se pudo crear la ETERNA.");
                        return;
                    }}

                    let text = "ETERNA creada correctamente.\\n\\n";
                    text += "ID: " + data.eterna_id + "\\n";
                    if (data.video_url) {{
                        const fullVideoUrl = "{base_url}" + data.video_url;
                        text += "Vídeo: " + fullVideoUrl + "\\n";
                        text += "\\nAbre este enlace para ver el vídeo.";
                    }}

                    resultBox.innerHTML = text.replace(
                        /(https?:\\/\\/[^\\s]+)/g,
                        '<a href="$1" target="_blank">$1</a>'
                    );
                }} catch (err) {{
                    resultBox.textContent = "Error inesperado al crear la ETERNA.";
                }}
            }});
        </script>
    </body>
    </html>
    """


@app.post("/crear-eterna", response_model=EternaCreateResponse)
async def crear_eterna(
    request: Request,
    customer_name: str = Form(...),
    customer_email: str = Form(...),
    recipient_name: str = Form(...),
    recipient_phone: str = Form(""),
    recipient_email: str = Form(""),
    phrase1: str = Form(...),
    phrase2: str = Form(...),
    phrase3: str = Form(...),
    photos: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    if not photos or len(photos) == 0:
        raise HTTPException(status_code=400, detail="Debes subir al menos 1 foto.")

    if len(photos) > 6:
        raise HTTPException(status_code=400, detail="Solo se permiten hasta 6 fotos.")

    eterna_id = str(uuid.uuid4())
    eterna_folder = storage.create_eterna_folder(eterna_id)

    phrases = [phrase1.strip(), phrase2.strip(), phrase3.strip()]
    storage.save_phrases(eterna_folder, phrases)

    try:
        saved_images = await storage.save_uploaded_images(eterna_folder, photos)
        output_video_path = storage.get_video_output_path(eterna_folder)

        video_engine.generate_video(
            image_paths=saved_images,
            phrases=phrases,
            output_path=output_video_path
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando el vídeo: {str(e)}")

    customer = Customer(
        name=customer_name.strip(),
        email=customer_email.strip()
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)

    recipient = Recipient(
        name=recipient_name.strip(),
        phone=recipient_phone.strip() or None,
        email=recipient_email.strip() or None
    )
    db.add(recipient)
    db.commit()
    db.refresh(recipient)

    order = EternaOrder(
        eterna_id=eterna_id,
        customer_id=customer.id,
        recipient_id=recipient.id,
        phrase1=phrases[0],
        phrase2=phrases[1],
        phrase3=phrases[2],
        image_count=len(saved_images),
        storage_folder=str(eterna_folder),
        video_path=output_video_path,
        status="completed"
    )
    db.add(order)
    db.commit()

    video_url = storage.get_public_video_url(eterna_id)

    return EternaCreateResponse(
        ok=True,
        eterna_id=eterna_id,
        message="ETERNA creada correctamente",
        video_url=video_url
    )


@app.get("/eterna/{eterna_id}")
def get_eterna(eterna_id: str, db: Session = Depends(get_db)):
    order = db.query(EternaOrder).filter(EternaOrder.eterna_id == eterna_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="ETERNA no encontrada.")

    return JSONResponse({
        "ok": True,
        "eterna_id": order.eterna_id,
        "status": order.status,
        "customer_name": order.customer.name if order.customer else None,
        "customer_email": order.customer.email if order.customer else None,
        "recipient_name": order.recipient.name if order.recipient else None,
        "recipient_phone": order.recipient.phone if order.recipient else None,
        "recipient_email": order.recipient.email if order.recipient else None,
        "phrases": [
            order.phrase1,
            order.phrase2,
            order.phrase3
        ],
        "image_count": order.image_count,
        "video_url": f"/media/{order.eterna_id}/video.mp4" if order.video_path else None,
        "created_at": order.created_at.isoformat() if order.created_at else None,
    })
