from __future__ import annotations

import os
import io
import re
import hmac
import html
import json
import time
import math
import shutil
import queue
import smtplib
import secrets
import hashlib
import logging
import traceback
import threading
import multiprocessing as mp
from pathlib import Path
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
from collections import defaultdict, deque
from email.message import EmailMessage
from typing import Optional, Dict, Any, List, Tuple

import numpy as np
import stripe
from PIL import Image, ImageOps

from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
    Query,
    UploadFile,
    File,
    Form,
    Header,
    Request,
    status,
)
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

from sqlalchemy import (
    create_engine,
    String,
    DateTime,
    Text,
    Integer,
    Boolean,
    Float,
    select,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session

try:
    import redis
except Exception:
    redis = None

try:
    from rq import Queue
except Exception:
    Queue = None


# ============================================================
# CONFIG
# ============================================================

class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    app_name: str = "ETERNA V8 LAB"
    debug: bool = True

    database_url: str = "sqlite:///./eterna_v8_lab.db"
    storage_private: str = "./private_vault"
    eterna_audio_path: str = "./assets/piano_base.mp3"
    eterna_font_path: str = "./assets/DejaVuSans-Bold.ttf"
    public_base_url: str = "http://127.0.0.1:8000"
    admin_token: str = "cambia_este_token_admin"

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_currency: str = "eur"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True

    redis_url: str = ""

    video_width: int = 1080
    video_height: int = 1920
    video_fps: int = 24
    eterna_core_seconds: int = 30
    regalante_max_seconds: int = 30

    max_fotos: int = 6
    max_frases: int = 3
    max_image_mb: int = 15
    max_video_regalante_mb: int = 250
    max_reaction_mb: int = 300

    max_requests_per_minute: int = 20
    max_pending_per_ip: int = 3

    render_timeout_seconds: int = 420
    cleanup_interval_seconds: int = 900

    link_expiry_hours: int = 0
    default_max_views: int = 0
    max_views_hard_cap: int = 50

    min_pin_length: int = 4
    max_pin_length: int = 12

    # negocio
    eterna_base_cents: int = 2900
    extra_video_regalante_cents: int = 700
    extra_reaccion_cents: int = 700
    gift_fee_percent: float = 0.05


settings = Settings()

BASE_DIR = Path(settings.storage_private)
INPUTS_DIR = BASE_DIR / "inputs"
RENDERS_DIR = BASE_DIR / "renders"
REACTIONS_DIR = BASE_DIR / "reactions"

for p in [BASE_DIR, INPUTS_DIR, RENDERS_DIR, REACTIONS_DIR]:
    p.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("eterna-v8-lab")

if settings.stripe_secret_key:
    stripe.api_key = settings.stripe_secret_key


# ============================================================
# REDIS / RQ OPCIONALES
# ============================================================

redis_conn = None
rq_queue = None

if settings.redis_url and redis and Queue:
    try:
        redis_conn = redis.from_url(settings.redis_url)
        redis_conn.ping()
        rq_queue = Queue(
            "eterna-renders",
            connection=redis_conn,
            default_timeout=settings.render_timeout_seconds + 60,
        )
        logger.info("Redis + RQ activos.")
    except Exception as exc:
        logger.warning("Redis/RQ no disponible, usando fallback local: %s", exc)
        redis_conn = None
        rq_queue = None
else:
    logger.info("Redis/RQ no configurado, usando fallback local.")


# ============================================================
# DATABASE
# ============================================================

class Base(DeclarativeBase):
    pass


class PedidoEterna(Base):
    __tablename__ = "pedidos_eterna"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: secrets.token_hex(18))
    access_token: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)

    fotos_csv: Mapped[str] = mapped_column(Text, nullable=False, default="")
    frases_csv: Mapped[str] = mapped_column(Text, nullable=False, default="")

    nombre_destinatario: Mapped[str] = mapped_column(String(255), nullable=False)
    nombre_remitente: Mapped[str] = mapped_column(String(255), nullable=False, default="Alguien que te quiere")
    buyer_email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    buyer_phone: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    requester_ip: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")

    link_pin_hash: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    max_views: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    payment_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending_payment")
    stripe_checkout_session_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    stripe_payment_intent_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # draft -> checkout_created -> paid -> queued -> rendering -> completed -> delivered
    # failed / revoked / expired
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    archivo_video_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    archivo_video_regalante_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    archivo_reaccion_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    render_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    render_finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reaction_uploaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    views_count: Mapped[int] = mapped_column(Integer, default=0)
    access_revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # flags producto
    incluye_video_regalante: Mapped[bool] = mapped_column(Boolean, default=False)
    incluye_reaccion: Mapped[bool] = mapped_column(Boolean, default=False)
    permite_compartir_regalante: Mapped[bool] = mapped_column(Boolean, default=True)
    permite_compartir_destinatario: Mapped[bool] = mapped_column(Boolean, default=True)

    # permiso reacción destinatario
    acepto_grabar_reaccion: Mapped[bool] = mapped_column(Boolean, default=False)
    permiso_publicar_reaccion: Mapped[bool] = mapped_column(Boolean, default=False)

    # regalo económico
    regalo_activo: Mapped[bool] = mapped_column(Boolean, default=False)
    regalo_amount_eur: Mapped[float] = mapped_column(Float, default=0.0)
    regalo_fee_eur: Mapped[float] = mapped_column(Float, default=0.0)
    regalo_total_cobrado_eur: Mapped[float] = mapped_column(Float, default=0.0)
    regalo_mensaje: Mapped[str] = mapped_column(Text, default="")

    # precios
    precio_base_eur: Mapped[float] = mapped_column(Float, default=0.0)
    extra_video_eur: Mapped[float] = mapped_column(Float, default=0.0)
    extra_reaccion_eur: Mapped[float] = mapped_column(Float, default=0.0)
    total_producto_eur: Mapped[float] = mapped_column(Float, default=0.0)
    total_checkout_eur: Mapped[float] = mapped_column(Float, default=0.0)

    email_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )


class StripeEvent(Base):
    __tablename__ = "stripe_events"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )


engine = create_engine(
    settings.database_url,
    future=True,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    logger.info("Base de datos inicializada.")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================
# ADMIN
# ============================================================

def require_admin(x_admin_token: Optional[str] = Header(default=None)):
    if not x_admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Admin no autorizado.")
    return True


# ============================================================
# RATE LIMIT
# ============================================================

rate_limit_lock = threading.Lock()
requests_by_ip: Dict[str, deque] = defaultdict(deque)


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def enforce_rate_limit(ip: str) -> None:
    if redis_conn:
        key = f"rl:{ip}:{int(time.time() // 60)}"
        try:
            current = redis_conn.incr(key)
            if current == 1:
                redis_conn.expire(key, 70)
            if current > settings.max_requests_per_minute:
                raise HTTPException(status_code=429, detail="Demasiadas solicitudes. Inténtalo más tarde.")
            return
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("Fallo rate-limit Redis, usando fallback local: %s", exc)

    now = time.time()
    with rate_limit_lock:
        dq = requests_by_ip[ip]
        while dq and now - dq[0] > 60:
            dq.popleft()
        if len(dq) >= settings.max_requests_per_minute:
            raise HTTPException(status_code=429, detail="Demasiadas solicitudes. Inténtalo más tarde.")
        dq.append(now)


def count_pending_jobs_for_ip(db: Session, ip: str) -> int:
    return db.execute(
        select(func.count()).select_from(PedidoEterna).where(
            PedidoEterna.requester_ip == ip,
            PedidoEterna.status.in_(["paid", "queued", "rendering"])
        )
    ).scalar_one()


# ============================================================
# HELPERS
# ============================================================

SAFE_TEXT_RE = re.compile(r"[^\w\s\-\.,:;!?@áéíóúÁÉÍÓÚñÑüÜ()#&+/€]", re.UNICODE)


def utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def csv_join(items: List[str]) -> str:
    return "|||".join(items)


def csv_split(value: str) -> List[str]:
    if not value:
        return []
    return [x for x in value.split("|||") if x]


def ensure_assets() -> None:
    if not os.path.exists(settings.eterna_audio_path):
        raise RuntimeError(f"No existe el audio base: {settings.eterna_audio_path}")
    if not os.path.exists(settings.eterna_font_path):
        raise RuntimeError(f"No existe la fuente: {settings.eterna_font_path}")


def generate_access_token() -> str:
    return secrets.token_urlsafe(32)


def build_delivery_url(token: str) -> str:
    return f"{settings.public_base_url}/entrega?token={token}"


def build_video_url(token: str) -> str:
    return f"{settings.public_base_url}/video-file?token={token}"


def build_status_url(pedido_id: str) -> str:
    return f"{settings.public_base_url}/estado/{pedido_id}"


def build_success_url(pedido_id: str) -> str:
    return f"{settings.public_base_url}/checkout/success?pedido_id={pedido_id}"


def build_cancel_url(pedido_id: str) -> str:
    return f"{settings.public_base_url}/checkout/cancel?pedido_id={pedido_id}"


def delete_path_safely(path: Optional[str]) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception as exc:
        logger.warning("No se pudo borrar archivo %s: %s", path, exc)


def delete_dir_safely(path: Optional[str]) -> None:
    try:
        if path and os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)
    except Exception as exc:
        logger.warning("No se pudo borrar carpeta %s: %s", path, exc)


def delete_job_inputs(job_id: str) -> None:
    delete_dir_safely(str(INPUTS_DIR / job_id))


def is_expired(pedido: PedidoEterna) -> bool:
    return bool(pedido.expires_at and pedido.expires_at <= utcnow_naive())


def sanitize_display_text(value: str, max_len: int = 255) -> str:
    value = (value or "").strip().replace("\x00", "")
    value = SAFE_TEXT_RE.sub("", value)
    return value[:max_len]


