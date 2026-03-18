import uuid
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Customer, Recipient, EternaOrder
from schemas import (
    HealthResponse,
    EternaCreationResponse,
    ReactionUploadResponse,
)
from storage_service import StorageService


app = FastAPI(title="ETERNA backend")

Base.metadata.create_all(bind=engine)

storage = StorageService()

app.mount("/media", StaticFiles(directory=str(storage.media_dir)), name="media")


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", service="ETERNA backend")


@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>ETERNA</title>
        <style>
            * { box-sizing: border-box; }
            body {
                margin: 0;
                font-family: Arial, sans-serif;
                background: #0b0b0b;
                color: white;
            }
            .wrap {
                max-width: 760px;
                margin: 0 auto;
                padding: 40px 20px 80px;
            }
            .brand {
                text-align: center;
                margin-bottom: 30px;
            }
            .brand h1 {
                font-size: 48px;
                margin: 0;
                letter-spacing: 6px;
            }
            .brand p {
                color: #cfcfcf;
                margin-top: 10px;
                font-size: 18px;
            }
            .card {
                background: #141414;
                border: 1px solid #222;
                border-radius: 24px;
                padding: 24px;
            }
            label {
                display: block;
                margin: 16px 0 8px;
                font-weight: bold;
            }
            input, textarea {
                width: 100%;
                padding: 14px;
                border-radius: 14px;
                border: 1px solid #333;
                background: #0f0f0f;
                color: white;
                font-size: 16px;
            }
            textarea {
                min-height: 90px;
                resize: vertical;
            }
            input[type="file"],
            input[type="checkbox"] {
                width: auto;
            }
            .checkrow {
                display: flex;
                align-items: center;
                gap: 10px;
                margin-top: 16px;
            }
            button {
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
            }
            .result {
                margin-top: 24px;
                padding: 16px;
                border-radius: 16px;
                background: #101820;
                border: 1px solid #213240;
                display: none;
                white-space: pre-wrap;
            }
            a {
                color: #9fd3ff;
                word-break: break-all;
            }
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

                    <label>Tu teléfono (opcional)</label>
                    <input type="text" name="customer_phone" />

                    <label>Nombre del destinatario</label>
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

                    <div class="checkrow">
                        <input type="checkbox" name="includes_reaction" id="includes_reaction" checked />
                        <label for="includes_reaction" style="margin:0;">Incluir reacción</label>
                    </div>

                    <div class="checkrow">
                        <input type="checkbox" name="gift_active" id="gift_active" />
                        <label for="gift_active" style="margin:0;">Activar regalo económico</label>
                    </div>

                    <label>Cantidad regalo EUR</label>
                    <input type="number" name="gift_amount_eur" value="0" min="0" step="0.01" />

                    <label>Mensaje de regalo (opcional)</label>
                    <textarea name="gift_message"></textarea>

                    <label>Vídeo del regalante (opcional)</label>
                    <input type="file" name="giver_video" accept="video/*" />

                    <label>Sube exactamente 6 fotos</label>
                    <input type="file" name="photos" accept="image/*" multiple required />

                    <button type="submit">Crear mi ETERNA</button>
                </form>

                <div class="result" id="resultBox"></div>
            </div>
        </div>

        <script>
            const form = document.getElementById("eternaForm");
            const resultBox = document.getElementById("resultBox");

            form.addEventListener("submit", async (e) => {
                e.preventDefault();

                resultBox.style.display = "block";
                resultBox.textContent = "Creando tu ETERNA...";

                const files = form.photos.files;
                if (files.length !== 6) {
                    resultBox.textContent = "Error: debes subir exactamente 6 fotos.";
                    return;
                }

                const formData = new FormData();
                formData.append("customer_name", form.customer_name.value);
                formData.append("customer_email", form.customer_email.value);
                formData.append("customer_phone", form.customer_phone.value);
                formData.append("recipient_name", form.recipient_name.value);
                formData.append("recipient_phone", form.recipient_phone.value);
                formData.append("recipient_email", form.recipient_email.value);
                formData.append("phrase1", form.phrase1.value);
                formData.append("phrase2", form.phrase2.value);
                formData.append("phrase3", form.phrase3.value);
                formData.append("includes_reaction", form.includes_reaction.checked ? "true" : "false");
                formData.append("gift_active", form.gift_active.checked ? "true" : "false");
                formData.append("gift_amount_eur", form.gift_amount_eur.value || "0");
                formData.append("gift_message", form.gift_message.value || "");

                if (form.giver_video.files.length > 0) {
                    formData.append("giver_video", form.giver_video.files[0]);
                }

                for (let i = 0; i < files.length; i++) {
                    formData.append("photos", files[i]);
                }

                try {
                    const res = await fetch("/crear-eterna", {
                        method: "POST",
                        body: formData
                    });

                    const data = await res.json();

                    if (!res.ok) {
                        resultBox.textContent = "Error: " + (data.detail || "No se pudo crear la ETERNA.");
                        return;
                    }

                    let text = "ETERNA creada correctamente.\\n\\n";
                    text += "ID: " + data.eterna_id + "\\n";
                    text += "Link privado: " + data.share_url + "\\n";
                    text += "Estado: lista sin vídeo por ahora.\\n";

                    resultBox.innerHTML = text.replace(
                        /(https?:\\/\\/[^\\s]+)/g,
                        '<a href="$1" target="_blank">$1</a>'
                    );
                } catch (err) {
                    resultBox.textContent = "Error inesperado al crear la ETERNA.";
                }
            });
        </script>
    </body>
    </html>
    """


@app.post("/crear-eterna", response_model=EternaCreationResponse)
async def crear_eterna(
    request: Request,
    customer_name: str = Form(...),
    customer_email: str = Form(...),
    customer_phone: Optional[str] = Form(None),
    recipient_name: str = Form(...),
    recipient_phone: Optional[str] = Form(None),
    recipient_email: Optional[str] = Form(None),
    phrase1: str = Form(...),
    phrase2: str = Form(...),
    phrase3: str = Form(...),
    includes_reaction: bool = Form(True),
    gift_active: bool = Form(False),
    gift_amount_eur: float = Form(0.0),
    gift_message: Optional[str] = Form(None),
    giver_video: Optional[UploadFile] = File(None),
    photos: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    if len(photos) != 6:
        raise HTTPException(status_code=400, detail="Debes subir exactamente 6 fotos.")

    if not customer_name.strip():
        raise HTTPException(status_code=400, detail="El nombre del cliente no puede estar vacío.")

    if "@" not in customer_email:
        raise HTTPException(status_code=400, detail="El email del cliente no es válido.")

    if not recipient_name.strip():
        raise HTTPException(status_code=400, detail="El nombre del destinatario no puede estar vacío.")

    if any(not p.strip() for p in [phrase1, phrase2, phrase3]):
        raise HTTPException(status_code=400, detail="Las frases no pueden estar vacías.")

    if gift_amount_eur < 0:
        raise HTTPException(status_code=400, detail="El regalo económico no puede ser negativo.")

    eterna_id = str(uuid.uuid4())
    share_token = str(uuid.uuid4())

    try:
        eterna_folder = storage.create_eterna_folder(eterna_id)
        saved_image_paths = await storage.save_uploaded_images(eterna_folder, photos)

        giver_video_path = None
        if giver_video and giver_video.filename:
            giver_video_path = await storage.save_uploaded_video(
                eterna_folder,
                giver_video,
                "video_regalante"
            )

        customer = db.query(Customer).filter(Customer.email == customer_email.strip()).first()
        if not customer:
            customer = Customer(
                name=customer_name.strip(),
                email=customer_email.strip(),
                phone=customer_phone.strip() if customer_phone else None
            )
            db.add(customer)
            db.commit()
            db.refresh(customer)
        else:
            customer.name = customer_name.strip()
            customer.phone = customer_phone.strip() if customer_phone else None
            db.commit()
            db.refresh(customer)

        recipient = Recipient(
            name=recipient_name.strip(),
            phone=recipient_phone.strip() if recipient_phone else None,
            email=recipient_email.strip() if recipient_email else None
        )
        db.add(recipient)
        db.commit()
        db.refresh(recipient)

        base_url = str(request.base_url).rstrip("/")
        share_url = f"{base_url}/e/{share_token}"

        folder_name = Path(eterna_folder).name
        public_giver_video_path = None
        if giver_video_path:
            public_giver_video_path = f"/media/{folder_name}/{Path(giver_video_path).name}"

        order = EternaOrder(
            eterna_id=eterna_id,
            customer_id=customer.id,
            recipient_id=recipient.id,
            phrase1=phrase1.strip(),
            phrase2=phrase2.strip(),
            phrase3=phrase3.strip(),
            image_count=len(saved_image_paths),
            storage_folder=str(eterna_folder),
            share_token=share_token,
            share_url=share_url,
            status="created",
            includes_reaction=includes_reaction,
            gift_active=gift_active,
            gift_amount_eur=gift_amount_eur,
            gift_message=gift_message.strip() if gift_message else None,
            giver_video_path=public_giver_video_path,
            final_video_path=None
        )

        db.add(order)
        db.commit()

        return EternaCreationResponse(
            ok=True,
            eterna_id=eterna_id,
            share_url=share_url,
            message="ETERNA creada correctamente"
        )

    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error interno al crear ETERNA: {str(e)}")


@app.get("/eterna/{eterna_id}")
def get_eterna(eterna_id: str, db: Session = Depends(get_db)):
    order = db.query(EternaOrder).filter(EternaOrder.eterna_id == eterna_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="ETERNA no encontrada.")

    return JSONResponse({
        "ok": True,
        "eterna_id": order.eterna_id,
        "status": order.status,
        "share_url": order.share_url,
        "customer_name": order.customer.name if order.customer else None,
        "recipient_name": order.recipient.name if order.recipient else None,
        "phrases": [order.phrase1, order.phrase2, order.phrase3],
        "image_count": order.image_count,
        "includes_reaction": order.includes_reaction,
        "gift_active": order.gift_active,
        "gift_amount_eur": order.gift_amount_eur,
        "gift_message": order.gift_message,
        "giver_video_path": order.giver_video_path,
        "reaction_video_path": order.reaction_video_path,
        "final_video_path": order.final_video_path,
        "opened_at": order.opened_at.isoformat() if order.opened_at else None,
    })


@app.get("/e/{token}", response_class=HTMLResponse)
def ver_eterna(token: str, db: Session = Depends(get_db)):
    order = db.query(EternaOrder).filter(EternaOrder.share_token == token).first()

    if not order:
        raise HTTPException(status_code=404, detail="ETERNA no encontrada.")

    if not order.opened_at:
        order.opened_at = datetime.utcnow()
        order.status = "opened"
        db.commit()
        db.refresh(order)

    folder_name = Path(order.storage_folder).name

    image_urls = []
    for i in range(1, order.image_count + 1):
        for ext in [".jpg", ".jpeg", ".png", ".webp"]:
            candidate = Path(order.storage_folder) / f"foto_{i}{ext}"
            if candidate.exists():
                image_urls.append(f"/media/{folder_name}/foto_{i}{ext}")
                break

    images_html = "".join(
        f'<img src="{url}" style="width:100%;border-radius:18px;margin:0 0 18px 0;border:1px solid #222;">'
        for url in image_urls
    )

    giver_video_html = ""
    if order.giver_video_path:
        giver_video_html = f"""
        <div class="card" style="margin-top:24px;">
            <h3>Mensaje en vídeo</h3>
            <video controls playsinline style="width:100%;border-radius:18px;">
                <source src="{order.giver_video_path}">
            </video>
        </div>
        """

    gift_html = ""
    if order.gift_active:
        gift_html = f"""
        <div class="card" style="margin-top:24px;">
            <h3>Regalo</h3>
            <p>{order.gift_amount_eur}€</p>
            <p>{order.gift_message or ""}</p>
        </div>
        """

    reaction_html = ""
    if order.includes_reaction:
        if order.reaction_video_path:
            reaction_html = f"""
            <div class="card" style="margin-top:24px;">
                <h3>Reacción subida</h3>
                <video controls playsinline style="width:100%;border-radius:18px;">
                    <source src="{order.reaction_video_path}">
                </video>
            </div>
            """
        else:
            reaction_html = f"""
            <div class="card" style="margin-top:24px;">
                <h3>Sube tu reacción</h3>
                <form id="reactionForm">
                    <input type="file" name="video" accept="video/*" required />
                    <label style="display:block;margin:14px 0;color:#cfcfcf;">
                        <input type="checkbox" name="permiso_publicar" />
                        Doy permiso para uso promocional
                    </label>
                    <button type="submit">Subir reacción</button>
                </form>
                <div id="reactionMsg" style="margin-top:12px;color:#cfcfcf;"></div>
            </div>
            """

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Tu ETERNA</title>
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                font-family: Arial, sans-serif;
                background: #050505;
                color: white;
            }}
            .wrap {{
                max-width: 760px;
                margin: 0 auto;
                padding: 30px 20px 80px;
            }}
            .hero {{
                text-align: center;
                padding: 18px 0 12px;
            }}
            .hero h1 {{
                margin: 0 0 12px 0;
                font-size: 40px;
                letter-spacing: 6px;
            }}
            .phrase {{
                margin: 0 0 10px 0;
                color: white;
                line-height: 1.5;
            }}
            .card {{
                background: #111;
                border: 1px solid #222;
                border-radius: 24px;
                padding: 20px;
            }}
            input[type="file"] {{
                width: 100%;
                padding: 12px;
                border-radius: 14px;
                border: 1px solid #333;
                background: #0f0f0f;
                color: white;
            }}
            button {{
                width: 100%;
                margin-top: 16px;
                padding: 16px;
                border: none;
                border-radius: 16px;
                background: white;
                color: black;
                font-size: 16px;
                font-weight: bold;
                cursor: pointer;
            }}
        </style>
    </head>
    <body>
        <div class="wrap">
            <div class="hero">
                <h1>ETERNA</h1>
                <p class="phrase">{order.phrase1}</p>
                <p class="phrase">{order.phrase2}</p>
                <p class="phrase">{order.phrase3}</p>
            </div>

            <div class="card">
                {images_html}
            </div>

            {giver_video_html}
            {gift_html}
            {reaction_html}
        </div>

        <script>
            const form = document.getElementById("reactionForm");
            if (form) {{
                form.addEventListener("submit", async (e) => {{
                    e.preventDefault();

                    const msg = document.getElementById("reactionMsg");
                    msg.textContent = "Subiendo reacción...";

                    const data = new FormData(form);

                    try {{
                        const res = await fetch("/reaccion/{order.eterna_id}", {{
                            method: "POST",
                            body: data
                        }});

                        const json = await res.json();

                        if (!res.ok) {{
                            msg.textContent = "Error: " + (json.detail || "No se pudo subir.");
                            return;
                        }}

                        msg.textContent = "Reacción subida correctamente.";
                        setTimeout(() => window.location.reload(), 800);
                    }} catch (err) {{
                        msg.textContent = "Error inesperado al subir la reacción.";
                    }}
                }});
            }}
        </script>
    </body>
    </html>
    """


@app.post("/reaccion/{eterna_id}", response_model=ReactionUploadResponse)
async def subir_reaccion(
    eterna_id: str,
    video: UploadFile = File(...),
    permiso_publicar: bool = Form(False),
    db: Session = Depends(get_db),
):
    order = db.query(EternaOrder).filter(EternaOrder.eterna_id == eterna_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="ETERNA no encontrada.")

    if not order.includes_reaction:
        raise HTTPException(status_code=400, detail="Esta ETERNA no admite reacción.")

    try:
        eterna_folder = Path(order.storage_folder)

        saved_path = await storage.save_uploaded_video(
            eterna_folder,
            video,
            "reaccion"
        )

        folder_name = eterna_folder.name
        public_url = f"/media/{folder_name}/{Path(saved_path).name}"

        order.reaction_video_path = public_url
        order.reaction_permission_public = permiso_publicar
        order.reaction_uploaded_at = datetime.utcnow()
        order.status = "reaction_uploaded"
        db.commit()

        return ReactionUploadResponse(
            ok=True,
            message="Reacción subida correctamente",
            reaction_url=public_url
        )

    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al subir la reacción: {str(e)}")
