import uuid
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import Base, engine, get_db
from models import Customer, Recipient, EternaOrder
from storage_service import StorageService

app = FastAPI(title="ETERNA backend")

Base.metadata.create_all(bind=engine)

storage = StorageService()

app.mount("/media", StaticFiles(directory=str(storage.temp_dir)), name="media")


# -----------------------
# RESPUESTAS
# -----------------------
class EternaCreationResponse(BaseModel):
    ok: bool
    eterna_id: str
    share_url: str
    message: str = "ETERNA creada correctamente"


# -----------------------
# HOME
# -----------------------
@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
    <body style="background:black;color:white;font-family:Arial;padding:40px;">
        <h1>ETERNA</h1>

        <form action="/crear-eterna" method="post" enctype="multipart/form-data">
            <input name="customer_name" placeholder="Tu nombre" required><br><br>
            <input type="email" name="customer_email" placeholder="Tu email" required><br><br>

            <input name="recipient_name" placeholder="Nombre destinatario" required><br><br>

            <textarea name="phrase1" placeholder="Frase 1" required></textarea><br><br>
            <textarea name="phrase2" placeholder="Frase 2" required></textarea><br><br>
            <textarea name="phrase3" placeholder="Frase 3" required></textarea><br><br>

            <input type="file" name="photos" multiple required><br><br>

            <button>Crear ETERNA</button>
        </form>
    </body>
    </html>
    """


# -----------------------
# CREAR ETERNA
# -----------------------
@app.post("/crear-eterna", response_model=EternaCreationResponse)
async def crear_eterna(
    request: Request,
    customer_name: str = Form(...),
    customer_email: str = Form(...),
    recipient_name: str = Form(...),
    phrase1: str = Form(...),
    phrase2: str = Form(...),
    phrase3: str = Form(...),
    photos: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    if len(photos) != 6:
        raise HTTPException(status_code=400, detail="Debes subir 6 fotos")

    eterna_id = str(uuid.uuid4())
    share_token = str(uuid.uuid4())

    folder = storage.create_eterna_folder(eterna_id)

    saved_images = await storage.save_uploaded_images(folder, photos)

    customer = Customer(name=customer_name, email=customer_email)
    db.add(customer)
    db.commit()
    db.refresh(customer)

    recipient = Recipient(name=recipient_name)
    db.add(recipient)
    db.commit()
    db.refresh(recipient)

    base_url = str(request.base_url).rstrip("/")
    share_url = f"{base_url}/e/{share_token}"

    order = EternaOrder(
        eterna_id=eterna_id,
        customer_id=customer.id,
        recipient_id=recipient.id,
        phrase1=phrase1,
        phrase2=phrase2,
        phrase3=phrase3,
        image_count=len(saved_images),
        storage_folder=str(folder),
        share_token=share_token,
        share_url=share_url,
        status="created",
    )

    db.add(order)
    db.commit()

    return {
        "ok": True,
        "eterna_id": eterna_id,
        "share_url": share_url,
        "message": "ETERNA creada correctamente"
    }


# -----------------------
# VER ETERNA
# -----------------------
@app.get("/e/{token}", response_class=HTMLResponse)
def ver_eterna(token: str, db: Session = Depends(get_db)):

    order = db.query(EternaOrder).filter(EternaOrder.share_token == token).first()

    if not order:
        return HTMLResponse("<h1>No encontrada</h1>")

    if not order.opened_at:
        order.opened_at = datetime.utcnow()
        order.status = "opened"
        db.commit()

    folder = Path(order.storage_folder).name

    images_html = ""
    for i in range(1, order.image_count + 1):
        images_html += f'<img src="/media/{folder}/foto_{i}.jpg" style="width:100%;margin-bottom:20px;">'

    reaction_block = f"""
    <form id="reactionForm">
        <input type="file" name="video" accept="video/*" required>
        <button>Subir reacción</button>
    </form>
    <p id="msg"></p>
    """

    return f"""
    <html>
    <body style="background:black;color:white;font-family:Arial;padding:20px;">
        <h2>{order.phrase1}</h2>
        <h3>{order.phrase2}</h3>
        <h4>{order.phrase3}</h4>

        {images_html}

        {reaction_block}

        <script>
        const form = document.getElementById("reactionForm");
        const msg = document.getElementById("msg");

        form.onsubmit = async (e) => {{
            e.preventDefault();

            const data = new FormData(form);

            const res = await fetch("/reaccion/{order.eterna_id}", {{
                method: "POST",
                body: data
            }});

            const json = await res.json();

            msg.innerText = json.message || "Subido";
        }}
        </script>
    </body>
    </html>
    """


# -----------------------
# SUBIR REACCIÓN
# -----------------------
@app.post("/reaccion/{eterna_id}")
async def subir_reaccion(
    eterna_id: str,
    video: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    order = db.query(EternaOrder).filter(EternaOrder.eterna_id == eterna_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="No encontrada")

    folder = Path(order.storage_folder)

    ext = Path(video.filename).suffix or ".mp4"
    path = folder / f"reaction{ext}"

    content = await video.read()

    with open(path, "wb") as f:
        f.write(content)

    order.status = "reaction_uploaded"
    db.commit()

    return {"ok": True, "message": "Reacción subida"}