def validate_text_fields(frases: List[str], nombre_destinatario: str, nombre_remitente: str) -> None:
    if len(frases) != settings.max_frases:
        raise ValueError(f"Debes enviar exactamente {settings.max_frases} frases.")
    for frase in frases:
        frase = sanitize_display_text(frase, 180)
        if len(frase) < 2:
            raise ValueError("Las frases deben tener contenido.")
        if len(frase) > 180:
            raise ValueError("Cada frase debe tener máximo 180 caracteres.")
    if not sanitize_display_text(nombre_destinatario):
        raise ValueError("El nombre del destinatario es obligatorio.")
    if not sanitize_display_text(nombre_remitente):
        raise ValueError("El nombre del remitente es obligatorio.")


def validate_optional_pin(pin: str) -> str:
    pin = pin.strip()
    if not pin:
        return ""
    if not pin.isdigit():
        raise ValueError("El PIN debe contener solo números.")
    if len(pin) < settings.min_pin_length or len(pin) > settings.max_pin_length:
        raise ValueError(
            f"El PIN debe tener entre {settings.min_pin_length} y {settings.max_pin_length} dígitos."
        )
    return pin


def hash_pin(pin: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, 200_000)
    return f"pbkdf2_sha256${salt.hex()}${dk.hex()}"


def verify_pin(pin: Optional[str], stored_hash: Optional[str]) -> bool:
    if not stored_hash:
        return True
    if not pin:
        return False
    try:
        algorithm, salt_hex, hash_hex = stored_hash.split("$", 2)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        candidate = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, 200_000)
        return hmac.compare_digest(candidate, expected)
    except Exception:
        return False


def validate_optional_max_views(max_views: int) -> int:
    if max_views < 0:
        raise ValueError("max_views no puede ser negativo.")
    if max_views > settings.max_views_hard_cap:
        raise ValueError(f"max_views no puede superar {settings.max_views_hard_cap}.")
    return max_views


def apply_access_checks(pedido: PedidoEterna, pin: Optional[str] = None) -> None:
    if pedido.access_revoked_at is not None:
        raise HTTPException(status_code=404, detail="Acceso revocado.")
    if is_expired(pedido):
        raise HTTPException(status_code=404, detail="Enlace expirado.")
    if pedido.max_views > 0 and pedido.views_count >= pedido.max_views:
        raise HTTPException(status_code=404, detail="Límite de visualizaciones alcanzado.")
    if not verify_pin(pin, pedido.link_pin_hash):
        raise HTTPException(status_code=401, detail="PIN incorrecto o no enviado.")


def get_pedido_by_token(db: Session, token: str, pin: Optional[str] = None) -> PedidoEterna:
    pedido = db.execute(
        select(PedidoEterna).where(PedidoEterna.access_token == token)
    ).scalar_one_or_none()

    if not pedido:
        raise HTTPException(status_code=404, detail="Enlace no válido.")

    apply_access_checks(pedido, pin)
    return pedido


def euros_to_cents(value: float) -> int:
    return int(round(value * 100))


def cents_to_euros(value: int) -> float:
    return round(value / 100, 2)


def compute_pricing(
    incluye_video_regalante: bool,
    incluye_reaccion: bool,
    regalo_amount_eur: float,
) -> Dict[str, float]:
    base = cents_to_euros(settings.eterna_base_cents)
    extra_video = cents_to_euros(settings.extra_video_regalante_cents) if incluye_video_regalante else 0.0
    extra_reaccion = cents_to_euros(settings.extra_reaccion_cents) if incluye_reaccion else 0.0
    regalo_fee = round(max(regalo_amount_eur, 0.0) * settings.gift_fee_percent, 2)
    regalo_total_cobrado = round(max(regalo_amount_eur, 0.0) + regalo_fee, 2)
    total_producto = round(base + extra_video + extra_reaccion, 2)
    total_checkout = round(total_producto + regalo_total_cobrado, 2)
    return {
        "base": base,
        "extra_video": extra_video,
        "extra_reaccion": extra_reaccion,
        "regalo_fee": regalo_fee,
        "regalo_total_cobrado": regalo_total_cobrado,
        "total_producto": total_producto,
        "total_checkout": total_checkout,
    }


async def save_uploaded_images_for_job(job_id: str, fotos: List[UploadFile]) -> List[str]:
    if len(fotos) != settings.max_fotos:
        raise ValueError(f"Debes subir exactamente {settings.max_fotos} fotos.")

    valid_ext = {".jpg", ".jpeg", ".png", ".webp"}
    valid_types = {"image/jpeg", "image/png", "image/webp"}
    max_bytes = settings.max_image_mb * 1024 * 1024

    job_input_dir = INPUTS_DIR / job_id
    job_input_dir.mkdir(parents=True, exist_ok=True)

    saved_paths: List[str] = []

    for idx, foto in enumerate(fotos, start=1):
        original_name = Path(foto.filename or f"foto_{idx}.jpg").name
        ext = Path(original_name).suffix.lower()

        if ext not in valid_ext:
            raise ValueError(f"Formato no permitido en {original_name}. Usa jpg, jpeg, png o webp.")
        if foto.content_type and foto.content_type not in valid_types:
            raise ValueError(f"Tipo MIME no permitido en {original_name}.")

        content = await foto.read()
        if not content:
            raise ValueError(f"La imagen {original_name} está vacía.")
        if len(content) > max_bytes:
            raise ValueError(f"La imagen {original_name} supera {settings.max_image_mb}MB.")

        dst = job_input_dir / f"foto_{idx}{ext}"
        with open(dst, "wb") as f:
            f.write(content)
        saved_paths.append(str(dst))

    return saved_paths


async def save_video_regalante_for_job(job_id: str, video_regalante: Optional[UploadFile]) -> Optional[str]:
    if not video_regalante or not getattr(video_regalante, "filename", None):
        return None

    valid_ext = {".mp4", ".mov", ".webm", ".m4v"}
    max_bytes = settings.max_video_regalante_mb * 1024 * 1024

    original_name = Path(video_regalante.filename or "video_regalante.mp4").name
    ext = Path(original_name).suffix.lower()
    if ext not in valid_ext:
        raise ValueError("El vídeo del regalante debe ser mp4, mov, webm o m4v.")

    content = await video_regalante.read()
    if not content:
        raise ValueError("El vídeo del regalante está vacío.")
    if len(content) > max_bytes:
        raise ValueError(f"El vídeo del regalante supera {settings.max_video_regalante_mb}MB.")

    job_input_dir = INPUTS_DIR / job_id
    job_input_dir.mkdir(parents=True, exist_ok=True)

    dst = job_input_dir / f"video_regalante{ext}"
    with open(dst, "wb") as f:
        f.write(content)

    return str(dst)


# ============================================================
# EMAIL
# ============================================================

def send_email_real(to_email: str, subject: str, body_text: str) -> bool:
    if not all([settings.smtp_host, settings.smtp_username, settings.smtp_password, settings.smtp_from_email]):
        logger.info("SMTP no configurado; email omitido.")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_email
    msg["To"] = to_email
    msg.set_content(body_text)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(msg)
        return True
    except Exception as exc:
        logger.warning("No se pudo enviar email a %s: %s", to_email, exc)
        return False


def notify_buyer_paid_and_processing(pedido: PedidoEterna) -> None:
    if pedido.buyer_email:
        send_email_real(
            pedido.buyer_email,
            "ETERNA: pago recibido",
            f"Tu pedido {pedido.id} ya está pagado y ha entrado en cola para prepararse.",
        )


def notify_buyer_ready(pedido: PedidoEterna) -> None:
    delivery_url = build_delivery_url(pedido.access_token)
    body = (
        f"Tu ETERNA ya está lista.\n\n"
        f"Entrega privada:\n{delivery_url}\n\n"
        f"Compártela cuando quieras con quien corresponda."
    )
    if pedido.buyer_email:
        ok = send_email_real(pedido.buyer_email, "Tu ETERNA ya está lista", body)
        if ok:
            pedido.email_sent_at = utcnow_naive()


# ============================================================
# STRIPE
# ============================================================

def create_stripe_checkout_session(pedido: PedidoEterna) -> Tuple[str, str]:
    if not settings.stripe_secret_key:
        raise RuntimeError("Stripe no está configurado.")

    line_items = [
        {
            "price_data": {
                "currency": settings.stripe_currency,
                "product_data": {
                    "name": "ETERNA",
                    "description": "Recuerdo emocional personalizado",
                },
                "unit_amount": euros_to_cents(pedido.precio_base_eur),
            },
            "quantity": 1,
        }
    ]

    if pedido.extra_video_eur > 0:
        line_items.append(
            {
                "price_data": {
                    "currency": settings.stripe_currency,
                    "product_data": {
                        "name": "Vídeo del regalante",
                        "description": "Mensaje final personal dentro de ETERNA",
                    },
                    "unit_amount": euros_to_cents(pedido.extra_video_eur),
                },
                "quantity": 1,
            }
        )

    if pedido.extra_reaccion_eur > 0:
        line_items.append(
            {
                "price_data": {
                    "currency": settings.stripe_currency,
                    "product_data": {
                        "name": "Reacción guardada",
                        "description": "Guardar la reacción sorpresa del destinatario",
                    },
                    "unit_amount": euros_to_cents(pedido.extra_reaccion_eur),
                },
                "quantity": 1,
            }
        )

    if pedido.regalo_activo and pedido.regalo_amount_eur > 0:
        line_items.append(
            {
                "price_data": {
                    "currency": settings.stripe_currency,
                    "product_data": {
                        "name": "Regalo económico",
                        "description": "El destinatario recibe el 100% de este importe",
                    },
                    "unit_amount": euros_to_cents(pedido.regalo_amount_eur),
                },
                "quantity": 1,
            }
        )
        line_items.append(
            {
                "price_data": {
                    "currency": settings.stripe_currency,
                    "product_data": {
                        "name": "Servicio de envío del regalo",
                        "description": "5% cobrado al regalante sobre el regalo económico",
                    },
                    "unit_amount": euros_to_cents(pedido.regalo_fee_eur),
                },
                "quantity": 1,
            }
        )

    session = stripe.checkout.Session.create(
        mode="payment",
        success_url=build_success_url(pedido.id),
        cancel_url=build_cancel_url(pedido.id),
        customer_email=pedido.buyer_email or None,
        line_items=line_items,
        metadata={
            "pedido_id": pedido.id,
        },
    )
    return session.url, session.id


