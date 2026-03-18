import uuid
import urllib.parse
from pathlib import Path
from typing import List, Optional
from datetime import datetime
import os
import stripe

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Customer, Recipient, EternaOrder
from storage_service import StorageService


# =========================
# CONFIG
# =========================

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

app = FastAPI(title="ETERNA backend")

Base.metadata.create_all(bind=engine)

storage = StorageService()
app.mount("/media", StaticFiles(directory=str(storage.media_dir)), name="media")


# =========================
# HOME
# =========================

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
    <body style="background:black;color:white;font-family:Arial;padding:30px;">

    <h1>ETERNA</h1>

    <form id="form">
        <input name="customer_name" placeholder="Tu nombre"><br><br>
        <input name="customer_email" placeholder="Tu email"><br><br>

        <input name="recipient_name" placeholder="Nombre destinatario"><br><br>
        <input name="recipient_phone" placeholder="Teléfono destinatario"><br><br>

        <textarea name="phrase1" placeholder="Frase 1"></textarea><br><br>
        <textarea name="phrase2" placeholder="Frase 2"></textarea><br><br>
        <textarea name="phrase3" placeholder="Frase 3"></textarea><br><br>

        <input type="file" name="photos" multiple required><br><br>

        <h3>Graba tu mensaje</h3>
        <video id="preview" autoplay muted style="width:200px;"></video><br><br>

        <button type="button" onclick="startRecording()">Grabar</button>
        <button type="button" onclick="stopRecording()">Parar</button><br><br>

        <button type="submit">Crear ETERNA</button>
    </form>

    <div id="result"></div>

    <script>
    let recorder;
    let chunks = [];
    let stream;

    async function startRecording() {
        stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: "user" },
            audio: true
        });

        preview.srcObject = stream;

        recorder = new MediaRecorder(stream);
        chunks = [];

        recorder.ondataavailable = e => chunks.push(e.data);

        recorder.start();
    }

    function stopRecording() {
        recorder.stop();

        recorder.onstop = () => {
            const blob = new Blob(chunks, { type: "video/webm" });
            const file = new File([blob], "giver.webm");

            const dt = new DataTransfer();
            dt.items.add(file);

            const input = document.createElement("input");
            input.type = "file";
            input.name = "giver_video";
            input.files = dt.files;

            form.appendChild(input);

            alert("Vídeo grabado");
        };
    }

    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        const fd = new FormData(form);

        const res = await fetch("/crear-eterna", {
            method: "POST",
            body: fd
        });

        const data = await res.json();

        let html = `<a href="${data.share_url}" target="_blank">Abrir</a>`;

        if (data.whatsapp_url) {
            html += `<br><br>
            <a href="${data.whatsapp_url}" target="_blank"
            style="padding:12px;background:#25D366;color:white;">
            WhatsApp
            </a>`;
        }

        html += `<br><br>
        <a href="/pagar/${data.eterna_id}" target="_blank"
        style="padding:12px;background:white;color:black;">
        Pagar
        </a>`;

        result.innerHTML = html;
    });
    </script>

    </body>
    </html>
    """


# =========================
# CREAR ETERNA
# =========================

@app.post("/crear-eterna")
async def crear(
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
        raise HTTPException(400, "Sube 6 fotos")

    eterna_id = str(uuid.uuid4())
    token = str(uuid.uuid4())

    folder = storage.create_eterna_folder(eterna_id)
    await storage.save_uploaded_images(folder, photos)

    if giver_video:
        await storage.save_uploaded_video(folder, giver_video, "giver")

    customer = Customer(name=customer_name, email=customer_email)
    db.add(customer)
    db.commit()
    db.refresh(customer)

    recipient = Recipient(name=recipient_name, phone=recipient_phone)
    db.add(recipient)
    db.commit()

    share_url = f"{str(request.base_url).rstrip('/')}/e/{token}"

    order = EternaOrder(
        eterna_id=eterna_id,
        customer_id=customer.id,
        recipient_id=recipient.id,
        phrase1=phrase1,
        phrase2=phrase2,
        phrase3=phrase3,
        image_count=6,
        storage_folder=str(folder),
        share_token=token,
        share_url=share_url,
        is_paid=False
    )

    db.add(order)
    db.commit()

    whatsapp_url = None
    if recipient_phone:
        phone = recipient_phone.replace("+","").replace(" ","")
        msg = urllib.parse.quote(f"Te han enviado una ETERNA:\n{share_url}")
        whatsapp_url = f"https://wa.me/{phone}?text={msg}"

    return {
        "eterna_id": eterna_id,
        "share_url": share_url,
        "whatsapp_url": whatsapp_url
    }


# =========================
# PAGO STRIPE
# =========================

@app.get("/pagar/{eterna_id}")
def pagar(eterna_id: str, db: Session = Depends(get_db)):

    order = db.query(EternaOrder).filter(EternaOrder.eterna_id == eterna_id).first()

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "eur",
                "product_data": {"name": "ETERNA"},
                "unit_amount": 1999,
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=order.share_url + "?paid=1",
        cancel_url=order.share_url,
    )

    return HTMLResponse(f"<script>window.location='{session.url}'</script>")


# =========================
# VER ETERNA
# =========================

@app.get("/e/{token}", response_class=HTMLResponse)
def ver(token: str, paid: int = Query(0), db: Session = Depends(get_db)):

    order = db.query(EternaOrder).filter(EternaOrder.share_token == token).first()

    if paid == 1:
        order.is_paid = True
        db.commit()

    if not order.is_paid:
        return HTMLResponse(f"""
        <h2 style="color:white;background:black;padding:40px;">
        ETERNA bloqueada<br><br>
        <a href="/pagar/{order.eterna_id}">Pagar</a>
        </h2>
        """)

    folder = Path(order.storage_folder)
    folder_name = folder.name

    imgs = []
    for i in range(1,7):
        for ext in [".jpg",".png",".jpeg",".webp"]:
            f = folder / f"foto_{i}{ext}"
            if f.exists():
                imgs.append(f"/media/{folder_name}/{f.name}")
                break

    giver = ""
    if (folder/"giver.webm").exists():
        giver = f"<video controls src='/media/{folder_name}/giver.webm' style='width:100%'></video>"

    reaction = ""
    if (folder/"reaction.webm").exists():
        reaction = f"<video controls src='/media/{folder_name}/reaction.webm' style='width:100%'></video>"

    return f"""
    <html>
    <body style="background:black;color:white;text-align:center;">

    <button onclick="start()">Comenzar</button>

    <div id="content" style="display:none;">
    <p>{order.phrase1}</p>
    {giver}
    {''.join([f'<img src="{i}" style="width:100%;">' for i in imgs])}
    <p>{order.phrase2}</p>
    <p>{order.phrase3}</p>
    {reaction}
    </div>

    <video id="preview" autoplay muted style="width:120px;position:fixed;bottom:10px;right:10px;"></video>

    <script>
    let r,c=[],s;

    async function start(){{
        content.style.display="block";

        s=await navigator.mediaDevices.getUserMedia({{video:true,audio:true}});
        preview.srcObject=s;

        r=new MediaRecorder(s);
        r.ondataavailable=e=>c.push(e.data);
        r.onstop=upload;
        r.start();

        setTimeout(()=>r.stop(),15000);
    }}

    async function upload(){{
        const b=new Blob(c);
        const f=new File([b],"reaction.webm");
        const fd=new FormData();
        fd.append("video",f);

        await fetch("/reaccion/{order.eterna_id}",{{method:"POST",body:fd}});
        location.reload();
    }}
    </script>

    </body>
    </html>
    """


# =========================
# GUARDAR REACCIÓN
# =========================

@app.post("/reaccion/{eterna_id}")
async def reaccion(eterna_id: str, video: UploadFile = File(...), db: Session = Depends(get_db)):
    order = db.query(EternaOrder).filter(EternaOrder.eterna_id == eterna_id).first()
    folder = Path(order.storage_folder)
    await storage.save_uploaded_video(folder, video, "reaction")
    return {"ok": True}
