import json
import os
import shutil
import uuid
import urllib.parse
from pathlib import Path
from typing import List

import stripe
from fastapi import FastAPI, Form, Request, HTTPException, Depends, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import EternaOrder

app = FastAPI(title="ETERNA backend")

# =========================
# CONFIG
# =========================

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
PUBLIC_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
STORAGE_PRIVATE = os.getenv("STORAGE_PRIVATE", "./private_vault")

if not STRIPE_SECRET_KEY:
    print("❌ Falta STRIPE_SECRET_KEY")

if not STRIPE_WEBHOOK_SECRET:
    print("❌ Falta STRIPE_WEBHOOK_SECRET")

if not PUBLIC_URL:
    print("❌ Falta PUBLIC_BASE_URL")

stripe.api_key = STRIPE_SECRET_KEY

Base.metadata.create_all(bind=engine)

# carpetas
PRIVATE_ROOT = Path(STORAGE_PRIVATE)
PRIVATE_ROOT.mkdir(parents=True, exist_ok=True)

MEDIA_ROOT = Path("./media")
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

app.mount("/media", StaticFiles(directory=str(MEDIA_ROOT)), name="media")

# =========================
# HELPERS
# =========================

def secure_filename(filename: str) -> str:
    filename = filename or "file"
    filename = Path(filename).name
    filename = filename.replace(" ", "_")
    return filename


def save_uploaded_photos(order_id: str, photos: List[UploadFile]) -> List[str]:
    saved_paths = []

    order_private_dir = PRIVATE_ROOT / order_id
    order_private_dir.mkdir(parents=True, exist_ok=True)

    for index, photo in enumerate(photos, start=1):
        original_name = secure_filename(photo.filename)
        ext = Path(original_name).suffix.lower() or ".jpg"
        final_name = f"photo_{index}{ext}"
        final_path = order_private_dir / final_name

        with final_path.open("wb") as buffer:
            shutil.copyfileobj(photo.file, buffer)

        saved_paths.append(str(final_path))

    return saved_paths


# =========================
# HOME
# =========================

@app.get("/")
def home():
    return {"status": "ETERNA funcionando"}

# =========================
# CREAR ETERNA
# =========================

@app.post("/crear-eterna")
async def crear_eterna(
    customer_name: str = Form(...),
    customer_email: str = Form(...),
    recipient_name: str = Form(...),
    recipient_phone