# ============================================================
# RENDER EN PROCESO SEPARADO
# ============================================================

def render_process_entry(payload: Dict[str, Any], result_queue: mp.Queue) -> None:
    try:
        from moviepy import (
            AudioFileClip,
            CompositeVideoClip,
            ImageClip,
            VideoFileClip,
            TextClip,
            ColorClip,
            concatenate_videoclips,
        )

        width = payload["video_width"]
        height = payload["video_height"]
        fps = payload["video_fps"]

        fotos_paths = payload["fotos_paths"]
        frases = payload["frases"]
        ruta_audio = payload["ruta_audio"]
        font_path = payload["font_path"]
        job_id = payload["job_id"]
        nombre_destinatario = payload["nombre_destinatario"]
        nombre_remitente = payload["nombre_remitente"]
        renders_dir = payload["renders_dir"]
        regalo_activo = payload["regalo_activo"]
        regalo_amount_eur = payload["regalo_amount_eur"]
        regalo_mensaje = payload["regalo_mensaje"]
        video_regalante_path = payload["video_regalante_path"]
        eterna_core_seconds = payload["eterna_core_seconds"]
        regalante_max_seconds = payload["regalante_max_seconds"]

        if not os.path.exists(ruta_audio):
            raise RuntimeError(f"No existe el audio base: {ruta_audio}")
        if not os.path.exists(font_path):
            raise RuntimeError(f"No existe la fuente: {font_path}")
        for p in fotos_paths:
            if not os.path.exists(p):
                raise RuntimeError(f"No existe imagen para render: {p}")

        def normalize_image(path: str) -> np.ndarray:
            with Image.open(path) as img:
                img = ImageOps.exif_transpose(img).convert("RGB")
                src_w, src_h = img.size
                target_ratio = width / height
                src_ratio = src_w / src_h

                if src_ratio > target_ratio:
                    new_h = src_h
                    new_w = int(new_h * target_ratio)
                    left = (src_w - new_w) // 2
                    img = img.crop((left, 0, left + new_w, src_h))
                else:
                    new_w = src_w
                    new_h = int(new_w / target_ratio)
                    top = (src_h - new_h) // 2
                    img = img.crop((0, top, src_w, top + new_h))

                img = img.resize((width, height), Image.LANCZOS)
                return np.array(img)

        def blend_gray_progress(frame: np.ndarray, progress: float) -> np.ndarray:
            gray = np.dot(frame[..., :3], [0.299, 0.587, 0.114])
            gray_rgb = np.stack([gray, gray, gray], axis=-1)
            alpha = max(0.0, min(1.0, progress))
            out = gray_rgb * (1.0 - alpha) + frame * alpha
            return np.clip(out, 0, 255).astype(np.uint8)

        def make_ken_burns_clip(img_path: str, duration: float, scene_start: float, total_core: float):
            base_frame = normalize_image(img_path)

            def frame_func(t):
                p = min(max(t / max(duration, 0.001), 0.0), 1.0)
                zoom = 1.0 + 0.08 * p

                src_h, src_w = base_frame.shape[:2]
                crop_w = max(1, int(src_w / zoom))
                crop_h = max(1, int(src_h / zoom))

                x1 = max(0, int((src_w - crop_w) / 2))
                y1 = max(0, int((src_h - crop_h) / 2))
                cropped = base_frame[y1:y1 + crop_h, x1:x1 + crop_w]

                img = Image.fromarray(cropped).resize((width, height), Image.LANCZOS)
                frame = np.array(img)

                overall_progress = min(max((scene_start + t) / max(total_core, 0.001), 0.0), 1.0)
                color_progress = 0.0 if overall_progress < 0.35 else (overall_progress - 0.35) / 0.45
                color_progress = min(max(color_progress, 0.0), 1.0)
                return blend_gray_progress(frame, color_progress)

            clip = ImageClip(base_frame).with_duration(duration)
            return clip.with_updated_frame_function(frame_func).with_duration(duration)

        def make_text_overlay(text: str, duration: float):
            return (
                TextClip(
                    text=text,
                    font=font_path,
                    font_size=58,
                    color="white",
                    method="caption",
                    size=(int(width * 0.82), None),
                    text_align="center",
                )
                .with_duration(duration)
                .with_position(("center", int(height * 0.80)))
            )

        def make_black_text_scene(text: str, duration: float, font_size: int = 62):
            bg = ColorClip(size=(width, height), color=(0, 0, 0)).with_duration(duration)
            txt = (
                TextClip(
                    text=text,
                    font=font_path,
                    font_size=font_size,
                    color="white",
                    method="caption",
                    size=(int(width * 0.82), None),
                    text_align="center",
                )
                .with_duration(duration)
                .with_position(("center", "center"))
            )
            return CompositeVideoClip([bg, txt], size=(width, height)).with_duration(duration)

        clips = []

        intro = make_black_text_scene("Hay momentos que merecen quedarse para siempre", 3.0, font_size=60)
        clips.append(intro)

        photos_total = max(12.0, eterna_core_seconds - 10.0)
        duration_per_photo = photos_total / len(fotos_paths)
        photo_scene_start = 3.0

        for i, img_path in enumerate(fotos_paths):
            kb = make_ken_burns_clip(
                img_path=img_path,
                duration=duration_per_photo,
                scene_start=photo_scene_start + i * duration_per_photo,
                total_core=eterna_core_seconds,
            )
            overlays = [kb]
            if i < len(frases):
                text_dur = min(4.2, max(3.0, duration_per_photo - 0.5))
                overlays.append(make_text_overlay(frases[i], text_dur).with_start(max(0.3, duration_per_photo * 0.2)))
            scene = CompositeVideoClip(overlays, size=(width, height)).with_duration(duration_per_photo)
            clips.append(scene)

        reveal = make_black_text_scene("Este momento es para ti", 2.4, font_size=64)
        clips.append(reveal)

        if regalo_activo and regalo_amount_eur > 0:
            regalo_text = f"Y además...\n{regalo_amount_eur:.2f}€ para ti"
            if regalo_mensaje:
                regalo_text += f"\n\n{regalo_mensaje}"
            regalo_scene = make_black_text_scene(regalo_text, 3.2, font_size=58)
            clips.append(regalo_scene)
        else:
            eterna_scene = make_black_text_scene("Te han regalado una ETERNA", 2.6, font_size=62)
            clips.append(eterna_scene)

        final_name = make_black_text_scene(
            f"Para {nombre_destinatario}\n\nCon cariño, {nombre_remitente}",
            2.8,
            font_size=56,
        )
        clips.append(final_name)

        output_dir = Path(renders_dir) / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"eterna_{job_id}.mp4"

        core_video = None
        full_video = None
        audio = None
        regalante_clip = None

        try:
            core_video = concatenate_videoclips(clips, method="compose")

            if os.path.exists(ruta_audio):
                audio = AudioFileClip(ruta_audio)
                if audio.duration > core_video.duration:
                    audio = audio.subclipped(0, core_video.duration)
                else:
                    audio = audio.with_duration(core_video.duration)
                core_video = core_video.with_audio(audio)

            if video_regalante_path and os.path.exists(video_regalante_path):
                regalante_clip = VideoFileClip(video_regalante_path)
                regalante_clip = regalante_clip.resized(height=height)
                if regalante_clip.w < width:
                    regalante_clip = regalante_clip.resized(width=width)
                x1 = max(0, int((regalante_clip.w - width) / 2))
                y1 = max(0, int((regalante_clip.h - height) / 2))
                regalante_clip = regalante_clip.cropped(x1=x1, y1=y1, x2=x1 + width, y2=y1 + height)
                regalante_clip = regalante_clip.subclipped(0, min(regalante_clip.duration, regalante_max_seconds))

                full_video = concatenate_videoclips([core_video, regalante_clip], method="compose")
            else:
                full_video = core_video

            full_video.write_videofile(
                str(output_file),
                fps=fps,
                codec="libx264",
                audio_codec="aac",
                preset="medium",
                threads=4,
                logger=None,
            )
        finally:
            try:
                if regalante_clip:
                    regalante_clip.close()
            except Exception:
                pass
            try:
                if audio:
                    audio.close()
            except Exception:
                pass
            try:
                if core_video:
                    core_video.close()
            except Exception:
                pass
            try:
                if full_video and full_video is not core_video:
                    full_video.close()
            except Exception:
                pass
            for c in clips:
                try:
                    c.close()
                except Exception:
                    pass

        if not output_file.exists():
            raise RuntimeError("El render terminó sin generar archivo final.")
        if output_file.stat().st_size < 1024:
            raise RuntimeError("El vídeo generado es demasiado pequeño o inválido.")

        result_queue.put({"ok": True, "output_path": str(output_file)})
    except Exception as exc:
        result_queue.put({"ok": False, "error": str(exc), "traceback": traceback.format_exc()})


