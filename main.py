import html
import re
import uuid
import urllib.parse
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Customer, Recipient, EternaOrder
from storage_service import StorageService


app = FastAPI(title="ETERNA backend")

Base.metadata.create_all(bind=engine)

storage = StorageService()

# Asegura que exista la carpeta media
storage.media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(storage.media_dir)), name="media")


def clean_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    cleaned = re.sub(r"[^\d]", "", phone)
    return cleaned or None


# =========================
# HOME (CREAR + GRABAR)
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
            body{
                background:#000;
                color:#fff;
                font-family:Arial, sans-serif;
                padding:30px;
                max-width:700px;
                margin:auto;
            }
            input, textarea, button{
                width:100%;
                padding:12px;
                margin-top:8px;
                margin-bottom:14px;
                border-radius:10px;
                border:1px solid #333;
                background:#111;
                color:#fff;
                box-sizing:border-box;
            }
            button{
                cursor:pointer;
                background:#fff;
                color:#000;
                font-weight:bold;
            }
            .secondary{
                background:#222;
                color:#fff;
            }
            #preview{
                width:220px;
                border-radius:12px;
                background:#111;
                margin-top:10px;
            }
            #result{
                margin-top:20px;
            }
            .wa-btn{
                display:inline-block;
                padding:12px 18px;
                background:#25D366;
                color:white;
                border-radius:10px;
                text-decoration:none;
                font-weight:bold;
            }
            .link-btn{
                display:inline-block;
                padding:12px 18px;
                background:white;
                color:black;
                border-radius:10px;
                text-decoration:none;
                font-weight:bold;
            }
            .row{
                display:flex;
                gap:10px;
                margin-bottom:14px;
            }
            .row button{
                margin:0;
            }
        </style>
    </head>
    <body>

        <h1>ETERNA</h1>

        <form id="form">
            <input name="customer_name" placeholder="Tu nombre" required>
            <input name="customer_email" type="email" placeholder="Tu email" required>

            <input name="recipient_name" placeholder="Nombre destinatario" required>
            <input name="recipient_phone" placeholder="Teléfono destinatario (con prefijo si hace falta)">

            <textarea name="phrase1" placeholder="Frase 1" required></textarea>
            <textarea name="phrase2" placeholder="Frase 2" required></textarea>
            <textarea name="phrase3" placeholder="Frase 3" required></textarea>

            <label>Sube 6 fotos</label>
            <input type="file" name="photos" multiple accept="image/*" required>

            <h3>Graba tu mensaje</h3>
            <video id="preview" autoplay muted playsinline></video>

            <div class="row">
                <button class="secondary" type="button" onclick="startRecording()">Grabar</button>
                <button class="secondary" type="button" onclick="stopRecording()">Parar</button>
            </div>

            <button type="submit">Crear ETERNA</button>
        </form>

        <div id="result"></div>

        <script>
            let recorder = null;
            let chunks = [];
            let stream = null;
            let giverVideoBlob = null;

            async function startRecording() {
                try {
                    if (stream) {
                        stream.getTracks().forEach(track => track.stop());
                    }

                    stream = await navigator.mediaDevices.getUserMedia({
                        video: { facingMode: "user" },
                        audio: true
                    });

                    const preview = document.getElementById("preview");
                    preview.srcObject = stream;

                    chunks = [];
                    recorder = new MediaRecorder(stream);

                    recorder.ondataavailable = (e) => {
                        if (e.data && e.data.size > 0) {
                            chunks.push(e.data);
                        }
                    };

                    recorder.onstop = () => {
                        giverVideoBlob = new Blob(chunks, { type: "video/webm" });
                        alert("Vídeo grabado");
                    };

                    recorder.start();
                } catch (err) {
                    alert("No se pudo abrir la cámara o el micrófono");
                    console.error(err);
                }
            }

            function stopRecording() {
                if (!recorder || recorder.state === "inactive") {
                    alert("Primero graba un vídeo");
                    return;
                }

                recorder.stop();

                if (stream) {
                    stream.getTracks().forEach(track => track.stop());
                }
            }

            const form = document.getElementById("form");

            form.addEventListener("submit", async (e) => {
                e.preventDefault();

                try {
                    const formData = new FormData(form);

                    const photos = formData.getAll("photos");
                    if (photos.length !== 6) {
                        alert("Tienes que subir exactamente 6 fotos");
                        return;
                    }

                    if (giverVideoBlob) {
                        formData.append("giver_video", giverVideoBlob, "giver.webm");
                    }

                    const res = await fetch("/crear-eterna", {
                        method: "POST",
                        body: formData
                    });

                    const data = await res.json();

                    if (!res.ok) {
                        alert(data.detail || "Error al crear la ETERNA");
                        return;
                    }

                    let html = `
                        <p>ETERNA creada</p>
                        <a class="link-btn" href="${data.share_url}" target="_blank">Abrir ETERNA</a>
                    `;

                    if (data.whatsapp_url) {
                        html += `
                            <br><br>
                            <a class="wa-btn" href="${data.whatsapp_url}" target="_blank">
                                Enviar por WhatsApp
                            </a>
                        `;
                    }

                    document.getElementById("result").innerHTML = html;
                } catch (err) {
                    console.error(err);
                    alert("Ha ocurrido un error al enviar el formulario");
                }
            });
        </script>

    </body>
    </html>
    """


# =========================
# CREAR ETERNA
# =========================

@app.post("/crear-eterna")
async def crear_eterna(
    request: Request,
    customer_name: str = Form(...),
    customer_email: str = Form(...),
    recipient_name: str = Form(...),
    recipient_phone: Optional[str] = Form(None),
    phrase1: str = Form(...),
    phrase2: str = Form(...),
    phrase3: str = Form(...),
    photos: List[UploadFile] = File(...),
    giver_video: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    if len(photos) != 6:
        raise HTTPException(status_code=400, detail="Sube exactamente 6 fotos")

    eterna_id = str(uuid.uuid4())
    token = str(uuid.uuid4())

    folder = storage.create_eterna_folder(eterna_id)
    await storage.save_uploaded_images(folder, photos)

    if giver_video:
        await storage.save_uploaded_video(folder, giver_video, "giver")

    customer = Customer(
        name=customer_name.strip(),
        email=customer_email.strip()
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)

    recipient = Recipient(
        name=recipient_name.strip(),
        phone=clean_phone(recipient_phone)
    )
    db.add(recipient)
    db.commit()
    db.refresh(recipient)

    share_url = f"{str(request.base_url).rstrip('/')}/e/{token}"

    order = EternaOrder(
        eterna_id=eterna_id,
        customer_id=customer.id,
        recipient_id=recipient.id,
        phrase1=phrase1.strip(),
        phrase2=phrase2.strip(),
        phrase3=phrase3.strip(),
        image_count=6,
        storage_folder=str(folder),
        share_token=token,
        share_url=share_url
    )

    db.add(order)
    db.commit()

    whatsapp_url = None
    if recipient.phone:
        msg = urllib.parse.quote(f"Te han enviado una ETERNA:\n{share_url}")
        whatsapp_url = f"https://wa.me/{recipient.phone}?text={msg}"

    return {
        "share_url": share_url,
        "whatsapp_url": whatsapp_url
    }


# =========================
# VER ETERNA + REACCIÓN
# =========================

@app.get("/e/{token}", response_class=HTMLResponse)
def ver(token: str, db: Session = Depends(get_db)):
    order = db.query(EternaOrder).filter(EternaOrder.share_token == token).first()
    if not order:
        raise HTTPException(status_code=404, detail="ETERNA no encontrada")

    folder = Path(order.storage_folder)
    folder_name = folder.name

    images = []
    for i in range(1, 7):
        for ext in [".jpg", ".jpeg", ".png", ".webp"]:
            f = folder / f"foto_{i}{ext}"
            if f.exists():
                images.append(f"/media/{folder_name}/{f.name}")
                break

    video_html = ""
    if (folder / "giver.webm").exists():
        video_html = f"""
        <div style="margin:20px 0;">
            <video controls playsinline style="width:100%;max-width:420px;border-radius:14px;">
                <source src="/media/{folder_name}/giver.webm" type="video/webm">
            </video>
        </div>
        """

    phrase1 = html.escape(order.phrase1 or "")
    phrase2 = html.escape(order.phrase2 or "")
    phrase3 = html.escape(order.phrase3 or "")

    images_html = "".join(
        [f'<img src="{img}" style="width:100%;max-width:420px;border-radius:14px;margin:12px 0;">' for img in images]
    )

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ETERNA</title>
        <style>
            body {{
                background:black;
                color:white;
                text-align:center;
                font-family:Arial, sans-serif;
                padding:20px;
                max-width:500px;
                margin:auto;
            }}
            button {{
                padding:14px 24px;
                border:none;
                border-radius:12px;
                background:white;
                color:black;
                font-weight:bold;
                cursor:pointer;
                margin-top:20px;
            }}
            #content {{
                display:none;
                margin-top:30px;
            }}
            #preview {{
                width:120px;
                position:fixed;
                bottom:10px;
                right:10px;
                border-radius:12px;
                background:#111;
            }}
            .phrase {{
                font-size:22px;
                line-height:1.5;
                margin:30px 0;
            }}
        </style>
    </head>
    <body>

        <h2>Prepárate...</h2>
        <button id="startBtn" onclick="start()">Comenzar</button>

        <div id="content">
            <p class="phrase">{phrase1}</p>
            {video_html}
            {images_html}
            <p class="phrase">{phrase2}</p>
            <p class="phrase">{phrase3}</p>
        </div>

        <video id="preview" autoplay muted playsinline></video>

        <script>
            let recorder = null;
            let chunks = [];
            let stream = null;

            async function start() {{
                try {{
                    document.getElementById("startBtn").style.display = "none";
                    document.getElementById("content").style.display = "block";

                    stream = await navigator.mediaDevices.getUserMedia({{
                        video: {{ facingMode: "user" }},
                        audio: true
                    }});

                    const preview = document.getElementById("preview");
                    preview.srcObject = stream;

                    recorder = new MediaRecorder(stream);
                    chunks = [];

                    recorder.ondataavailable = (e) => {{
                        if (e.data && e.data.size > 0) {{
                            chunks.push(e.data);
                        }}
                    }};

                    recorder.onstop = upload;
                    recorder.start();

                    setTimeout(() => {{
                        if (recorder && recorder.state !== "inactive") {{
                            recorder.stop();
                        }}
                        if (stream) {{
                            stream.getTracks().forEach(track => track.stop());
                        }}
                    }}, 15000);
                }} catch (err) {{
                    console.error(err);
                    alert("No se pudo iniciar la grabación de la reacción");
                }}
            }}

            async function upload() {{
                try {{
                    const blob = new Blob(chunks, {{ type: "video/webm" }});
                    const fd = new FormData();
                    fd.append("video", blob, "reaction.webm");

                    const res = await fetch("/reaccion/{order.eterna_id}", {{
                        method: "POST",
                        body: fd
                    }});

                    const data = await res.json();

                    if (!res.ok) {{
                        alert(data.detail || "No se pudo guardar la reacción");
                        return;
                    }}

                    alert("Reacción guardada");
                }} catch (err) {{
                    console.error(err);
                    alert("Error al subir la reacción");
                }}
            }}
        </script>

    </body>
    </html>
    """


# =========================
# GUARDAR REACCIÓN
# =========================

@app.post("/reaccion/{eterna_id}")
async def reaccion(
    eterna_id: str,
    video: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    order = db.query(EternaOrder).filter(EternaOrder.eterna_id == eterna_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    folder = Path(order.storage_folder)
    await storage.save_uploaded_video(folder, video, "reaction")

    return {"ok": True}
