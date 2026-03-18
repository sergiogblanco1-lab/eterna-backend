import uuid
import urllib.parse
from pathlib import Path
from typing import List, Optional
import os
import stripe

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Customer, Recipient, EternaOrder
from storage_service import StorageService


stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

app = FastAPI()

Base.metadata.create_all(bind=engine)

storage = StorageService()

app.mount("/media", StaticFiles(directory=str(storage.media_dir)), name="media")


# =========================
# HOME
# =========================

@app.get("/", response_class=HTMLResponse)
def home():
    return "<h1>ETERNA OK</h1>"


# =========================
# CREAR
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
    db: Session = Depends(get_db),
):

    if len(photos) != 6:
        raise HTTPException(400)

    eterna_id = str(uuid.uuid4())
    token = str(uuid.uuid4())

    folder = storage.create_eterna_folder(eterna_id)
    await storage.save_uploaded_images(folder, photos)

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
# VER
# =========================

@app.get("/e/{token}", response_class=HTMLResponse)
def ver(token: str, db: Session = Depends(get_db)):

    order = db.query(EternaOrder).filter(EternaOrder.share_token == token).first()

    if not order:
        raise HTTPException(404)

    return f"<h1>{order.phrase1}</h1><p>{order.phrase2}</p><p>{order.phrase3}</p>"