def run_render_with_timeout(
    pedido: PedidoEterna,
    fotos_paths: List[str],
    frases: List[str],
) -> str:
    payload = {
        "job_id": pedido.id,
        "fotos_paths": fotos_paths,
        "frases": frases,
        "nombre_destinatario": pedido.nombre_destinatario,
        "nombre_remitente": pedido.nombre_remitente,
        "ruta_audio": settings.eterna_audio_path,
        "font_path": settings.eterna_font_path,
        "renders_dir": str(RENDERS_DIR),
        "video_width": settings.video_width,
        "video_height": settings.video_height,
        "video_fps": settings.video_fps,
        "eterna_core_seconds": settings.eterna_core_seconds,
        "regalante_max_seconds": settings.regalante_max_seconds,
        "regalo_activo": pedido.regalo_activo,
        "regalo_amount_eur": pedido.regalo_amount_eur,
        "regalo_mensaje": pedido.regalo_mensaje,
        "video_regalante_path": pedido.archivo_video_regalante_path,
    }

    result_queue: mp.Queue = mp.Queue()
    proc = mp.Process(target=render_process_entry, args=(payload, result_queue), daemon=True)
    proc.start()
    proc.join(settings.render_timeout_seconds)

    if proc.is_alive():
        proc.terminate()
        proc.join(timeout=5)
        raise RuntimeError("Timeout de render alcanzado.")

    if result_queue.empty():
        raise RuntimeError("El render terminó sin devolver resultado.")

    result = result_queue.get()
    if not result.get("ok"):
        logger.error(result.get("traceback", ""))
        raise RuntimeError(result.get("error", "Error desconocido de render."))

    output_path = result["output_path"]
    if not os.path.exists(output_path):
        raise RuntimeError("No existe el archivo renderizado.")
    if os.path.getsize(output_path) < 1024:
        raise RuntimeError("El archivo renderizado es inválido.")
    return output_path


# ============================================================
# COLA + WORKERS
# ============================================================

local_render_queue: "queue.Queue[str]" = queue.Queue()
worker_stop_event = threading.Event()
worker_thread: Optional[threading.Thread] = None
cleanup_thread: Optional[threading.Thread] = None


def process_render_job(job_id: str) -> None:
    db = SessionLocal()
    pedido: Optional[PedidoEterna] = None

    try:
        pedido = db.get(PedidoEterna, job_id)
        if not pedido:
            logger.warning("Pedido no encontrado: %s", job_id)
            return

        if pedido.payment_status != "paid":
            logger.info("Pedido no pagado; no se renderiza: %s", job_id)
            return

        if pedido.access_revoked_at is not None:
            logger.info("Pedido revocado, no se procesa: %s", job_id)
            return

        if is_expired(pedido):
            pedido.status = "expired"
            db.commit()
            return

        pedido.status = "rendering"
        pedido.render_started_at = utcnow_naive()
        pedido.error_message = None
        db.commit()
        db.refresh(pedido)

        fotos = csv_split(pedido.fotos_csv)
        frases = csv_split(pedido.frases_csv)

        ensure_assets()

        output_path = run_render_with_timeout(
            pedido=pedido,
            fotos_paths=fotos,
            frases=frases,
        )

        pedido = db.get(PedidoEterna, job_id)
        if not pedido:
            return

        pedido.archivo_video_path = output_path
        pedido.status = "completed"
        pedido.render_finished_at = utcnow_naive()

        notify_buyer_ready(pedido)
        db.commit()

    except Exception as exc:
        logger.error("Fallo render job %s: %s", job_id, exc)
        logger.error(traceback.format_exc())
        try:
            pedido = db.get(PedidoEterna, job_id)
            if pedido is not None:
                pedido.status = "failed"
                pedido.error_message = str(exc)
                pedido.render_finished_at = utcnow_naive()
                db.commit()
        except Exception:
            logger.error("No se pudo guardar el estado fallido del pedido %s", job_id)
    finally:
        db.close()


def enqueue_render(job_id: str) -> None:
    db = SessionLocal()
    try:
        pedido = db.get(PedidoEterna, job_id)
        if pedido:
            pedido.status = "queued"
            db.commit()
    finally:
        db.close()

    if rq_queue:
        rq_queue.enqueue(process_render_job, job_id)
    else:
        local_render_queue.put(job_id)


def local_worker_loop() -> None:
    logger.info("Worker local de render iniciado.")
    while not worker_stop_event.is_set():
        try:
            job_id = local_render_queue.get(timeout=1.0)
        except queue.Empty:
            continue
        try:
            process_render_job(job_id)
        finally:
            local_render_queue.task_done()
    logger.info("Worker local de render detenido.")


def cleanup_orphans_loop() -> None:
    logger.info("Limpieza de huérfanos iniciada.")
    while not worker_stop_event.is_set():
        try:
            db = SessionLocal()
            try:
                valid_render_dirs = set()
                valid_reaction_dirs = set()
                valid_input_dirs = set()

                pedidos = db.execute(select(PedidoEterna)).scalars().all()
                for p in pedidos:
                    valid_input_dirs.add(str(INPUTS_DIR / p.id))
                    if p.archivo_video_path:
                        valid_render_dirs.add(str(Path(p.archivo_video_path).parent))
                    if p.archivo_reaccion_path:
                        valid_reaction_dirs.add(str(Path(p.archivo_reaccion_path).parent))
                    if is_expired(p) and p.status not in ["revoked", "expired"]:
                        p.status = "expired"

                db.commit()

                for child in RENDERS_DIR.iterdir():
                    if child.is_dir() and str(child) not in valid_render_dirs:
                        delete_dir_safely(str(child))
                for child in REACTIONS_DIR.iterdir():
                    if child.is_dir() and str(child) not in valid_reaction_dirs:
                        delete_dir_safely(str(child))
            finally:
                db.close()
        except Exception as exc:
            logger.warning("Error en limpieza de huérfanos: %s", exc)

        worker_stop_event.wait(settings.cleanup_interval_seconds)
    logger.info("Limpieza de huérfanos detenida.")


# ============================================================
# RESPONSE MODELS
# ============================================================

class PedidoCrearOut(BaseModel):
    id: str
    status: str
    payment_status: str
    poll_url: str
    checkout_url: str
    preview_url: str
    total_checkout_eur: float


class PedidoEstadoOut(BaseModel):
    id: str
    status: str
    payment_status: str
    error_message: Optional[str]
    views_count: int
    max_views: int
    created_at: datetime
    render_started_at: Optional[datetime]
    render_finished_at: Optional[datetime]
    delivered_at: Optional[datetime]
    reaction_uploaded_at: Optional[datetime]
    expires_at: Optional[datetime]
    tiene_video: bool
    tiene_reaccion: bool
    url_entrega: str
    url_video: str
    incluye_video_regalante: bool
    incluye_reaccion: bool
    regalo_activo: bool
    regalo_amount_eur: float
    regalo_fee_eur: float
    total_checkout_eur: float


# ============================================================
# HTML
# ============================================================

def html_page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="es">
        <head>
            <meta charset="utf-8"/>
            <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>
            <title>{html.escape(title)}</title>
            <style>
                :root {{
                    --bg: #0b0b0b;
                    --card: rgba(255,255,255,0.04);
                    --line: rgba(255,255,255,0.10);
                    --text: #ffffff;
                    --muted: #cccccc;
                }}
                * {{ box-sizing: border-box; }}
                html, body {{
                    margin: 0;
                    padding: 0;
                    background:
                        radial-gradient(circle at top, rgba(255,255,255,0.05), transparent 22%),
                        linear-gradient(180deg, #000000 0%, #0b0b0b 100%);
                    color: var(--text);
                    font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif;
                }}
                .wrap {{
                    width: 100%;
                    max-width: 760px;
                    margin: 0 auto;
                    padding: 22px 16px 56px;
                }}
                .card {{
                    background: var(--card);
                    border: 1px solid var(--line);
                    border-radius: 24px;
                    padding: 22px;
                    box-shadow: 0 16px 50px rgba(0,0,0,.35);
                    backdrop-filter: blur(12px);
                }}
                .brand {{
                    font-size: 12px;
                    letter-spacing: .32em;
                    text-transform: uppercase;
                    color: #dddddd;
                    margin-bottom: 18px;
                }}
                h1 {{
                    font-size: 32px;
                    line-height: 1.06;
                    margin: 0 0 14px;
                    letter-spacing: -0.03em;
                    font-weight: 700;
                }}
                h2 {{
                    font-size: 22px;
                    margin: 28px 0 10px;
                }}
                p {{
                    color: var(--muted);
                    line-height: 1.65;
                    margin: 10px 0;
                }}
                .btn {{
                    display: inline-block;
                    width: 100%;
                    text-align: center;
                    padding: 16px 18px;
                    border-radius: 16px;
                    text-decoration: none;
                    font-weight: 700;
                    border: none;
                    cursor: pointer;
                    margin-top: 14px;
                    font-size: 16px;
                }}
                .btn-primary {{
                    background: #ffffff;
                    color: #111111;
                }}
                .btn-secondary {{
                    background: #141414;
                    color: #ffffff;
                    border: 1px solid var(--line);
                }}
                .box {{
                    margin-top: 18px;
                    padding: 16px;
                    border-radius: 16px;
                    border: 1px solid var(--line);
                    background: rgba(255,255,255,0.03);
                }}
                .muted {{
                    color: var(--muted);
                    font-size: 14px;
                }}
                .hidden {{
                    display: none;
                }}
                .row {{
                    display: grid;
                    gap: 12px;
                }}
                video {{
                    width: 100%;
                    background: #000;
                    border-radius: 20px;
                    margin-top: 16px;
                    box-shadow: 0 0 30px rgba(255,255,255,0.08);
                }}
                input[type="file"], input[type="text"], input[type="email"], input[type="tel"], input[type="password"], input[type="number"], textarea {{
                    display: block;
                    width: 100%;
                    padding: 14px;
                    margin-top: 10px;
                    border-radius: 14px;
                    border: 1px solid var(--line);
                    background: rgba(255,255,255,0.04);
                    color: #fff;
                }}
                input::placeholder, textarea::placeholder {{
                    color: #bfbfbf;
                }}
                .price {{
                    font-size: 28px;
                    font-weight: 800;
                    margin-top: 12px;
                }}
                .tiny {{
                    font-size: 12px;
                    color: #a8a8a8;
                    margin-top: 10px;
                }}
                .pill {{
                    display:inline-block;
                    padding:6px 10px;
                    border-radius:999px;
                    border:1px solid var(--line);
                    margin-top:8px;
                    font-size:13px;
                }}
                .summary-row {{
                    display:flex;
                    justify-content:space-between;
                    gap:20px;
                    margin:8px 0;
                    color: var(--muted);
                }}
                .summary-row strong {{
                    color:#fff;
                }}
                label.checkbox {{
                    display:flex;
                    align-items:flex-start;
                    gap:10px;
                    margin-top:12px;
                    color:var(--muted);
                    font-size:14px;
                }}
                .center {{
                    text-align:center;
                }}
            </style>
        </head>
        <body>
            <div class="wrap">{body}</div>
        </body>
        </html>
        """
    )


# ============================================================
# APP
# ============================================================

app = FastAPI(title=settings.app_name)


# ============================================================
# ROUTES: PUBLIC
# ============================================================

@app.get("/")
def root():
    return {
        "app": settings.app_name,
        "status": "ok",
        "queue_mode": "rq" if rq_queue else "local",
    }


@app.get("/comprar", response_class=HTMLResponse)
def pagina_comprar():
    body = f"""
    <div class="card">
        <div class="brand">ETERNA</div>
        <h1>Convierte un recuerdo en un momento eterno</h1>
        <p>6 fotos. 3 frases. Un vídeo emocional. Y, si quieres, un mensaje final tuyo, un regalo económico y la reacción sorpresa al final.</p>
        <div class="price">{settings.eterna_base_cents / 100:.2f} €</div>
        <div class="pill">Negro • blanco • emoción • sorpresa</div>

        <form id="createForm" action="/crear-eterna" method="post" enctype="multipart/form-data">
            <input type="text" name="nombre_destinatario" placeholder="Nombre del destinatario" required />
            <input type="text" name="nombre_remitente" placeholder="Tu nombre" required />
            <input type="email" name="buyer_email" placeholder="Tu email" required />
            <input type="tel" name="buyer_phone" placeholder="Tu teléfono (opcional)" />
            <textarea name="frase_1" rows="3" placeholder="Frase 1" required></textarea>
            <textarea name="frase_2" rows="3" placeholder="Frase 2" required></textarea>
            <textarea name="frase_3" rows="3" placeholder="Frase 3" required></textarea>

            <div class="box">
                <p><strong>Sube exactamente 6 fotos</strong></p>
                <input type="file" name="fotos" accept=".jpg,.jpeg,.png,.webp" multiple required />
            </div>

            <div class="box">
                <p><strong>Vídeo del regalante</strong> <span class="muted">(opcional, +{settings.extra_video_regalante_cents/100:.2f}€)</span></p>
                <p class="tiny">Puedes subirlo o grabarlo desde el móvil. Este vídeo irá al final de la ETERNA.</p>
                <input type="file" name="video_regalante" accept="video/*" capture="user" />
            </div>

            <div class="box">
                <label class="checkbox">
                    <input type="checkbox" name="incluye_reaccion" value="true" checked />
                    <span>Activar guardado de reacción sorpresa al final (+{settings.extra_reaccion_cents/100:.2f}€)</span>
                </label>
            </div>

            <div class="box">
                <label class="checkbox">
                    <input type="checkbox" id="regaloActivo" name="regalo_activo" value="true" />
                    <span>Añadir regalo económico</span>
                </label>
                <div id="giftFields" class="hidden">
                    <input type="number" step="0.01" min="0" name="regalo_amount_eur" id="regaloAmount" placeholder="Cantidad del regalo en €" />
                    <textarea name="regalo_mensaje" rows="2" placeholder="Mensaje opcional del regalo"></textarea>
                    <p class="tiny">El destinatario recibe el 100% del regalo. A ti se te cobra un 5% encima por el servicio de envío.</p>
                </div>
            </div>

            <div class="box">
                <input type="password" name="link_pin" placeholder="PIN opcional de acceso (solo números)" />
                <input type="number" name="max_views" min="0" max="{settings.max_views_hard_cap}" placeholder="Máximo de vistas opcional (0 = ilimitado)" />
            </div>

            <div class="box">
                <label class="checkbox">
                    <input type="checkbox" name="acepto_video_regalante" value="true" required />
                    <span>Autorizo el uso y almacenamiento de mi vídeo para crear y enviar esta ETERNA.</span>
                </label>
                <label class="checkbox">
                    <input type="checkbox" name="permite_compartir_regalante" value="true" checked />
                    <span>Permito compartir la ETERNA y mi vídeo final desde el enlace correspondiente.</span>
                </label>
                <label class="checkbox">
                    <input type="checkbox" name="permite_compartir_destinatario" value="true" checked />
                    <span>Permito que el destinatario pueda compartir su reacción si decide grabarla.</span>
                </label>
            </div>

            <div class="box">
                <div class="summary-row"><span>ETERNA base</span><strong>{settings.eterna_base_cents/100:.2f}€</strong></div>
                <div class="summary-row"><span>Vídeo del regalante</span><strong id="summaryVideo">0.00€</strong></div>
                <div class="summary-row"><span>Reacción</span><strong id="summaryReaction">{settings.extra_reaccion_cents/100:.2f}€</strong></div>
                <div class="summary-row"><span>Regalo</span><strong id="summaryGift">0.00€</strong></div>
                <div class="summary-row"><span>Servicio regalo (5%)</span><strong id="summaryGiftFee">0.00€</strong></div>
                <div class="summary-row"><span>Total</span><strong id="summaryTotal">{settings.eterna_base_cents/100 + settings.extra_reaccion_cents/100:.2f}€</strong></div>
            </div>

            <button class="btn btn-primary" type="submit">Pagar y crear mi ETERNA</button>
        </form>

        <div id="resultBox" class="box hidden">
            <p id="resultText">Preparando checkout…</p>
        </div>
    </div>

    <script>
    const form = document.getElementById('createForm');
    const resultBox = document.getElementById('resultBox');
    const resultText = document.getElementById('resultText');
    const regaloActivo = document.getElementById('regaloActivo');
    const giftFields = document.getElementById('giftFields');
    const regaloAmount = document.getElementById('regaloAmount');
    const incluyeReaccion = document.querySelector('input[name="incluye_reaccion"]');
    const videoRegalante = document.querySelector('input[name="video_regalante"]');

    const summaryVideo = document.getElementById('summaryVideo');
    const summaryReaction = document.getElementById('summaryReaction');
    const summaryGift = document.getElementById('summaryGift');
    const summaryGiftFee = document.getElementById('summaryGiftFee');
    const summaryTotal = document.getElementById('summaryTotal');

    function updateSummary() {{
        const base = {settings.eterna_base_cents / 100:.2f};
        const extraVideo = videoRegalante.files && videoRegalante.files.length > 0 ? {settings.extra_video_regalante_cents / 100:.2f} : 0;
        const extraReaction = incluyeReaccion.checked ? {settings.extra_reaccion_cents / 100:.2f} : 0;
        const gift = regaloActivo.checked ? parseFloat(regaloAmount.value || '0') : 0;
        const giftFee = regaloActivo.checked ? (gift * {settings.gift_fee_percent}) : 0;
        const total = base + extraVideo + extraReaction + gift + giftFee;

        summaryVideo.textContent = extraVideo.toFixed(2) + '€';
        summaryReaction.textContent = extraReaction.toFixed(2) + '€';
        summaryGift.textContent = gift.toFixed(2) + '€';
        summaryGiftFee.textContent = giftFee.toFixed(2) + '€';
        summaryTotal.textContent = total.toFixed(2) + '€';
    }}

    regaloActivo.addEventListener('change', () => {{
        giftFields.classList.toggle('hidden', !regaloActivo.checked);
        updateSummary();
    }});
    regaloAmount.addEventListener('input', updateSummary);
    incluyeReaccion.addEventListener('change', updateSummary);
    videoRegalante.addEventListener('change', updateSummary);
    updateSummary();

    form.addEventListener('submit', async (e) => {{
        e.preventDefault();
        resultBox.classList.remove('hidden');
        resultText.textContent = 'Subiendo recuerdos y preparando pago…';

        const formData = new FormData(form);

        if (!regaloActivo.checked) {{
            formData.set('regalo_amount_eur', '0');
        }}

        try {{
            const res = await fetch('/crear-eterna', {{ method: 'POST', body: formData }});
            const data = await res.json();

            if (!res.ok) throw new Error(data.detail || 'No se pudo crear el pedido.');

            resultText.textContent = 'Redirigiendo a pago…';
            window.location.href = data.checkout_url;
        }} catch (err) {{
            resultText.textContent = err.message || 'Error al crear el pedido.';
        }}
    }});
    </script>
    """
    return html_page("ETERNA - Comprar", body)


@app.post("/crear-eterna", response_model=PedidoCrearOut, status_code=status.HTTP_202_ACCEPTED)
async def crear_pedido(
    request: Request,
    nombre_destinatario: str = Form(...),
    nombre_remitente: str = Form(...),
    buyer_email: str = Form(...),
    buyer_phone: str = Form(default=""),
    frase_1: str = Form(...),
    frase_2: str = Form(...),
    frase_3: str = Form(...),
    link_pin: str = Form(default=""),
    max_views: int = Form(default=0),
    incluye_reaccion: Optional[str] = Form(default=None),
    regalo_activo: Optional[str] = Form(default=None),
    regalo_amount_eur: float = Form(default=0.0),
    regalo_mensaje: str = Form(default=""),
    acepto_video_regalante: Optional[str] = Form(default=None),
    permite_compartir_regalante: Optional[str] = Form(default=None),
    permite_compartir_destinatario: Optional[str] = Form(default=None),
    fotos: List[UploadFile] = File(...),
    video_regalante: Optional[UploadFile] = File(default=None),
    db: Session = Depends(get_db),
):
    ip = get_client_ip(request)
    enforce_rate_limit(ip)

    if count_pending_jobs_for_ip(db, ip) >= settings.max_pending_per_ip:
        raise HTTPException(
            status_code=429,
            detail="Tienes demasiados pedidos pendientes. Espera a que termine alguno."
        )

    frases = [frase_1, frase_2, frase_3]
    incluye_video_regalante = video_regalante is not None and bool(getattr(video_regalante, "filename", ""))
    incluye_reaccion_bool = bool(incluye_reaccion)
    regalo_activo_bool = bool(regalo_activo) and regalo_amount_eur > 0

    try:
        ensure_assets()
        validate_text_fields(frases, nombre_destinatario, nombre_remitente)
        clean_pin = validate_optional_pin(link_pin)
        clean_max_views = validate_optional_max_views(max_views or settings.default_max_views)
        buyer_email = sanitize_display_text(buyer_email)
        if "@" not in buyer_email:
            raise ValueError("Email de comprador inválido.")
        if incluye_video_regalante and not acepto_video_regalante:
            raise ValueError("Debes autorizar el uso del vídeo del regalante.")
        if regalo_amount_eur < 0:
            raise ValueError("El regalo económico no puede ser negativo.")
        regalo_mensaje = sanitize_display_text(regalo_mensaje, 240)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    pricing = compute_pricing(
        incluye_video_regalante=incluye_video_regalante,
        incluye_reaccion=incluye_reaccion_bool,
        regalo_amount_eur=regalo_amount_eur if regalo_activo_bool else 0.0,
    )

    access_token = generate_access_token()
    expires_at = None
    if settings.link_expiry_hours > 0:
        expires_at = utcnow_naive() + timedelta(hours=settings.link_expiry_hours)

    pedido = PedidoEterna(
        access_token=access_token,
        fotos_csv="",
        frases_csv=csv_join([sanitize_display_text(x, 180) for x in frases]),
        nombre_destinatario=sanitize_display_text(nombre_destinatario),
        nombre_remitente=sanitize_display_text(nombre_remitente),
        buyer_email=buyer_email,
        buyer_phone=sanitize_display_text(buyer_phone, 64),
        requester_ip=ip,
        link_pin_hash=hash_pin(clean_pin) if clean_pin else None,
        max_views=clean_max_views,
        payment_status="pending_payment",
        status="checkout_created",
        expires_at=expires_at,
        incluye_video_regalante=incluye_video_regalante,
        incluye_reaccion=incluye_reaccion_bool,
        permite_compartir_regalante=bool(permite_compartir_regalante),
        permite_compartir_destinatario=bool(permite_compartir_destinatario),
        regalo_activo=regalo_activo_bool,
        regalo_amount_eur=round(regalo_amount_eur if regalo_activo_bool else 0.0, 2),
        regalo_fee_eur=pricing["regalo_fee"],
        regalo_total_cobrado_eur=pricing["regalo_total_cobrado"],
        regalo_mensaje=regalo_mensaje,
        precio_base_eur=pricing["base"],
        extra_video_eur=pricing["extra_video"],
        extra_reaccion_eur=pricing["extra_reaccion"],
        total_producto_eur=pricing["total_producto"],
        total_checkout_eur=pricing["total_checkout"],
    )

    db.add(pedido)
    db.commit()
    db.refresh(pedido)

    try:
        saved_paths = await save_uploaded_images_for_job(pedido.id, fotos)
        pedido.fotos_csv = csv_join(saved_paths)

        video_regalante_path = await save_video_regalante_for_job(pedido.id, video_regalante)
        pedido.archivo_video_regalante_path = video_regalante_path

        checkout_url, session_id = create_stripe_checkout_session(pedido)
        pedido.stripe_checkout_session_id = session_id
        db.commit()
    except Exception as exc:
        delete_job_inputs(pedido.id)
        pedido.status = "failed"
        pedido.error_message = f"Error preparando pedido: {exc}"
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc))

    return PedidoCrearOut(
        id=pedido.id,
        status=pedido.status,
        payment_status=pedido.payment_status,
        poll_url=build_status_url(pedido.id),
        checkout_url=checkout_url,
        preview_url=build_delivery_url(pedido.access_token),
        total_checkout_eur=pedido.total_checkout_eur,
    )


@app.post("/stripe/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")

    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=500, detail="Webhook Stripe no configurado.")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
    except Exception as exc:
        logger.warning("Webhook Stripe inválido: %s", exc)
        raise HTTPException(status_code=400, detail="Webhook inválido.")

    event_id = event["id"]
    event_type = event["type"]

    existing = db.get(StripeEvent, event_id)
    if existing:
        return {"status": "duplicate"}

    db.add(StripeEvent(id=event_id, event_type=event_type))
    db.commit()

    if event_type == "checkout.session.completed":
        session_obj = event["data"]["object"]
        pedido_id = (session_obj.get("metadata") or {}).get("pedido_id")
        stripe_session_id = session_obj.get("id")
        payment_intent_id = session_obj.get("payment_intent")

        if pedido_id:
            pedido = db.get(PedidoEterna, pedido_id)
            if pedido and pedido.payment_status != "paid":
                pedido.payment_status = "paid"
                pedido.status = "paid"
                pedido.stripe_checkout_session_id = stripe_session_id
                pedido.stripe_payment_intent_id = payment_intent_id
                db.commit()

                notify_buyer_paid_and_processing(pedido)
                db.commit()

                enqueue_render(pedido.id)

    return {"received": True}


@app.get("/checkout/success", response_class=HTMLResponse)
def checkout_success(pedido_id: str, db: Session = Depends(get_db)):
    pedido = db.get(PedidoEterna, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")

    body = f"""
    <div class="card">
        <div class="brand">ETERNA</div>
        <h1>Pago recibido</h1>
        <p>Tu ETERNA ya está en marcha.</p>
        <div class="box">
            <p><strong>ID:</strong> {html.escape(pedido.id)}</p>
            <p><strong>Estado:</strong> {html.escape(pedido.status)}</p>
            <p><strong>Total:</strong> {pedido.total_checkout_eur:.2f}€</p>
            <a class="btn btn-primary" href="{html.escape(build_status_url(pedido.id))}">Ver estado</a>
        </div>
    </div>
    """
    return html_page("Pago completado", body)


@app.get("/checkout/cancel", response_class=HTMLResponse)
def checkout_cancel(pedido_id: str, db: Session = Depends(get_db)):
    pedido = db.get(PedidoEterna, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")

    body = f"""
    <div class="card">
        <div class="brand">ETERNA</div>
        <h1>Pago cancelado</h1>
        <p>Tu pedido no se ha pagado todavía.</p>
        <div class="box">
            <p><strong>ID:</strong> {html.escape(pedido.id)}</p>
            <p><strong>Pago:</strong> {html.escape(pedido.payment_status)}</p>
        </div>
    </div>
    """
    return html_page("Pago cancelado", body)


@app.get("/estado/{pedido_id}", response_model=PedidoEstadoOut)
def estado_pedido(pedido_id: str, db: Session = Depends(get_db)):
    pedido = db.get(PedidoEterna, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")

    return PedidoEstadoOut(
        id=pedido.id,
        status=pedido.status,
        payment_status=pedido.payment_status,
        error_message=pedido.error_message,
        views_count=pedido.views_count,
        max_views=pedido.max_views,
        created_at=pedido.created_at.replace(tzinfo=timezone.utc),
        render_started_at=pedido.render_started_at.replace(tzinfo=timezone.utc) if pedido.render_started_at else None,
        render_finished_at=pedido.render_finished_at.replace(tzinfo=timezone.utc) if pedido.render_finished_at else None,
        delivered_at=pedido.delivered_at.replace(tzinfo=timezone.utc) if pedido.delivered_at else None,
        reaction_uploaded_at=pedido.reaction_uploaded_at.replace(tzinfo=timezone.utc) if pedido.reaction_uploaded_at else None,
        expires_at=pedido.expires_at.replace(tzinfo=timezone.utc) if pedido.expires_at else None,
        tiene_video=bool(pedido.archivo_video_path),
        tiene_reaccion=bool(pedido.archivo_reaccion_path),
        url_entrega=build_delivery_url(pedido.access_token),
        url_video=build_video_url(pedido.access_token),
        incluye_video_regalante=pedido.incluye_video_regalante,
        incluye_reaccion=pedido.incluye_reaccion,
        regalo_activo=pedido.regalo_activo,
        regalo_amount_eur=pedido.regalo_amount_eur,
        regalo_fee_eur=pedido.regalo_fee_eur,
        total_checkout_eur=pedido.total_checkout_eur,
    )


@app.get("/video-file")
def video_file(
    token: str = Query(...),
    pin: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    pedido = get_pedido_by_token(db, token, pin=pin)

    if pedido.payment_status != "paid":
        raise HTTPException(status_code=403, detail="Pedido no pagado.")
    if pedido.status not in ["completed", "delivered"]:
        raise HTTPException(status_code=404, detail="Vídeo no disponible todavía.")
    if not pedido.archivo_video_path or not os.path.exists(pedido.archivo_video_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")

    pedido.views_count += 1
    if pedido.delivered_at is None:
        pedido.delivered_at = utcnow_naive()
    pedido.status = "delivered"
    db.commit()

    return FileResponse(
        path=pedido.archivo_video_path,
        media_type="video/mp4",
        filename="tu_eterna.mp4",
        headers={
            "X-Robots-Tag": "noindex, nofollow, noarchive",
            "Cache-Control": "private, no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        },
    )


@app.post("/upload-reaction")
async def upload_reaction(
    token: str = Form(...),
    pin: str = Form(default=""),
    permiso_publicar: bool = Form(False),
    reaction_file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    pedido = get_pedido_by_token(db, token, pin=pin or None)

    if not pedido.incluye_reaccion:
        raise HTTPException(status_code=400, detail="Esta ETERNA no tiene activada la reacción.")

    ext = Path(reaction_file.filename or "").suffix.lower()
    if ext not in [".webm", ".mp4", ".mov", ".m4v"]:
        raise HTTPException(status_code=400, detail="Formato no permitido.")

    content = await reaction_file.read()
    max_bytes = settings.max_reaction_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=400, detail=f"La reacción supera {settings.max_reaction_mb}MB.")

    reaction_dir = REACTIONS_DIR / pedido.id
    reaction_dir.mkdir(parents=True, exist_ok=True)
    dst = reaction_dir / f"reaction{ext}"

    with open(dst, "wb") as f:
        f.write(content)

    if not dst.exists() or dst.stat().st_size == 0:
        raise HTTPException(status_code=500, detail="No se pudo guardar la reacción.")

    pedido.archivo_reaccion_path = str(dst)
    pedido.reaction_uploaded_at = utcnow_naive()
    pedido.permiso_publicar_reaccion = permiso_publicar
    pedido.acepto_grabar_reaccion = True
    db.commit()

    return {"ok": True, "message": "Reacción subida correctamente."}


@app.get("/entrega", response_class=HTMLResponse)
def pagina_entrega(
    token: str = Query(...),
    pin: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    pedido = get_pedido_by_token(db, token, pin=pin)

    if pedido.payment_status != "paid":
        body = """
        <div class="card"><div class="brand">ETERNA</div><h1>Pedido no pagado</h1></div>
        """
        return html_page("ETERNA", body)

    if pedido.status not in ["completed", "delivered"] or not pedido.archivo_video_path:
        body = """
        <div class="card">
            <div class="brand">ETERNA</div>
            <h1>Tu momento aún no está listo</h1>
            <p>Estamos terminando de preparar este recuerdo especial.</p>
            <p class="muted">Vuelve a intentarlo en unos minutos.</p>
        </div>
        """
        return html_page("ETERNA", body)

    video_url = build_video_url(token)
    if pin:
        video_url += "&pin=" + pin

    pin_param_script = json.dumps(pin or "")
    share_url = build_delivery_url(token)

    body = f"""
    <div class="card">
        <div class="brand">ETERNA</div>
        <div id="introScreen">
            <h1>Alguien ha preparado algo para ti</h1>
            <p>Hay momentos que merecen quedarse para siempre.</p>
            <button class="btn btn-primary" id="btnStart">Ver mi ETERNA</button>
        </div>

        <div id="prepareScreen" class="box hidden">
            <p>Vívelo con calma. Puede ser un momento especial.</p>
            {'<p class="muted">Antes de empezar, puedes activar tu cámara. No se mostrará nada mientras ves el vídeo.</p>' if pedido.incluye_reaccion else ''}
            <div class="row">
                {'<button class="btn btn-primary" id="btnCamera">Activar cámara y continuar</button>' if pedido.incluye_reaccion else ''}
                <button class="btn btn-secondary" id="btnContinue">Continuar</button>
            </div>
        </div>

        <div id="statusBox" class="box hidden">
            <p id="statusText" class="muted">Preparando...</p>
        </div>

        <div id="cameraBox" class="box hidden">
            <p class="muted">Cámara preparada</p>
            <video id="cameraPreview" autoplay muted playsinline></video>
        </div>

        <div id="videoBox" class="hidden">
            <video id="eternaVideo" controls playsinline preload="auto">
                <source src="{html.escape(video_url)}" type="video/mp4">
                Tu navegador no soporta vídeo.
            </video>
        </div>

        <div id="finalPause" class="box hidden center">
            <p>...</p>
        </div>

        <div id="afterVideo" class="box hidden center">
            <h2>Este momento también puede quedarse para siempre</h2>
            <p id="afterText">Gracias por vivirlo.</p>

            <div id="reactionReveal" class="hidden">
                <p>Si quieres, puedes enviárselo a quien te regaló este momento.</p>
                <button class="btn btn-primary" id="btnShowSaveReaction">Guardar mi reacción</button>
                <button class="btn btn-secondary" id="btnSkipReaction">Ahora no</button>
            </div>

            <div id="permissionBox" class="hidden">
                <label class="checkbox">
                    <input type="checkbox" id="permisoPublicar" />
                    <span>Doy permiso para que ETERNA use mi reacción con fines promocionales</span>
                </label>
                <button class="btn btn-primary" id="btnUploadReaction">Enviar reacción</button>
            </div>

            <div id="shareBox" class="hidden">
                <button class="btn btn-secondary" id="btnCopyLink">Copiar enlace</button>
                <a class="btn btn-secondary" id="btnWhatsapp" target="_blank">Compartir por WhatsApp</a>
            </div>
        </div>
    </div>

    <script>
    const token = {json.dumps(token)};
    const pin = {pin_param_script};
    const shareUrl = {json.dumps(share_url)};
    const allowReaction = {json.dumps(bool(pedido.incluye_reaccion))};

    const introScreen = document.getElementById('introScreen');
    const prepareScreen = document.getElementById('prepareScreen');
    const statusBox = document.getElementById('statusBox');
    const statusText = document.getElementById('statusText');
    const cameraBox = document.getElementById('cameraBox');
    const cameraPreview = document.getElementById('cameraPreview');
    const videoBox = document.getElementById('videoBox');
    const videoEl = document.getElementById('eternaVideo');
    const finalPause = document.getElementById('finalPause');
    const afterVideo = document.getElementById('afterVideo');
    const afterText = document.getElementById('afterText');
    const reactionReveal = document.getElementById('reactionReveal');
    const permissionBox = document.getElementById('permissionBox');
    const permisoPublicar = document.getElementById('permisoPublicar');
    const btnStart = document.getElementById('btnStart');
    const btnCamera = document.getElementById('btnCamera');
    const btnContinue = document.getElementById('btnContinue');
    const btnShowSaveReaction = document.getElementById('btnShowSaveReaction');
    const btnSkipReaction = document.getElementById('btnSkipReaction');
    const btnUploadReaction = document.getElementById('btnUploadReaction');
    const shareBox = document.getElementById('shareBox');
    const btnCopyLink = document.getElementById('btnCopyLink');
    const btnWhatsapp = document.getElementById('btnWhatsapp');

    let stream = null;
    let recorder = null;
    let chunks = [];
    let recordedBlob = null;
    let cameraArmed = false;

    function showStatus(text) {{
        statusBox.classList.remove('hidden');
        statusText.textContent = text;
    }}

    function hideStatus() {{
        statusBox.classList.add('hidden');
    }}

    function stopStream() {{
        if (stream) {{
            stream.getTracks().forEach(track => track.stop());
            stream = null;
        }}
        cameraPreview.srcObject = null;
    }}

    function prepareShare() {{
        shareBox.classList.remove('hidden');
        const texto = encodeURIComponent("Quiero compartir contigo este momento de ETERNA");
        const url = encodeURIComponent(shareUrl);
        btnWhatsapp.href = `https://wa.me/?text=${{texto}}%20${{url}}`;
    }}

    async function armCamera() {{
        if (!navigator.mediaDevices || !window.MediaRecorder) {{
            showStatus('Tu navegador no permite preparar la cámara aquí.');
            return false;
        }}
        showStatus('Solicitando acceso a cámara...');
        try {{
            stream = await navigator.mediaDevices.getUserMedia({{
                video: {{ facingMode: "user" }},
                audio: true
            }});
            cameraPreview.srcObject = stream;
            cameraBox.classList.remove('hidden');

            let mimeType = "";
            if (MediaRecorder.isTypeSupported("video/webm;codecs=vp9,opus")) {{
                mimeType = "video/webm;codecs=vp9,opus";
            }} else if (MediaRecorder.isTypeSupported("video/webm;codecs=vp8,opus")) {{
                mimeType = "video/webm;codecs=vp8,opus";
            }} else if (MediaRecorder.isTypeSupported("video/webm")) {{
                mimeType = "video/webm";
            }}

            recorder = mimeType ? new MediaRecorder(stream, {{ mimeType }}) : new MediaRecorder(stream);
            chunks = [];
            recorder.ondataavailable = (e) => {{
                if (e.data && e.data.size > 0) chunks.push(e.data);
            }};
            recorder.onstop = () => {{
                recordedBlob = new Blob(chunks, {{ type: recorder.mimeType || "video/webm" }});
                stopStream();
            }};
            cameraArmed = true;
            hideStatus();
            return true;
        }} catch (err) {{
            console.error(err);
            showStatus('No se pudo acceder a la cámara.');
            return false;
        }}
    }}

    function startPlayback() {{
        prepareScreen.classList.add('hidden');
        videoBox.classList.remove('hidden');

        if (cameraArmed && recorder) {{
            try {{
                recorder.start();
            }} catch (err) {{
                console.error(err);
            }}
        }}

        videoEl.play().catch(() => {{
            showStatus('Pulsa play para empezar.');
        }});
    }}

    btnStart.addEventListener('click', () => {{
        introScreen.classList.add('hidden');
        prepareScreen.classList.remove('hidden');
    }});

    if (btnCamera) {{
        btnCamera.addEventListener('click', async () => {{
            await armCamera();
            startPlayback();
        }});
    }}

    btnContinue.addEventListener('click', () => {{
        startPlayback();
    }});

    videoEl.addEventListener('ended', async () => {{
        if (cameraArmed && recorder && recorder.state !== 'inactive') {{
            try {{
                recorder.stop();
            }} catch (err) {{
                console.error(err);
            }}
        }}

        finalPause.classList.remove('hidden');
        setTimeout(() => {{
            finalPause.classList.add('hidden');
            afterVideo.classList.remove('hidden');

            if (allowReaction && recordedBlob) {{
                afterText.textContent = 'Tu momento ha quedado capturado. Puedes decidir si enviarlo.';
                reactionReveal.classList.remove('hidden');
            }} else {{
                afterText.textContent = 'Gracias por vivir este momento.';
                prepareShare();
            }}

            afterVideo.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
        }}, 1400);
    }});

    if (btnShowSaveReaction) {{
        btnShowSaveReaction.addEventListener('click', () => {{
            reactionReveal.classList.add('hidden');
            permissionBox.classList.remove('hidden');
        }});
    }}

    if (btnSkipReaction) {{
        btnSkipReaction.addEventListener('click', () => {{
            reactionReveal.classList.add('hidden');
            afterText.textContent = 'Gracias por vivir este momento.';
            prepareShare();
        }});
    }}

    if (btnUploadReaction) {{
        btnUploadReaction.addEventListener('click', async () => {{
            if (!recordedBlob) {{
                alert('No hay reacción grabada.');
                return;
            }}

            btnUploadReaction.disabled = true;
            btnUploadReaction.textContent = 'Enviando reacción…';

            const ext = recordedBlob.type.includes('mp4') ? 'mp4' : 'webm';
            const file = new File([recordedBlob], `reaction.${{ext}}`, {{ type: recordedBlob.type || 'video/webm' }});

            const formData = new FormData();
            formData.append('token', token);
            if (pin) formData.append('pin', pin);
            formData.append('permiso_publicar', permisoPublicar.checked ? 'true' : 'false');
            formData.append('reaction_file', file);

            try {{
                const res = await fetch('/upload-reaction', {{
                    method: 'POST',
                    body: formData
                }});

                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || 'No se pudo subir la reacción');

                btnUploadReaction.textContent = 'Reacción enviada';
                permissionBox.classList.add('hidden');
                afterText.textContent = 'Tu reacción se ha guardado correctamente.';
                prepareShare();
            }} catch (err) {{
                console.error(err);
                btnUploadReaction.disabled = false;
                btnUploadReaction.textContent = 'Enviar reacción';
                alert(err.message || 'Error al subir la reacción');
            }}
        }});
    }}

    btnCopyLink.addEventListener('click', async () => {{
        try {{
            await navigator.clipboard.writeText(shareUrl);
            btnCopyLink.textContent = 'Enlace copiado';
        }} catch (err) {{
            alert('No se pudo copiar el enlace');
        }}
    }});
    </script>
    """
    return html_page("ETERNA - Entrega", body)


# ============================================================
# HEALTH / ANALYTICS / ADMIN
# ============================================================

@app.get("/healthz")
def healthz():
    return {"ok": True, "app": settings.app_name}


@app.get("/healthz/deep")
def healthz_deep():
    result = {
        "app": True,
        "db": False,
        "stripe": False,
        "redis": False,
        "smtp": False,
    }

    try:
        db = SessionLocal()
        db.execute(select(1))
        db.close()
        result["db"] = True
    except Exception:
        pass

    try:
        if settings.stripe_secret_key:
            stripe.Balance.retrieve()
            result["stripe"] = True
    except Exception:
        pass

    try:
        if redis_conn:
            redis_conn.ping()
            result["redis"] = True
    except Exception:
        pass

    try:
        if settings.smtp_host:
            smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5)
            smtp.quit()
            result["smtp"] = True
    except Exception:
        pass

    return result


@app.get("/analytics/basic")
def analytics_basic(
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),
):
    total = db.execute(select(func.count()).select_from(PedidoEterna)).scalar_one()
    paid = db.execute(
        select(func.count()).select_from(PedidoEterna).where(PedidoEterna.payment_status == "paid")
    ).scalar_one()
    completed = db.execute(
        select(func.count()).select_from(PedidoEterna).where(PedidoEterna.status == "completed")
    ).scalar_one()
    delivered = db.execute(
        select(func.count()).select_from(PedidoEterna).where(PedidoEterna.status == "delivered")
    ).scalar_one()
    reactions = db.execute(
        select(func.count()).select_from(PedidoEterna).where(PedidoEterna.archivo_reaccion_path.is_not(None))
    ).scalar_one()

    return {
        "orders_total": total,
        "orders_paid": paid,
        "orders_completed": completed,
        "orders_delivered": delivered,
        "reactions_uploaded": reactions,
    }


@app.get("/admin/stats")
def admin_stats(
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),
):
    total = db.execute(select(func.count()).select_from(PedidoEterna)).scalar_one()
    return {
        "total": total,
        "checkout_created": db.execute(select(func.count()).select_from(PedidoEterna).where(PedidoEterna.status == "checkout_created")).scalar_one(),
        "paid": db.execute(select(func.count()).select_from(PedidoEterna).where(PedidoEterna.status == "paid")).scalar_one(),
        "queued": db.execute(select(func.count()).select_from(PedidoEterna).where(PedidoEterna.status == "queued")).scalar_one(),
        "rendering": db.execute(select(func.count()).select_from(PedidoEterna).where(PedidoEterna.status == "rendering")).scalar_one(),
        "completed": db.execute(select(func.count()).select_from(PedidoEterna).where(PedidoEterna.status == "completed")).scalar_one(),
        "delivered": db.execute(select(func.count()).select_from(PedidoEterna).where(PedidoEterna.status == "delivered")).scalar_one(),
        "failed": db.execute(select(func.count()).select_from(PedidoEterna).where(PedidoEterna.status == "failed")).scalar_one(),
        "queue_mode": "rq" if rq_queue else "local",
    }


@app.get("/admin/pedido/{pedido_id}/resumen", response_class=HTMLResponse)
def resumen_pedido(
    pedido_id: str,
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),
):
    pedido = db.get(PedidoEterna, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")

    reaccion_html = """
    <div class="box">
        <p class="muted"><strong>Aún no hay reacción guardada.</strong></p>
    </div>
    """
    if pedido.archivo_reaccion_path:
        reaccion_html = f"""
        <div class="box">
            <p class="muted"><strong>Reacción disponible.</strong></p>
            <a class="btn btn-secondary" href="/admin/reaccion/{html.escape(pedido.id)}">Ver reacción</a>
        </div>
        """

    regalante_html = """
    <div class="box">
        <p class="muted"><strong>No hay vídeo del regalante.</strong></p>
    </div>
    """
    if pedido.archivo_video_regalante_path and os.path.exists(pedido.archivo_video_regalante_path):
        regalante_html = f"""
        <div class="box">
            <p class="muted"><strong>Vídeo del regalante guardado.</strong></p>
            <a class="btn btn-secondary" href="/admin/video-regalante/{html.escape(pedido.id)}">Ver vídeo del regalante</a>
        </div>
        """

    body = f"""
    <div class="card">
        <div class="brand">ETERNA</div>
        <h1>Resumen del pedido</h1>
        <p><strong>ID:</strong> {html.escape(pedido.id)}</p>
        <p><strong>Estado:</strong> {html.escape(pedido.status)}</p>
        <p><strong>Pago:</strong> {html.escape(pedido.payment_status)}</p>
        <p><strong>Destinatario:</strong> {html.escape(pedido.nombre_destinatario)}</p>
        <p><strong>Remitente:</strong> {html.escape(pedido.nombre_remitente)}</p>
        <p><strong>Total checkout:</strong> {pedido.total_checkout_eur:.2f}€</p>
        <p><strong>Regalo:</strong> {pedido.regalo_amount_eur:.2f}€</p>
        <p><strong>Fee regalo:</strong> {pedido.regalo_fee_eur:.2f}€</p>
        <p><strong>Enlace de entrega:</strong><br><span class="muted">{html.escape(build_delivery_url(pedido.access_token))}</span></p>

        <div class="box">
            <a class="btn btn-primary" href="{html.escape(build_delivery_url(pedido.access_token))}">Abrir entrega</a>
        </div>

        {regalante_html}
        {reaccion_html}
    </div>
    """
    return html_page("ETERNA - Resumen", body)


@app.get("/admin/reaccion/{pedido_id}")
def ver_reaccion(
    pedido_id: str,
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),
):
    pedido = db.get(PedidoEterna, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")
    if not pedido.archivo_reaccion_path or not os.path.exists(pedido.archivo_reaccion_path):
        raise HTTPException(status_code=404, detail="Reacción no encontrada.")

    ext = Path(pedido.archivo_reaccion_path).suffix.lower()
    media_type = "video/webm"
    if ext in [".mp4", ".m4v"]:
        media_type = "video/mp4"
    elif ext == ".mov":
        media_type = "video/quicktime"

    return FileResponse(
        path=pedido.archivo_reaccion_path,
        media_type=media_type,
        filename=f"reaccion{ext}",
        headers={"X-Robots-Tag": "noindex, nofollow, noarchive"},
    )


@app.get("/admin/video-regalante/{pedido_id}")
def ver_video_regalante(
    pedido_id: str,
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),
):
    pedido = db.get(PedidoEterna, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")
    if not pedido.archivo_video_regalante_path or not os.path.exists(pedido.archivo_video_regalante_path):
        raise HTTPException(status_code=404, detail="Vídeo del regalante no encontrado.")

    ext = Path(pedido.archivo_video_regalante_path).suffix.lower()
    media_type = "video/mp4"
    if ext == ".webm":
        media_type = "video/webm"
    elif ext == ".mov":
        media_type = "video/quicktime"

    return FileResponse(
        path=pedido.archivo_video_regalante_path,
        media_type=media_type,
        filename=f"video_regalante{ext}",
        headers={"X-Robots-Tag": "noindex, nofollow, noarchive"},
    )


# ============================================================
# LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    worker_stop_event.clear()

    global worker_thread, cleanup_thread

    if not rq_queue:
        worker_thread = threading.Thread(target=local_worker_loop, daemon=True)
        worker_thread.start()

    cleanup_thread = threading.Thread(target=cleanup_orphans_loop, daemon=True)
    cleanup_thread.start()

    yield

    worker_stop_event.set()
    if worker_thread is not None:
        worker_thread.join(timeout=5)
    if cleanup_thread is not None:
        cleanup_thread.join(timeout=5)


app.router.lifespan_context = lifespan


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
