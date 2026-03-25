import html
import json
import mimetypes
import os
import secrets
import sqlite3
import urllib.parse
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import boto3
import stripe
from botocore.client import Config
from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from twilio.rest import Client

app = FastAPI(title="ETERNA MASTER TWILIO CLEAN")


# =========================================================
# CONFIG
# =========================================================

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "").strip()

PUBLIC_BASE_URL = os.getenv(
    "PUBLIC_BASE_URL",
    "https://eterna-v2-lab.onrender.com",
).strip().rstrip("/")

BASE_PRICE = float(os.getenv("ETERNA_BASE_PRICE", "29"))
CURRENCY = os.getenv("ETERNA_CURRENCY", "eur").strip().lower()

GIFT_COMMISSION_RATE = float(os.getenv("GIFT_COMMISSION_RATE", "0.05"))
FIXED_PLATFORM_FEE = float(os.getenv("ETERNA_FIXED_FEE", "2"))
GIFT_REFUND_DAYS = int(os.getenv("GIFT_REFUND_DAYS", "20"))

DEFAULT_GIFT_VIDEO_URL = os.getenv("DEFAULT_GIFT_VIDEO_URL", "").strip()

R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY", "").strip()
R2_SECRET_KEY = os.getenv("R2_SECRET_KEY", "").strip()
R2_BUCKET = os.getenv("R2_BUCKET", "").strip()
R2_ENDPOINT = os.getenv("R2_ENDPOINT", "").strip().rstrip("/")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "").strip().rstrip("/")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "").strip()

MAX_VIDEO_SIZE = 30 * 1024 * 1024
ALLOWED_VIDEO_TYPES = {
    "video/webm",
    "video/mp4",
    "application/octet-stream",
}

DATA_FOLDER = Path("data")
DATA_FOLDER.mkdir(parents=True, exist_ok=True)

VIDEO_FOLDER = Path("videos")
VIDEO_FOLDER.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_FOLDER / "eterna.db"

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY


# =========================================================
# LOG
# =========================================================

def log_info(label: str, value=None):
    if value is None:
        print(f"[INFO] {label}")
    else:
        print(f"[INFO] {label}: {value}")


def log_error(label: str, error: Exception):
    print(f"[ERROR] {label}: {error}")


# =========================================================
# DB
# =========================================================

def db_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def column_exists(table_name: str, column_name: str) -> bool:
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table_name})")
    cols = cur.fetchall()
    conn.close()
    return any(col["name"] == column_name for col in cols)


def add_column_if_missing(table_name: str, column_name: str, sql: str):
    if not column_exists(table_name, column_name):
        conn = db_conn()
        cur = conn.cursor()
        cur.execute(sql)
        conn.commit()
        conn.close()


def init_db():
    conn = db_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS senders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT,
        phone TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS recipients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id TEXT PRIMARY KEY,
        sender_id INTEGER NOT NULL,
        recipient_id INTEGER NOT NULL,

        phrase_1 TEXT NOT NULL,
        phrase_2 TEXT NOT NULL,
        phrase_3 TEXT NOT NULL,

        gift_amount REAL NOT NULL DEFAULT 0,
        platform_fixed_fee REAL NOT NULL DEFAULT 0,
        platform_variable_fee REAL NOT NULL DEFAULT 0,
        platform_total_fee REAL NOT NULL DEFAULT 0,
        total_amount REAL NOT NULL DEFAULT 0,

        paid INTEGER NOT NULL DEFAULT 0,
        delivered_to_recipient INTEGER NOT NULL DEFAULT 0,
        reaction_uploaded INTEGER NOT NULL DEFAULT 0,
        cashout_completed INTEGER NOT NULL DEFAULT 0,
        transfer_completed INTEGER NOT NULL DEFAULT 0,
        transfer_in_progress INTEGER NOT NULL DEFAULT 0,
        sender_notified INTEGER NOT NULL DEFAULT 0,
        experience_started INTEGER NOT NULL DEFAULT 0,
        experience_completed INTEGER NOT NULL DEFAULT 0,
        connect_onboarding_completed INTEGER NOT NULL DEFAULT 0,
        gift_refunded INTEGER NOT NULL DEFAULT 0,

        stripe_session_id TEXT,
        stripe_payment_status TEXT,
        stripe_payment_intent_id TEXT,
        stripe_connected_account_id TEXT,
        stripe_transfer_id TEXT,
        stripe_gift_refund_id TEXT,

        recipient_token TEXT NOT NULL UNIQUE,
        sender_token TEXT NOT NULL UNIQUE,

        reaction_video_local TEXT,
        reaction_video_public_url TEXT,
        gift_video_url TEXT,

        gift_refund_deadline_at TEXT,

        recipient_sms_sent_at TEXT,
        sender_sms_sent_at TEXT,
        recipient_sms_sid TEXT,
        sender_sms_sid TEXT,

        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,

        FOREIGN KEY(sender_id) REFERENCES senders(id),
        FOREIGN KEY(recipient_id) REFERENCES recipients(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT NOT NULL,
        asset_type TEXT NOT NULL,
        file_url TEXT NOT NULL,
        storage_provider TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(order_id) REFERENCES orders(id)
    )
    """)

    conn.commit()
    conn.close()

    add_column_if_missing(
        "orders",
        "sender_notified",
        "ALTER TABLE orders ADD COLUMN sender_notified INTEGER NOT NULL DEFAULT 0",
    )
    add_column_if_missing(
        "orders",
        "experience_started",
        "ALTER TABLE orders ADD COLUMN experience_started INTEGER NOT NULL DEFAULT 0",
    )
    add_column_if_missing(
        "orders",
        "experience_completed",
        "ALTER TABLE orders ADD COLUMN experience_completed INTEGER NOT NULL DEFAULT 0",
    )
    add_column_if_missing(
        "orders",
        "reaction_video_public_url",
        "ALTER TABLE orders ADD COLUMN reaction_video_public_url TEXT",
    )
    add_column_if_missing(
        "orders",
        "gift_video_url",
        "ALTER TABLE orders ADD COLUMN gift_video_url TEXT",
    )
    add_column_if_missing(
        "orders",
        "reaction_video_local",
        "ALTER TABLE orders ADD COLUMN reaction_video_local TEXT",
    )
    add_column_if_missing(
        "orders",
        "stripe_session_id",
        "ALTER TABLE orders ADD COLUMN stripe_session_id TEXT",
    )
    add_column_if_missing(
        "orders",
        "stripe_payment_status",
        "ALTER TABLE orders ADD COLUMN stripe_payment_status TEXT",
    )
    add_column_if_missing(
        "orders",
        "stripe_payment_intent_id",
        "ALTER TABLE orders ADD COLUMN stripe_payment_intent_id TEXT",
    )
    add_column_if_missing(
        "orders",
        "stripe_connected_account_id",
        "ALTER TABLE orders ADD COLUMN stripe_connected_account_id TEXT",
    )
    add_column_if_missing(
        "orders",
        "stripe_transfer_id",
        "ALTER TABLE orders ADD COLUMN stripe_transfer_id TEXT",
    )
    add_column_if_missing(
        "orders",
        "connect_onboarding_completed",
        "ALTER TABLE orders ADD COLUMN connect_onboarding_completed INTEGER NOT NULL DEFAULT 0",
    )
    add_column_if_missing(
        "orders",
        "transfer_completed",
        "ALTER TABLE orders ADD COLUMN transfer_completed INTEGER NOT NULL DEFAULT 0",
    )
    add_column_if_missing(
        "orders",
        "transfer_in_progress",
        "ALTER TABLE orders ADD COLUMN transfer_in_progress INTEGER NOT NULL DEFAULT 0",
    )
    add_column_if_missing(
        "orders",
        "platform_fixed_fee",
        "ALTER TABLE orders ADD COLUMN platform_fixed_fee REAL NOT NULL DEFAULT 0",
    )
    add_column_if_missing(
        "orders",
        "platform_variable_fee",
        "ALTER TABLE orders ADD COLUMN platform_variable_fee REAL NOT NULL DEFAULT 0",
    )
    add_column_if_missing(
        "orders",
        "platform_total_fee",
        "ALTER TABLE orders ADD COLUMN platform_total_fee REAL NOT NULL DEFAULT 0",
    )
    add_column_if_missing(
        "orders",
        "gift_refund_deadline_at",
        "ALTER TABLE orders ADD COLUMN gift_refund_deadline_at TEXT",
    )
    add_column_if_missing(
        "orders",
        "gift_refunded",
        "ALTER TABLE orders ADD COLUMN gift_refunded INTEGER NOT NULL DEFAULT 0",
    )
    add_column_if_missing(
        "orders",
        "stripe_gift_refund_id",
        "ALTER TABLE orders ADD COLUMN stripe_gift_refund_id TEXT",
    )
    add_column_if_missing(
        "orders",
        "recipient_sms_sent_at",
        "ALTER TABLE orders ADD COLUMN recipient_sms_sent_at TEXT",
    )
    add_column_if_missing(
        "orders",
        "sender_sms_sent_at",
        "ALTER TABLE orders ADD COLUMN sender_sms_sent_at TEXT",
    )
    add_column_if_missing(
        "orders",
        "recipient_sms_sid",
        "ALTER TABLE orders ADD COLUMN recipient_sms_sid TEXT",
    )
    add_column_if_missing(
        "orders",
        "sender_sms_sid",
        "ALTER TABLE orders ADD COLUMN sender_sms_sid TEXT",
    )


init_db()


# =========================================================
# HELPERS
# =========================================================

def now_dt() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_dt().isoformat()


def parse_iso(value: Optional[str]) -> Optional[datetime]:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        return None


def gift_refund_deadline_iso() -> str:
    return (now_dt() + timedelta(days=GIFT_REFUND_DAYS)).isoformat()


def safe_text(v: str) -> str:
    return html.escape(str(v or "").strip())


def safe_attr(v: str) -> str:
    return html.escape(str(v or "").strip(), quote=True)


def money(v: float) -> str:
    return f"{float(v):.2f}"


def format_amount_display(value) -> str:
    try:
        return f"{float(value):.2f} €".replace(".", ",")
    except Exception:
        return "0,00 €"


def normalize_phone(p: str) -> str:
    raw = str(p or "").strip()
    raw = raw.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if raw.startswith("00"):
        raw = raw[2:]
    if raw.startswith("+"):
        raw = raw[1:]
    digits = "".join(ch for ch in raw if ch.isdigit())
    return digits


def whatsapp_link(phone: str, message: str) -> str:
    normalized = normalize_phone(phone)
    if not normalized:
        return "#"
    return f"https://wa.me/{normalized}?text={urllib.parse.quote(message)}"


def new_order_id() -> str:
    return uuid.uuid4().hex[:12]


def new_token() -> str:
    return secrets.token_urlsafe(24)


def detect_video_extension(upload: UploadFile) -> str:
    content_type = (upload.content_type or "").lower().strip()
    filename = (upload.filename or "").lower().strip()

    if filename.endswith(".mp4") or content_type == "video/mp4":
        return "mp4"
    return "webm"


def reaction_video_path(order_id: str, extension: str = "webm") -> str:
    extension = (extension or "webm").lower().strip()
    if extension not in {"webm", "mp4"}:
        extension = "webm"
    return str(VIDEO_FOLDER / f"{order_id}.{extension}")


def guess_media_type_from_path(path: str) -> str:
    media_type, _ = mimetypes.guess_type(path)
    return media_type or "application/octet-stream"


def guess_media_type_from_url(url: str) -> str:
    raw = (url or "").split("?")[0].lower()
    if raw.endswith(".webm"):
        return "video/webm"
    if raw.endswith(".mp4"):
        return "video/mp4"
    return "video/mp4"


def r2_enabled() -> bool:
    return all([R2_ACCESS_KEY, R2_SECRET_KEY, R2_BUCKET, R2_ENDPOINT, R2_PUBLIC_URL])


def get_r2_client():
    if not r2_enabled():
        return None

    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def upload_video_to_r2(local_path: str, remote_name: str, content_type: str = "video/webm") -> Optional[str]:
    client = get_r2_client()
    if not client:
        return None

    client.upload_file(
        local_path,
        R2_BUCKET,
        remote_name,
        ExtraArgs={"ContentType": content_type},
    )
    return f"{R2_PUBLIC_URL}/{remote_name}"


def insert_asset(order_id: str, asset_type: str, file_url: str, storage_provider: str):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO assets (order_id, asset_type, file_url, storage_provider, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (order_id, asset_type, file_url, storage_provider, now_iso()))
    conn.commit()
    conn.close()


def get_order_by_id(order_id: str):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            o.*,
            s.name AS sender_name,
            s.email AS sender_email,
            s.phone AS sender_phone,
            r.name AS recipient_name,
            r.phone AS recipient_phone
        FROM orders o
        JOIN senders s ON s.id = o.sender_id
        JOIN recipients r ON r.id = o.recipient_id
        WHERE o.id = ?
    """, (order_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    return dict(row)


def get_order_by_recipient_token_or_404(token: str):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            o.*,
            s.name AS sender_name,
            s.email AS sender_email,
            s.phone AS sender_phone,
            r.name AS recipient_name,
            r.phone AS recipient_phone
        FROM orders o
        JOIN senders s ON s.id = o.sender_id
        JOIN recipients r ON r.id = o.recipient_id
        WHERE o.recipient_token = ?
    """, (token,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Experiencia no encontrada")
    return dict(row)


def get_order_by_sender_token_or_404(token: str):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            o.*,
            s.name AS sender_name,
            s.email AS sender_email,
            s.phone AS sender_phone,
            r.name AS recipient_name,
            r.phone AS recipient_phone
        FROM orders o
        JOIN senders s ON s.id = o.sender_id
        JOIN recipients r ON r.id = o.recipient_id
        WHERE o.sender_token = ?
    """, (token,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Sender pack no encontrado")
    return dict(row)


def update_order(order_id: str, **fields):
    if not fields:
        return

    fields["updated_at"] = now_iso()
    columns = ", ".join([f"{k} = ?" for k in fields.keys()])
    values = list(fields.values()) + [order_id]

    conn = db_conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE orders SET {columns} WHERE id = ?", values)
    conn.commit()
    conn.close()


def reaction_exists(order: dict) -> bool:
    if order.get("reaction_video_public_url"):
        return True
    local_path = order.get("reaction_video_local")
    return bool(local_path) and os.path.exists(local_path)


def sender_pack_url_from_order(order: dict) -> str:
    return f"{PUBLIC_BASE_URL}/sender/{order['sender_token']}"


def recipient_experience_url_from_order(order: dict) -> str:
    return f"{PUBLIC_BASE_URL}/pedido/{order['recipient_token']}"


def get_assets_count() -> int:
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM assets")
    row = cur.fetchone()
    conn.close()
    return int(row["c"])


def get_orders_count() -> int:
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM orders")
    row = cur.fetchone()
    conn.close()
    return int(row["c"])


def build_recipient_message(order: dict) -> str:
    return (
        "ETERNA 💙\n\n"
        "Tienes algo que ver...\n\n"
        f"👉 {recipient_experience_url_from_order(order)}"
    )


def build_sender_ready_message(order: dict) -> str:
    return (
        "Tu ETERNA ha vuelto 💙\n\n"
        "Mira lo que provocaste...\n\n"
        f"👉 {sender_pack_url_from_order(order)}"
    )


def calculate_fees(gift_amount: float) -> dict:
    gift_amount = max(0.0, round(float(gift_amount or 0), 2))
    fixed_fee = round(FIXED_PLATFORM_FEE, 2)
    variable_fee = round(gift_amount * GIFT_COMMISSION_RATE, 2)
    total_fee = round(fixed_fee + variable_fee, 2)
    total_amount = round(BASE_PRICE + gift_amount + total_fee, 2)
    return {
        "gift_amount": gift_amount,
        "fixed_fee": fixed_fee,
        "variable_fee": variable_fee,
        "total_fee": total_fee,
        "total_amount": total_amount,
    }


def twilio_enabled() -> bool:
    return bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER)


def to_e164(phone: str) -> str:
    normalized = normalize_phone(phone)
    if not normalized:
        return ""
    return f"+{normalized}"


def send_sms(phone: str, message: str) -> Optional[str]:
    to_phone = to_e164(phone)

    if not to_phone:
        log_info("SMS skipped", "invalid phone")
        return None

    if not twilio_enabled():
        log_info("SMS skipped", "twilio not configured")
        return None

    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        sms = client.messages.create(
            body=message,
            from_=TWILIO_FROM_NUMBER,
            to=to_phone,
        )
        log_info("SMS sent", {
            "to": to_phone,
            "sid": sms.sid,
            "status": sms.status,
        })
        return sms.sid
    except Exception as e:
        log_error("Twilio SMS error", e)
        return None


def try_send_recipient_sms(order: dict) -> Optional[str]:
    if order.get("recipient_sms_sent_at"):
        return order.get("recipient_sms_sid")

    sms_sid = send_sms(
        order.get("recipient_phone", ""),
        build_recipient_message(order),
    )

    if sms_sid:
        update_order(
            order["id"],
            recipient_sms_sent_at=now_iso(),
            recipient_sms_sid=sms_sid,
        )

    return sms_sid


def try_send_sender_sms(order: dict) -> Optional[str]:
    if order.get("sender_sms_sent_at"):
        return order.get("sender_sms_sid")

    sms_sid = send_sms(
        order.get("sender_phone", ""),
        build_sender_ready_message(order),
    )

    if sms_sid:
        update_order(
            order["id"],
            sender_sms_sent_at=now_iso(),
            sender_sms_sid=sms_sid,
            sender_notified=1,
        )

    return sms_sid


def try_acquire_transfer_lock(order_id: str) -> bool:
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE orders
        SET transfer_in_progress = 1, updated_at = ?
        WHERE id = ?
          AND transfer_in_progress = 0
          AND transfer_completed = 0
          AND gift_refunded = 0
    """, (now_iso(), order_id))
    conn.commit()
    acquired = cur.rowcount > 0
    conn.close()
    return acquired


def release_transfer_lock(order_id: str):
    update_order(order_id, transfer_in_progress=0)


def compute_cashout_status(order: dict) -> str:
    gift_amount = float(order.get("gift_amount") or 0)

    if bool(order.get("gift_refunded")):
        return "gift_refunded"

    if gift_amount <= 0 and bool(order.get("cashout_completed")):
        return "completed"

    if gift_amount > 0 and bool(order.get("transfer_completed")):
        return "completed"

    if bool(order.get("transfer_in_progress")):
        return "verifying"

    if gift_amount > 0 and bool(order.get("connect_onboarding_completed")):
        return "ready_to_finalize"

    return "pending"


def try_start_experience(order_id: str) -> str:
    conn = db_conn()
    cur = conn.cursor()

    cur.execute("""
        UPDATE orders
        SET experience_started = 1,
            delivered_to_recipient = 1,
            updated_at = ?
        WHERE id = ?
          AND paid = 1
          AND experience_started = 0
          AND experience_completed = 0
    """, (now_iso(), order_id))

    conn.commit()
    changed = cur.rowcount
    conn.close()

    if changed > 0:
        return "started"

    refreshed = get_order_by_id(order_id)
    if not bool(refreshed.get("paid")):
        return "not_paid"
    if bool(refreshed.get("experience_completed")):
        return "already_completed"
    if bool(refreshed.get("experience_started")):
        return "already_started"
    return "blocked"


# =========================================================
# STRIPE CONNECT HELPERS
# =========================================================

def get_or_create_connected_account(order: dict) -> str:
    existing = (order.get("stripe_connected_account_id") or "").strip()
    if existing:
        return existing

    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe no configurado")

    account = stripe.Account.create(
        type="express",
        country="ES",
        capabilities={
            "transfers": {"requested": True},
        },
        metadata={
            "order_id": order["id"],
            "recipient_name": order.get("recipient_name", ""),
        },
    )

    update_order(order["id"], stripe_connected_account_id=account.id)
    return account.id


def create_connect_onboarding_link(order: dict) -> str:
    account_id = get_or_create_connected_account(order)

    link = stripe.AccountLink.create(
        account=account_id,
        refresh_url=f"{PUBLIC_BASE_URL}/connect/refresh/{order['recipient_token']}",
        return_url=f"{PUBLIC_BASE_URL}/connect/return/{order['recipient_token']}",
        type="account_onboarding",
    )
    return link.url


def refresh_connect_status(order: dict) -> bool:
    account_id = (order.get("stripe_connected_account_id") or "").strip()
    if not account_id:
        return False

    acct = stripe.Account.retrieve(account_id)

    ready = bool(acct.get("details_submitted")) and (
        acct.get("capabilities", {}).get("transfers") == "active"
    )

    update_order(
        order["id"],
        connect_onboarding_completed=1 if ready else 0,
    )

    return ready


def process_gift_transfer_for_order(order: dict) -> dict:
    order = get_order_by_id(order["id"])
    gift_amount = float(order.get("gift_amount") or 0)

    if bool(order.get("gift_refunded")):
        return {"status": "gift_already_refunded"}

    if gift_amount <= 0:
        update_order(
            order["id"],
            transfer_completed=1,
            cashout_completed=1,
            transfer_in_progress=0,
        )
        return {"status": "no_gift"}

    if not STRIPE_SECRET_KEY:
        update_order(
            order["id"],
            transfer_completed=1,
            cashout_completed=1,
            connect_onboarding_completed=1,
            transfer_in_progress=0,
        )
        return {"status": "stripe_disabled_test_mode"}

    if not bool(order.get("paid")):
        return {"status": "not_paid"}

    if not bool(order.get("experience_completed")):
        return {"status": "experience_not_completed"}

    if not bool(order.get("connect_onboarding_completed")):
        return {"status": "onboarding_not_ready"}

    if order.get("stripe_transfer_id"):
        if not bool(order.get("transfer_completed")) or not bool(order.get("cashout_completed")):
            update_order(
                order["id"],
                transfer_completed=1,
                cashout_completed=1,
                transfer_in_progress=0,
            )
        return {"status": "already_transferred", "transfer_id": order.get("stripe_transfer_id")}

    destination = (order.get("stripe_connected_account_id") or "").strip()
    if not destination:
        return {"status": "missing_destination"}

    if not try_acquire_transfer_lock(order["id"]):
        refreshed = get_order_by_id(order["id"])
        if refreshed.get("stripe_transfer_id"):
            return {"status": "already_transferred", "transfer_id": refreshed.get("stripe_transfer_id")}
        if bool(refreshed.get("gift_refunded")):
            return {"status": "gift_already_refunded"}
        if bool(refreshed.get("transfer_in_progress")):
            return {"status": "transfer_in_progress"}
        return {"status": "lock_not_acquired"}

    try:
        transfer = stripe.Transfer.create(
            amount=int(round(gift_amount * 100)),
            currency=CURRENCY,
            destination=destination,
            metadata={
                "order_id": order["id"],
                "type": "eterna_gift_transfer",
            },
            transfer_group=f"ETERNA_ORDER_{order['id']}",
        )

        update_order(
            order["id"],
            stripe_transfer_id=transfer.id,
            transfer_completed=1,
            cashout_completed=1,
            transfer_in_progress=0,
        )

        return {"status": "ok", "transfer_id": transfer.id}
    except Exception as e:
        log_error("Transfer error", e)
        release_transfer_lock(order["id"])
        return {"status": "error", "error": str(e)}


def process_expired_gift_refunds() -> dict:
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id
        FROM orders
        WHERE paid = 1
          AND gift_amount > 0
          AND transfer_completed = 0
          AND gift_refunded = 0
          AND stripe_gift_refund_id IS NULL
          AND gift_refund_deadline_at IS NOT NULL
    """)
    rows = cur.fetchall()
    conn.close()

    checked = 0
    refunded = 0
    skipped = 0
    errors = 0
    now = now_dt()

    for row in rows:
        checked += 1
        order = get_order_by_id(row["id"])
        deadline = parse_iso(order.get("gift_refund_deadline_at"))

        if deadline is None or deadline > now:
            skipped += 1
            continue

        if bool(order.get("transfer_completed")) or bool(order.get("gift_refunded")):
            skipped += 1
            continue

        if order.get("stripe_transfer_id"):
            skipped += 1
            continue

        payment_intent_id = (order.get("stripe_payment_intent_id") or "").strip()
        gift_amount = float(order.get("gift_amount") or 0)

        if gift_amount <= 0:
            update_order(order["id"], gift_refunded=1)
            skipped += 1
            continue

        try:
            if STRIPE_SECRET_KEY and payment_intent_id:
                refund = stripe.Refund.create(
                    payment_intent=payment_intent_id,
                    amount=int(round(gift_amount * 100)),
                    metadata={
                        "order_id": order["id"],
                        "type": "eterna_gift_partial_refund",
                    },
                )
                update_order(
                    order["id"],
                    gift_refunded=1,
                    stripe_gift_refund_id=refund.id,
                    transfer_in_progress=0,
                    cashout_completed=0,
                )
            else:
                update_order(
                    order["id"],
                    gift_refunded=1,
                    stripe_gift_refund_id="test_no_stripe_refund",
                    transfer_in_progress=0,
                    cashout_completed=0,
                )

            refunded += 1
        except Exception as e:
            log_error(f"Gift refund error {order['id']}", e)
            errors += 1

    return {
        "checked": checked,
        "refunded": refunded,
        "skipped": skipped,
        "errors": errors,
    }


# =========================================================
# CREATE FORM
# =========================================================

def render_create_form() -> str:
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Crear ETERNA</title>
        <style>
            * {{ box-sizing: border-box; }}
            html, body {{ margin: 0; min-height: 100%; background: #000; }}
            body {{
                min-height: 100vh;
                background:
                    radial-gradient(circle at top, rgba(255,255,255,0.08), transparent 30%),
                    linear-gradient(180deg, #050505 0%, #000000 100%);
                color: white;
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 24px;
            }}
            .card {{
                width: 100%;
                max-width: 760px;
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 24px;
                padding: 28px;
            }}
            h1 {{
                margin: 0 0 10px 0;
                font-size: 38px;
                letter-spacing: 2px;
                text-align: center;
            }}
            .subtitle {{
                text-align: center;
                color: rgba(255,255,255,0.75);
                margin-bottom: 26px;
                line-height: 1.5;
            }}
            .section-title {{
                margin: 20px 0 10px 0;
                font-size: 14px;
                text-transform: uppercase;
                letter-spacing: 1.5px;
                color: rgba(255,255,255,0.65);
            }}
            input {{
                width: 100%;
                padding: 14px 16px;
                margin: 8px 0;
                border-radius: 14px;
                border: 1px solid rgba(255,255,255,0.10);
                background: rgba(255,255,255,0.06);
                color: white;
                outline: none;
                font-size: 15px;
            }}
            input::placeholder {{
                color: rgba(255,255,255,0.45);
            }}
            .hint {{
                margin-top: 8px;
                font-size: 13px;
                color: rgba(255,255,255,0.5);
                line-height: 1.6;
            }}
            .buttons {{
                display: grid;
                gap: 12px;
                margin-top: 22px;
            }}
            button, .ghost {{
                width: 100%;
                padding: 16px 22px;
                border-radius: 999px;
                border: 0;
                font-weight: bold;
                font-size: 15px;
                cursor: pointer;
                text-decoration: none;
                text-align: center;
                display: inline-block;
            }}
            button {{
                background: white;
                color: black;
            }}
            button[disabled] {{
                opacity: 0.7;
                cursor: not-allowed;
            }}
            .ghost {{
                background: rgba(255,255,255,0.10);
                color: white;
                border: 1px solid rgba(255,255,255,0.10);
            }}
            .price-box {{
                margin-top: 12px;
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 16px;
                padding: 14px 16px;
                font-size: 14px;
                line-height: 1.8;
                color: rgba(255,255,255,0.82);
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>CREAR ETERNA</h1>

            <div class="subtitle">
                Hay momentos que merecen quedarse para siempre
            </div>

            <form action="/crear" method="post" id="createForm">
                <div class="section-title">Tus datos</div>
                <input name="customer_name" placeholder="Tu nombre" required>
                <input name="customer_email" type="email" placeholder="Tu email">
                <input name="customer_phone" placeholder="Tu teléfono / SMS" required>

                <div class="section-title">Persona que recibe</div>
                <input name="recipient_name" placeholder="Nombre de la persona" required>
                <input name="recipient_phone" placeholder="Teléfono / SMS de la persona" required>

                <div class="section-title">Las 3 frases</div>
                <input name="phrase_1" placeholder="Frase 1" required maxlength="160">
                <input name="phrase_2" placeholder="Frase 2" required maxlength="160">
                <input name="phrase_3" placeholder="Frase 3" required maxlength="160">

                <div class="section-title">Dinero a regalar</div>
                <input
                    name="gift_amount"
                    placeholder="Dinero a regalar (€)"
                    type="number"
                    step="0.01"
                    min="0"
                    value="0"
                    required
                >

                <div class="price-box">
                    Precio base ETERNA: {money(BASE_PRICE)}€<br>
                    Comisión regalo: {money(FIXED_PLATFORM_FEE)}€ + {(GIFT_COMMISSION_RATE * 100):.0f}% del importe regalado
                </div>

                <div class="hint">
                    Ejemplo: si regalas 100€, pagarás 100€ + {money(FIXED_PLATFORM_FEE)}€ + 5%.
                </div>

                <div class="buttons">
                    <button type="submit" id="submitBtn">CONTINUAR</button>
                    <a class="ghost" href="/">Volver</a>
                </div>
            </form>
        </div>

        <script>
            document.addEventListener("DOMContentLoaded", function () {{
                const form = document.getElementById("createForm");
                const button = document.getElementById("submitBtn");

                form.addEventListener("submit", function () {{
                    button.disabled = true;
                    button.textContent = "Procesando...";
                }});
            }});
        </script>
    </body>
    </html>
    """


def create_order_and_redirect(
    customer_name: str,
    customer_email: str,
    customer_phone: str,
    recipient_name: str,
    recipient_phone: str,
    phrase_1: str,
    phrase_2: str,
    phrase_3: str,
    gift_amount: float,
):
    customer_name = (customer_name or "").strip()
    customer_email = (customer_email or "").strip()
    recipient_name = (recipient_name or "").strip()

    phrase_1 = (phrase_1 or "").strip()
    phrase_2 = (phrase_2 or "").strip()
    phrase_3 = (phrase_3 or "").strip()

    if not customer_name:
        raise HTTPException(status_code=400, detail="Tu nombre es obligatorio")

    if not recipient_name:
        raise HTTPException(status_code=400, detail="El nombre del destinatario es obligatorio")

    if not phrase_1 or not phrase_2 or not phrase_3:
        raise HTTPException(status_code=400, detail="Las 3 frases son obligatorias")

    if len(phrase_1) > 160 or len(phrase_2) > 160 or len(phrase_3) > 160:
        raise HTTPException(status_code=400, detail="Las frases son demasiado largas")

    try:
        gift_amount = round(float(gift_amount or 0), 2)
    except Exception:
        raise HTTPException(status_code=400, detail="Importe no válido")

    if gift_amount < 0:
        raise HTTPException(status_code=400, detail="Importe no válido")

    sender_phone = normalize_phone(customer_phone)
    recipient_phone_norm = normalize_phone(recipient_phone)

    if not sender_phone or not recipient_phone_norm:
        raise HTTPException(status_code=400, detail="Teléfono no válido")

    order_id = new_order_id()
    recipient_token = new_token()
    sender_token = new_token()

    fees = calculate_fees(gift_amount)
    created_at = now_iso()

    conn = db_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO senders (name, email, phone, created_at)
        VALUES (?, ?, ?, ?)
    """, (
        customer_name,
        customer_email,
        sender_phone,
        created_at,
    ))
    sender_id = cur.lastrowid

    cur.execute("""
        INSERT INTO recipients (name, phone, created_at)
        VALUES (?, ?, ?)
    """, (
        recipient_name,
        recipient_phone_norm,
        created_at,
    ))
    recipient_id = cur.lastrowid

    placeholders = ", ".join(["?"] * 40)

    cur.execute(f"""
        INSERT INTO orders (
            id, sender_id, recipient_id,
            phrase_1, phrase_2, phrase_3,
            gift_amount, platform_fixed_fee, platform_variable_fee, platform_total_fee, total_amount,
            paid, delivered_to_recipient, reaction_uploaded, cashout_completed, transfer_completed,
            transfer_in_progress, sender_notified, experience_started, experience_completed, connect_onboarding_completed,
            gift_refunded,
            stripe_session_id, stripe_payment_status, stripe_payment_intent_id, stripe_connected_account_id, stripe_transfer_id, stripe_gift_refund_id,
            recipient_token, sender_token,
            reaction_video_local, reaction_video_public_url, gift_video_url,
            gift_refund_deadline_at,
            recipient_sms_sent_at, sender_sms_sent_at,
            recipient_sms_sid, sender_sms_sid,
            created_at, updated_at
        )
        VALUES ({placeholders})
    """, (
        order_id, sender_id, recipient_id,
        phrase_1, phrase_2, phrase_3,
        fees["gift_amount"],
        fees["fixed_fee"],
        fees["variable_fee"],
        fees["total_fee"],
        fees["total_amount"],
        0, 0, 0, 0, 0,
        0, 0, 0, 0, 0,
        0,
        None, None, None, None, None, None,
        recipient_token, sender_token,
        None, None, DEFAULT_GIFT_VIDEO_URL or None,
        None,
        None, None,
        None, None,
        created_at, created_at
    ))

    conn.commit()
    conn.close()

    if not STRIPE_SECRET_KEY:
        update_order(
            order_id,
            paid=1,
            stripe_payment_status="test_no_stripe",
            gift_refund_deadline_at=gift_refund_deadline_iso(),
        )
        order = get_order_by_id(order_id)
        try_send_recipient_sms(order)
        return RedirectResponse(url=f"/post-pago/{order_id}", status_code=303)

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": CURRENCY,
                        "product_data": {
                            "name": "ETERNA",
                            "description": (
                                f"Base {money(BASE_PRICE)}€ + "
                                f"regalo {money(fees['gift_amount'])}€ + "
                                f"comisión {money(fees['total_fee'])}€"
                            ),
                        },
                        "unit_amount": int(round(fees["total_amount"] * 100)),
                    },
                    "quantity": 1,
                }
            ],
            success_url=f"{PUBLIC_BASE_URL}/checkout-exito/{order_id}",
            cancel_url=f"{PUBLIC_BASE_URL}/crear",
            client_reference_id=order_id,
            metadata={"order_id": order_id},
        )
        update_order(order_id, stripe_session_id=session.id, stripe_payment_status="created")
        return RedirectResponse(url=session.url, status_code=303)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando checkout Stripe: {e}")


# =========================================================
# HOME / CREAR
# =========================================================

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
            * { box-sizing: border-box; }
            html, body { margin: 0; min-height: 100%; background: #000; }
            body {
                min-height: 100vh;
                background:
                    radial-gradient(circle at top, rgba(255,255,255,0.08), transparent 30%),
                    linear-gradient(180deg, #050505 0%, #000000 100%);
                color: white;
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 24px;
            }
            .card {
                width: 100%;
                max-width: 760px;
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 28px;
                padding: 42px 30px;
                text-align: center;
            }
            h1 {
                margin: 0 0 10px 0;
                font-size: 48px;
                letter-spacing: 3px;
            }
            .subtitle {
                color: rgba(255,255,255,0.80);
                font-size: 20px;
                line-height: 1.8;
                margin-top: 18px;
            }
            .soft {
                margin-top: 24px;
                color: rgba(255,255,255,0.50);
                font-size: 15px;
                line-height: 1.7;
            }
            .buttons {
                display: grid;
                gap: 14px;
                margin-top: 30px;
            }
            .btn {
                width: 100%;
                padding: 18px 24px;
                border-radius: 999px;
                border: 0;
                font-weight: bold;
                font-size: 16px;
                cursor: pointer;
                text-decoration: none;
                text-align: center;
                display: inline-block;
                background: white;
                color: black;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>ETERNA</h1>
            <div class="subtitle">
                Hay momentos que merecen quedarse para siempre
            </div>
            <div class="soft">
                No es un vídeo. Es un momento.
            </div>
            <div class="buttons">
                <a class="btn" href="/crear">CREAR MI ETERNA</a>
            </div>
        </div>
    </body>
    </html>
    """


@app.get("/crear", response_class=HTMLResponse)
def crear_get():
    return render_create_form()


@app.post("/crear")
def crear_post(
    customer_name: str = Form(...),
    customer_email: str = Form(""),
    customer_phone: str = Form(...),
    recipient_name: str = Form(...),
    recipient_phone: str = Form(...),
    phrase_1: str = Form(...),
    phrase_2: str = Form(...),
    phrase_3: str = Form(...),
    gift_amount: float = Form(0),
):
    return create_order_and_redirect(
        customer_name=customer_name,
        customer_email=customer_email,
        customer_phone=customer_phone,
        recipient_name=recipient_name,
        recipient_phone=recipient_phone,
        phrase_1=phrase_1,
        phrase_2=phrase_2,
        phrase_3=phrase_3,
        gift_amount=gift_amount,
    )


@app.post("/crear-eterna")
def crear_eterna_legacy(
    customer_name: str = Form(...),
    customer_email: str = Form(""),
    customer_phone: str = Form(...),
    recipient_name: str = Form(...),
    recipient_phone: str = Form(...),
    phrase_1: str = Form(...),
    phrase_2: str = Form(...),
    phrase_3: str = Form(...),
    gift_amount: float = Form(0),
):
    return create_order_and_redirect(
        customer_name=customer_name,
        customer_email=customer_email,
        customer_phone=customer_phone,
        recipient_name=recipient_name,
        recipient_phone=recipient_phone,
        phrase_1=phrase_1,
        phrase_2=phrase_2,
        phrase_3=phrase_3,
        gift_amount=gift_amount,
    )


# =========================================================
# CHECKOUT / WEBHOOK STRIPE
# =========================================================

@app.get("/checkout-exito/{order_id}", response_class=HTMLResponse)
def checkout_exito(order_id: str):
    order = get_order_by_id(order_id)
    is_paid = bool(order["paid"])

    refresh = '<meta http-equiv="refresh" content="9">' if not is_paid else ""
    redirect_script = f"""
        setTimeout(function() {{
            window.location.href = "/post-pago/{safe_attr(order_id)}";
        }}, 8000);
    """ if is_paid else ""

    fallback_link = f"""
        <div class="soft">
            Si esta página no avanza sola,
            <a href="/post-pago/{safe_attr(order_id)}" style="color:white;">pulsa aquí</a>
        </div>
    """

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        {refresh}
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ETERNA</title>
        <style>
            html, body {{
                margin: 0;
                min-height: 100%;
                background: #000;
            }}
            body {{
                min-height: 100vh;
                background:
                    radial-gradient(circle at top, rgba(255,255,255,0.08), transparent 30%),
                    linear-gradient(180deg, #050505 0%, #000000 100%);
                color: white;
                font-family: Arial, sans-serif;
                display: flex;
                align-items: center;
                justify-content: center;
                text-align: center;
                padding: 24px;
            }}
            .card {{
                max-width: 680px;
                opacity: 0;
                transform: translateY(10px);
                animation: fadeIn 1.6s ease forwards;
            }}
            h1 {{
                font-size: 42px;
                margin-bottom: 18px;
                letter-spacing: 2px;
            }}
            .text {{
                font-size: 20px;
                line-height: 1.8;
                color: rgba(255,255,255,0.85);
            }}
            .soft {{
                margin-top: 24px;
                font-size: 14px;
                color: rgba(255,255,255,0.4);
            }}
            @keyframes fadeIn {{
                to {{
                    opacity: 1;
                    transform: translateY(0);
                }}
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Todo ya está en camino</h1>
            <div class="text">
                En unos instantes,<br>
                alguien va a vivir algo que no espera
            </div>
            {fallback_link}
        </div>

        <script>
            {redirect_script}
        </script>
    </body>
    </html>
    """


@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not STRIPE_WEBHOOK_SECRET and STRIPE_SECRET_KEY:
        raise HTTPException(status_code=400, detail="Webhook secret no configurado")

    try:
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=sig_header,
                secret=STRIPE_WEBHOOK_SECRET,
            )
        else:
            event = json.loads(payload.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook inválido: {e}")

    event_type = event.get("type")

    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        order_id = session.get("metadata", {}).get("order_id") or session.get("client_reference_id")

        if order_id:
            try:
                existing = get_order_by_id(order_id)
            except HTTPException:
                return {"received": True}

            update_order(
                order_id,
                paid=1,
                stripe_payment_status="paid",
                stripe_session_id=session.get("id"),
                stripe_payment_intent_id=session.get("payment_intent"),
                gift_refund_deadline_at=existing.get("gift_refund_deadline_at") or gift_refund_deadline_iso(),
            )

            try:
                updated = get_order_by_id(order_id)
                try_send_recipient_sms(updated)
            except Exception as e:
                log_error("Recipient SMS after payment", e)

    return {"received": True}


# =========================================================
# POST PAGO / RESUMEN
# =========================================================

@app.get("/post-pago/{order_id}")
def post_pago(order_id: str):
    order = get_order_by_id(order_id)

    if not order["paid"]:
        return RedirectResponse(url=f"/checkout-exito/{order_id}", status_code=303)

    return RedirectResponse(url=f"/resumen/{order_id}", status_code=303)


@app.get("/resumen/{order_id}", response_class=HTMLResponse)
def resumen(order_id: str):
    order = get_order_by_id(order_id)

    sender_pack_url = sender_pack_url_from_order(order)
    reaction_ready = reaction_exists(order)

    recipient_sms_message = build_recipient_message(order)

    if reaction_ready:
        status_line = "Lo que creaste… volvió a ti"
        soft_line = "Tu enlace privado ya está listo."
        main_button = f"""
            <a href="{safe_attr(sender_pack_url)}" target="_blank" rel="noopener noreferrer">
                <button class="primary">Abrir mi ETERNA</button>
            </a>
        """
        extra_block = f"""
            <div class="private-link-box">
                <div class="private-link-label">Enlace privado</div>
                <div class="private-link-url">{safe_text(sender_pack_url)}</div>
            </div>
        """
        estado_texto = "Volvió a ti"
    else:
        sms_url = f"sms:{safe_attr(to_e164(order['recipient_phone']))}?&body={safe_attr(recipient_sms_message)}"
        status_line = "Tu ETERNA está lista"
        soft_line = "Si Twilio está configurado, el SMS se enviará automáticamente tras el pago."
        main_button = f"""
            <a href="{sms_url}">
                <button class="primary">Abrir SMS manual</button>
            </a>
        """
        extra_block = f"""
            <div class="private-link-box">
                <div class="private-link-label">Enlace de la experiencia</div>
                <div class="private-link-url">{safe_text(recipient_experience_url_from_order(order))}</div>
            </div>
        """
        estado_texto = "Pendiente de vivir"

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta http-equiv="refresh" content="8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Resumen ETERNA</title>
        <style>
            * {{ box-sizing: border-box; }}
            html, body {{ margin: 0; min-height: 100%; background: #000; }}
            body {{
                min-height: 100vh;
                background:
                    radial-gradient(circle at top, rgba(255,255,255,0.08), transparent 30%),
                    linear-gradient(180deg, #050505 0%, #000000 100%);
                color: white;
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 24px;
            }}
            .card {{
                width: 100%;
                max-width: 760px;
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 24px;
                padding: 32px 28px;
                text-align: center;
            }}
            .stats {{
                display: grid;
                gap: 12px;
                margin-top: 24px;
            }}
            .stat {{
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: 16px;
                padding: 16px;
            }}
            .label {{
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 1.2px;
                color: rgba(255,255,255,0.5);
            }}
            .value {{
                font-size: 22px;
                font-weight: bold;
                margin-top: 6px;
            }}
            .buttons {{
                display: grid;
                gap: 14px;
                margin-top: 28px;
            }}
            button {{
                width: 100%;
                padding: 16px 22px;
                border-radius: 999px;
                border: 0;
                font-weight: bold;
                font-size: 15px;
                cursor: pointer;
            }}
            .primary {{
                background: white;
                color: black;
            }}
            a {{ text-decoration: none; }}
            .private-link-box {{
                margin-top: 18px;
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 16px;
                padding: 16px;
                text-align: left;
                word-break: break-word;
            }}
            .private-link-label {{
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 1.2px;
                color: rgba(255,255,255,0.5);
                margin-bottom: 8px;
            }}
            .private-link-url {{
                color: rgba(255,255,255,0.88);
                font-size: 14px;
                line-height: 1.6;
            }}
            .soft {{
                margin-top: 14px;
                color: rgba(255,255,255,0.45);
                font-size: 13px;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>{safe_text(status_line)}</h1>

            <div class="stats">
                <div class="stat">
                    <div class="label">Regalo</div>
                    <div class="value">{money(order["gift_amount"])}€</div>
                </div>
                <div class="stat">
                    <div class="label">Comisión</div>
                    <div class="value">{money(order["platform_total_fee"])}€</div>
                </div>
                <div class="stat">
                    <div class="label">Total</div>
                    <div class="value">{money(order["total_amount"])}€</div>
                </div>
                <div class="stat">
                    <div class="label">Estado</div>
                    <div class="value">{safe_text(estado_texto)}</div>
                </div>
            </div>

            <div class="buttons">
                {main_button}
            </div>

            {extra_block}

            <div class="soft">{safe_text(soft_line)}</div>
        </div>
    </body>
    </html>
    """


# =========================================================
# START EXPERIENCE LOCK
# =========================================================

@app.post("/start-experience")
def start_experience(recipient_token: str = Form(...)):
    order = get_order_by_recipient_token_or_404(recipient_token)
    result = try_start_experience(order["id"])

    if result == "not_paid":
        raise HTTPException(status_code=403, detail="Pedido no pagado")

    if result == "already_completed":
        return JSONResponse({
            "status": "already_completed",
            "redirect_url": f"/preview-emocion/{recipient_token}",
        })

    if result in {"already_started", "blocked"}:
        return JSONResponse({
            "status": "already_started",
            "redirect_url": f"/bloqueado/{recipient_token}",
        })

    return JSONResponse({"status": "ok"})


# =========================================================
# BLOQUEO SEGUNDA ENTRADA
# =========================================================

@app.get("/bloqueado/{recipient_token}", response_class=HTMLResponse)
def bloqueado(recipient_token: str):
    order = get_order_by_recipient_token_or_404(recipient_token)

    if bool(order.get("experience_completed")):
        return RedirectResponse(url=f"/preview-emocion/{recipient_token}", status_code=303)

    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ETERNA</title>
        <style>
            html, body {
                margin: 0;
                min-height: 100%;
                background: #000;
            }
            body {
                min-height: 100vh;
                background:
                    radial-gradient(circle at top, rgba(255,255,255,0.08), transparent 35%),
                    linear-gradient(180deg, #050505 0%, #000000 100%);
                color: white;
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 24px;
                text-align: center;
            }
            .card {
                width: 100%;
                max-width: 760px;
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 28px;
                padding: 40px 28px;
            }
            h1 {
                margin: 0 0 16px 0;
                font-size: 38px;
            }
            .lead {
                font-size: 18px;
                color: rgba(255,255,255,0.82);
                line-height: 1.8;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Esta ETERNA ya empezó</h1>
            <div class="lead">
                Esta experiencia solo puede vivirse una vez.
            </div>
        </div>
    </body>
    </html>
    """


# =========================================================
# EXPERIENCIA DEL REGALADO
# =========================================================

@app.get("/pedido/{recipient_token}", response_class=HTMLResponse)
def pedido(recipient_token: str):
    order = get_order_by_recipient_token_or_404(recipient_token)

    if not order["paid"]:
        return HTMLResponse("""
        <!DOCTYPE html>
        <html lang="es">
        <body style="background:#000;color:white;text-align:center;padding-top:100px;font-family:Arial;">
            <h1>Esta ETERNA aún no está disponible</h1>
        </body>
        </html>
        """)

    if bool(order.get("experience_completed")):
        return RedirectResponse(url=f"/preview-emocion/{recipient_token}", status_code=303)

    phrase_1 = safe_text(order["phrase_1"])
    phrase_2 = safe_text(order["phrase_2"])
    phrase_3 = safe_text(order["phrase_3"])
    gift_amount = format_amount_display(order["gift_amount"])

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ETERNA</title>
        <style>
            * {{ box-sizing: border-box; }}
            html, body {{
                margin: 0;
                width: 100%;
                min-height: 100%;
                background: #000;
            }}
            body {{
                background: #000;
                color: white;
                font-family: Arial, sans-serif;
                text-align: center;
            }}
            .screen {{
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                flex-direction: column;
                padding: 24px;
            }}
            .hidden {{ display: none; }}
            .gate-card {{
                width: 100%;
                max-width: 700px;
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 28px;
                padding: 40px 30px;
            }}
            .gate-card h1 {{
                font-size: 42px;
                margin: 0 0 18px 0;
            }}
            .lead {{
                max-width: 560px;
                margin: 0 auto;
                color: rgba(255,255,255,0.82);
                font-size: 18px;
                line-height: 1.9;
            }}
            .single {{
                margin-top: 26px;
                font-size: 24px;
                font-weight: bold;
                letter-spacing: 1px;
                color: white;
                opacity: 0;
                animation: fadeIn 1.5s ease forwards, pulse 2.5s ease-in-out infinite;
            }}
            .consent-row {{
                margin-top: 28px;
                display: flex;
                align-items: flex-start;
                justify-content: center;
                gap: 12px;
                color: rgba(255,255,255,0.88);
                font-size: 14px;
                line-height: 1.7;
                cursor: pointer;
                user-select: none;
                text-align: left;
            }}
            .consent-row input {{
                width: 22px;
                height: 22px;
                margin-top: 2px;
                accent-color: #ffffff;
                cursor: pointer;
                flex: 0 0 auto;
            }}
            #startBtn {{
                width: 100%;
                padding: 16px 24px;
                border-radius: 999px;
                border: 0;
                background: white;
                color: black;
                font-weight: bold;
                cursor: pointer;
                margin-top: 22px;
                font-size: 15px;
                opacity: 0.45;
            }}
            #startBtn.enabled {{ opacity: 1; }}
            #content {{
                width: 100%;
                max-width: 920px;
                padding: 24px;
                opacity: 0;
                transform: translateY(12px);
                transition: opacity 0.9s ease, transform 0.9s ease;
            }}
            #content.visible {{
                opacity: 1;
                transform: translateY(0);
            }}
            #content h2 {{
                font-size: 44px;
                line-height: 1.35;
                margin: 0;
                font-weight: 600;
                color: white;
                white-space: pre-line;
            }}
            #content p {{
                color: rgba(255,255,255,0.78);
                margin-top: 16px;
                line-height: 1.7;
                font-size: 18px;
            }}
            #content .amount {{
                margin-top: 20px;
                font-size: 54px;
                font-weight: bold;
                line-height: 1;
            }}
            #statusMsg {{
                margin-top: 20px;
                color: rgba(255,255,255,0.6);
                font-size: 14px;
            }}
            @keyframes fadeIn {{
                to {{
                    opacity: 1;
                    transform: translateY(0);
                }}
            }}
            @keyframes pulse {{
                0% {{ opacity: 0.8; transform: scale(1); }}
                50% {{ opacity: 1; transform: scale(1.02); }}
                100% {{ opacity: 0.8; transform: scale(1); }}
            }}
        </style>
    </head>
    <body>

        <div id="start" class="screen">
            <div class="gate-card">
                <h1>Hay algo para ti</h1>

                <div class="lead">
                    Cuando estés listo, pulsa y déjate llevar.
                </div>

                <div class="single">
                    Esta experiencia solo se vive una vez
                </div>

                <label class="consent-row" for="consentCheck">
                    <input type="checkbox" id="consentCheck" required>
                    <span>
                        Acepto vivir esta experiencia, la grabación de mi reacción y las
                        <a href="/condiciones" target="_blank" style="color:white;">condiciones</a> y
                        <a href="/privacidad" target="_blank" style="color:white;">política de privacidad</a>.
                    </span>
                </label>

                <button id="startBtn" type="button" onclick="startExperience()" disabled>
                    Vivirlo
                </button>
            </div>
        </div>

        <div id="experience" class="screen hidden">
            <div id="content"></div>
            <div id="statusMsg"></div>
        </div>

        <script>
            let recorder = null;
            let chunks = [];
            let currentStream = null;
            let mediaMimeType = "video/webm";
            let uploadStarted = false;
            let experienceStarted = false;

            document.addEventListener("DOMContentLoaded", () => {{
                const consentCheck = document.getElementById("consentCheck");
                const startBtn = document.getElementById("startBtn");

                function updateButton() {{
                    const enabled = consentCheck.checked && !experienceStarted;
                    startBtn.disabled = !enabled;
                    if (enabled) startBtn.classList.add("enabled");
                    else startBtn.classList.remove("enabled");
                }}

                consentCheck.addEventListener("change", updateButton);
                updateButton();
            }});

            function wait(ms) {{
                return new Promise(resolve => setTimeout(resolve, ms));
            }}

            function setStatus(text) {{
                const el = document.getElementById("statusMsg");
                if (el) el.textContent = text || "";
            }}

            async function showScene(scene) {{
                const content = document.getElementById("content");
                content.classList.remove("visible");
                await wait(180);
                content.innerHTML = scene.html || "";
                await wait(40);
                content.classList.add("visible");
                await wait(scene.duration || 2000);
            }}

            async function lockExperienceStart() {{
                const formData = new FormData();
                formData.append("recipient_token", "{safe_attr(order['recipient_token'])}");

                const response = await fetch("/start-experience", {{
                    method: "POST",
                    body: formData
                }});

                const data = await response.json();
                if (data.status === "already_completed" || data.status === "already_started") {{
                    window.location.href = data.redirect_url || "/preview-emocion/{safe_attr(order['recipient_token'])}";
                    return false;
                }}

                return true;
            }}

            async function sendVideo() {{
                try {{
                    if (!chunks.length) return null;

                    const ext = mediaMimeType.includes("mp4") ? "mp4" : "webm";
                    const blob = new Blob(chunks, {{ type: ext === "mp4" ? "video/mp4" : "video/webm" }});
                    if (!blob || blob.size === 0) return null;

                    const formData = new FormData();
                    formData.append("recipient_token", "{safe_attr(order['recipient_token'])}");
                    formData.append("video", blob, "{safe_attr(order['id'])}." + ext);

                    const response = await fetch("/upload-video", {{
                        method: "POST",
                        body: formData
                    }});

                    if (!response.ok) return null;
                    return await response.json();
                }} catch (err) {{
                    return null;
                }}
            }}

            async function stopRecordingAndUpload() {{
                if (uploadStarted) return null;
                uploadStarted = true;

                if (recorder && recorder.state !== "inactive") {{
                    await new Promise((resolve) => {{
                        recorder.onstop = () => resolve();
                        try {{
                            recorder.stop();
                        }} catch (e) {{
                            resolve();
                        }}
                    }});
                }}

                if (currentStream) {{
                    currentStream.getTracks().forEach(track => track.stop());
                    currentStream = null;
                }}

                await wait(500);
                return await sendVideo();
            }}

            async function finishFlow() {{
                setStatus("Guardando este momento…");
                const uploadResult = await stopRecordingAndUpload();

                if (uploadResult && uploadResult.preview_url) {{
                    window.location.href = uploadResult.preview_url;
                    return;
                }}

                window.location.href = "/cobrar/{safe_attr(order['recipient_token'])}";
            }}

            const scenes = [
                {{ html: "<h2>…</h2>", duration: 1200 }},
                {{ html: "<h2>{phrase_1}</h2>", duration: 2200 }},
                {{ html: "<h2>{phrase_2}</h2>", duration: 2200 }},
                {{ html: "<h2>{phrase_3}</h2>", duration: 2200 }},
                {{
                    html: "<h2>Esto también era para ti</h2><p>Alguien ha querido cuidarte de esta manera</p><div class='amount'>{gift_amount}</div>",
                    duration: 5000
                }}
            ];

            async function startExperience() {{
                if (experienceStarted) return;
                experienceStarted = true;

                const startBtn = document.getElementById("startBtn");
                startBtn.disabled = true;

                try {{
                    if (!window.MediaRecorder) {{
                        throw new Error("MediaRecorder no soportado");
                    }}

                    const stream = await navigator.mediaDevices.getUserMedia({{
                        video: {{ width: 640, height: 480, facingMode: "user" }},
                        audio: true
                    }});

                    currentStream = stream;
                    chunks = [];
                    uploadStarted = false;

                    let options = null;

                    if (MediaRecorder.isTypeSupported("video/webm;codecs=vp8,opus")) {{
                        mediaMimeType = "video/webm;codecs=vp8,opus";
                        options = {{
                            mimeType: mediaMimeType,
                            videoBitsPerSecond: 900000,
                            audioBitsPerSecond: 64000
                        }};
                    }} else if (MediaRecorder.isTypeSupported("video/webm")) {{
                        mediaMimeType = "video/webm";
                        options = {{
                            mimeType: mediaMimeType,
                            videoBitsPerSecond: 900000,
                            audioBitsPerSecond: 64000
                        }};
                    }} else if (MediaRecorder.isTypeSupported("video/mp4")) {{
                        mediaMimeType = "video/mp4";
                        options = {{
                            mimeType: mediaMimeType,
                            videoBitsPerSecond: 900000,
                            audioBitsPerSecond: 64000
                        }};
                    }} else {{
                        currentStream.getTracks().forEach(track => track.stop());
                        currentStream = null;
                        throw new Error("Formato de grabación no soportado");
                    }}

                    const lockOk = await lockExperienceStart();
                    if (!lockOk) {{
                        if (currentStream) {{
                            currentStream.getTracks().forEach(track => track.stop());
                            currentStream = null;
                        }}
                        return;
                    }}

                    recorder = new MediaRecorder(stream, options);

                    recorder.ondataavailable = (e) => {{
                        if (e.data && e.data.size > 0) chunks.push(e.data);
                    }};

                    recorder.start(300);

                    document.getElementById("start").classList.add("hidden");
                    document.getElementById("experience").classList.remove("hidden");

                    for (const scene of scenes) {{
                        await showScene(scene);
                    }}

                    await finishFlow();

                }} catch (e) {{
                    if (currentStream) {{
                        currentStream.getTracks().forEach(track => track.stop());
                        currentStream = null;
                    }}
                    alert("Necesitamos acceso a cámara y micrófono para continuar.");
                    experienceStarted = false;
                    startBtn.disabled = false;
                    window.location.reload();
                }}
            }}
        </script>
    </body>
    </html>
    """


# =========================================================
# SUBIR VIDEO
# =========================================================

@app.post("/upload-video")
async def upload_video(
    recipient_token: str = Form(...),
    video: UploadFile = File(...),
):
    order = get_order_by_recipient_token_or_404(recipient_token)

    if not order["paid"]:
        raise HTTPException(status_code=403, detail="Pedido no pagado")

    if bool(order.get("reaction_uploaded")) or reaction_exists(order):
        return JSONResponse({
            "status": "already_uploaded",
            "preview_url": f"{PUBLIC_BASE_URL}/preview-emocion/{order['recipient_token']}",
            "cashout_url": f"{PUBLIC_BASE_URL}/cobrar/{order['recipient_token']}",
            "sender_pack_url": sender_pack_url_from_order(order),
            "public_video_url": order.get("reaction_video_public_url"),
        })

    content_type = (video.content_type or "").lower().strip()
    filename = (video.filename or "").lower().strip()

    is_allowed_type = content_type in ALLOWED_VIDEO_TYPES
    is_allowed_name = filename.endswith(".webm") or filename.endswith(".mp4")

    if not is_allowed_type and not is_allowed_name:
        raise HTTPException(status_code=400, detail="Formato de vídeo no permitido")

    video_extension = detect_video_extension(video)
    filepath = reaction_video_path(order["id"], video_extension)
    final_content_type = "video/mp4" if video_extension == "mp4" else "video/webm"
    total_size = 0

    try:
        with open(filepath, "wb") as f:
            while True:
                chunk = await video.read(1024 * 1024)
                if not chunk:
                    break

                total_size += len(chunk)
                if total_size > MAX_VIDEO_SIZE:
                    f.close()
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    raise HTTPException(status_code=400, detail="Vídeo demasiado grande")

                f.write(chunk)

        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            raise HTTPException(status_code=400, detail="Vídeo vacío")

        public_video_url = None
        try:
            public_video_url = upload_video_to_r2(
                filepath,
                f"{order['id']}.{video_extension}",
                final_content_type,
            )
        except Exception as e:
            log_error("Error subiendo a R2", e)

        update_order(
            order["id"],
            reaction_video_local=filepath,
            reaction_video_public_url=public_video_url,
            reaction_uploaded=1,
            experience_completed=1,
        )

        if public_video_url:
            insert_asset(order["id"], "reaction_video", public_video_url, "r2")
        else:
            insert_asset(order["id"], "reaction_video", f"{PUBLIC_BASE_URL}/video/sender/{order['sender_token']}", "local")

        updated_order = get_order_by_id(order["id"])

        try:
            try_send_sender_sms(updated_order)
        except Exception as e:
            log_error("Sender SMS after reaction", e)

        return JSONResponse({
            "status": "ok",
            "preview_url": f"{PUBLIC_BASE_URL}/preview-emocion/{updated_order['recipient_token']}",
            "cashout_url": f"{PUBLIC_BASE_URL}/cobrar/{updated_order['recipient_token']}",
            "sender_pack_url": sender_pack_url_from_order(updated_order),
            "public_video_url": updated_order.get("reaction_video_public_url"),
        })
    finally:
        await video.close()


# =========================================================
# VIDEO FILE PRIVADO
# =========================================================

@app.get("/video/sender/{sender_token}")
def get_video_for_sender(sender_token: str):
    order = get_order_by_sender_token_or_404(sender_token)

    filepath = order.get("reaction_video_local")
    if not filepath or not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Vídeo no encontrado")

    media_type = guess_media_type_from_path(filepath)
    return FileResponse(filepath, media_type=media_type, filename=os.path.basename(filepath))


@app.get("/video/reaction/{recipient_token}")
def get_video_for_recipient_preview(recipient_token: str):
    order = get_order_by_recipient_token_or_404(recipient_token)

    filepath = order.get("reaction_video_local")
    if not filepath or not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Vídeo no encontrado")

    media_type = guess_media_type_from_path(filepath)
    return FileResponse(filepath, media_type=media_type, filename=os.path.basename(filepath))


# =========================================================
# PREVIEW ANTES DE ENVIAR AL REGALANTE
# =========================================================

@app.get("/preview-emocion/{recipient_token}", response_class=HTMLResponse)
def preview_emocion(recipient_token: str):
    order = get_order_by_recipient_token_or_404(recipient_token)

    if not bool(order.get("experience_started")):
        return RedirectResponse(url=f"/pedido/{recipient_token}", status_code=303)

    if not bool(order.get("experience_completed")):
        return RedirectResponse(url=f"/pedido/{recipient_token}", status_code=303)

    if not reaction_exists(order):
        return HTMLResponse("""
        <!DOCTYPE html>
        <html lang="es">
        <body style="margin:0;min-height:100vh;background:#000;color:white;font-family:Arial, sans-serif;display:flex;align-items:center;justify-content:center;text-align:center;padding:24px;">
            <div><h1>Estamos preparando la vista previa…</h1></div>
        </body>
        </html>
        """)

    video_url = order.get("reaction_video_public_url") or f"/video/reaction/{order['recipient_token']}"
    video_type = guess_media_type_from_url(video_url)

    phrases_json = json.dumps([
        order["phrase_1"],
        order["phrase_2"],
        order["phrase_3"],
    ])

    sender_sms_url = f"sms:{safe_attr(to_e164(order['sender_phone']))}?&body={safe_attr(build_sender_ready_message(order))}"
    sender_pack_url = sender_pack_url_from_order(order)

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Vista previa emoción</title>
        <style>
            * {{
                box-sizing: border-box;
            }}

            html, body {{
                margin: 0;
                min-height: 100%;
                background: #000;
            }}

            body {{
                min-height: 100vh;
                background:
                    radial-gradient(circle at top, rgba(255,255,255,0.06), transparent 30%),
                    linear-gradient(180deg, #050505 0%, #000000 100%);
                color: white;
                font-family: Arial, sans-serif;
            }}

            .wrap {{
                min-height: 100vh;
                display: flex;
                flex-direction: column;
            }}

            .top {{
                flex: 1;
                min-height: 46vh;
                background: #000;
                display: flex;
                align-items: center;
                justify-content: center;
                overflow: hidden;
            }}

            .bottom {{
                flex: 1;
                min-height: 34vh;
                display: flex;
                align-items: center;
                justify-content: center;
                text-align: center;
                padding: 24px;
                border-top: 1px solid rgba(255,255,255,0.08);
            }}

            .actions {{
                padding: 24px;
                border-top: 1px solid rgba(255,255,255,0.08);
                background: rgba(255,255,255,0.03);
            }}

            .video-box {{
                width: 100%;
                height: 100%;
            }}

            video {{
                width: 100%;
                height: 100%;
                object-fit: cover;
                display: block;
                background: #111;
            }}

            .text-box {{
                width: 100%;
                max-width: 900px;
            }}

            .eyebrow {{
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 1.6px;
                color: rgba(255,255,255,0.45);
                margin-bottom: 18px;
            }}

            .phrase {{
                font-size: 32px;
                line-height: 1.45;
                font-weight: 600;
                opacity: 0;
                transform: translateY(10px);
                transition: opacity 0.35s ease, transform 0.35s ease;
                min-height: 96px;
                display: flex;
                align-items: center;
                justify-content: center;
            }}

            .phrase.visible {{
                opacity: 1;
                transform: translateY(0);
            }}

            .buttons {{
                display: grid;
                gap: 12px;
                max-width: 760px;
                margin: 0 auto;
            }}

            .btn {{
                width: 100%;
                padding: 16px 24px;
                border-radius: 999px;
                border: 0;
                font-weight: bold;
                font-size: 15px;
                cursor: pointer;
                display: inline-block;
                text-decoration: none;
                text-align: center;
            }}

            .primary {{
                background: white;
                color: black;
            }}

            .ghost {{
                background: rgba(255,255,255,0.10);
                color: white;
                border: 1px solid rgba(255,255,255,0.10);
            }}

            .soft {{
                margin-top: 14px;
                color: rgba(255,255,255,0.45);
                font-size: 13px;
                text-align: center;
            }}

            @media (max-width: 768px) {{
                .phrase {{
                    font-size: 24px;
                    min-height: 88px;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="wrap">
            <div class="top">
                <div class="video-box">
                    <video id="video" playsinline controls autoplay preload="metadata">
                        <source src="{safe_attr(video_url)}" type="{safe_attr(video_type)}">
                        Tu navegador no puede reproducir este vídeo.
                    </video>
                </div>
            </div>

            <div class="bottom">
                <div class="text-box">
                    <div class="eyebrow">Vista previa antes de enviar al regalante</div>
                    <div id="phrase" class="phrase"></div>
                </div>
            </div>

            <div class="actions">
                <div class="buttons">
                    <a class="btn primary" href="{sender_sms_url}">
                        Abrir SMS al regalante
                    </a>

                    <a class="btn ghost" href="{safe_attr(sender_pack_url)}" target="_blank" rel="noopener noreferrer">
                        Abrir sender pack
                    </a>

                    <a class="btn ghost" href="/cobrar/{safe_attr(recipient_token)}">
                        Seguir al cobro
                    </a>
                </div>

                <div class="soft">
                    Primero revisas el compacto. Si está bien, Twilio también enviará el SMS automático al regalante.
                </div>
            </div>
        </div>

        <script>
            const phrases = {phrases_json};
            const phraseEl = document.getElementById("phrase");
            const video = document.getElementById("video");

            const phraseWindows = [
                {{ start: 0, end: 3, text: phrases[0] || "" }},
                {{ start: 3, end: 6, text: phrases[1] || "" }},
                {{ start: 6, end: 999999, text: phrases[2] || "" }}
            ];

            let rafId = null;
            let currentPhraseText = null;

            function setPhrase(text) {{
                if (currentPhraseText === text) return;
                currentPhraseText = text;
                phraseEl.classList.remove("visible");
                window.setTimeout(() => {{
                    phraseEl.textContent = text || "";
                    if (text) {{
                        phraseEl.classList.add("visible");
                    }}
                }}, 120);
            }}

            function getPhraseForTime(t) {{
                for (const w of phraseWindows) {{
                    if (t >= w.start && t < w.end) return w.text;
                }}
                return phrases[phrases.length - 1] || "";
            }}

            function syncPhraseToVideo() {{
                setPhrase(getPhraseForTime(video.currentTime || 0));
            }}

            function stopLoop() {{
                if (rafId) {{
                    cancelAnimationFrame(rafId);
                    rafId = null;
                }}
            }}

            function startLoop() {{
                stopLoop();
                function tick() {{
                    if (!video.paused && !video.ended) {{
                        syncPhraseToVideo();
                        rafId = requestAnimationFrame(tick);
                    }}
                }}
                tick();
            }}

            video.addEventListener("loadedmetadata", syncPhraseToVideo);
            video.addEventListener("play", () => {{
                syncPhraseToVideo();
                startLoop();
            }});
            video.addEventListener("pause", () => {{
                stopLoop();
                syncPhraseToVideo();
            }});
            video.addEventListener("seeking", syncPhraseToVideo);
            video.addEventListener("timeupdate", syncPhraseToVideo);
            video.addEventListener("ended", () => {{
                stopLoop();
                syncPhraseToVideo();
            }});
        </script>
    </body>
    </html>
    """


# =========================================================
# COBRAR
# =========================================================

@app.get("/cobrar/{recipient_token}", response_class=HTMLResponse)
def cobrar(recipient_token: str):
    order = get_order_by_recipient_token_or_404(recipient_token)

    if not bool(order.get("experience_started")):
        return RedirectResponse(url=f"/pedido/{recipient_token}", status_code=303)

    if not bool(order.get("experience_completed")):
        return HTMLResponse("""
        <!DOCTYPE html>
        <html lang="es">
        <body style="margin:0;min-height:100vh;background:#000;color:white;font-family:Arial, sans-serif;display:flex;align-items:center;justify-content:center;text-align:center;padding:24px;">
            <div><h1>Estamos preparando tu cobro…</h1></div>
        </body>
        </html>
        """)

    if not reaction_exists(order):
        return HTMLResponse("""
        <!DOCTYPE html>
        <html lang="es">
        <body style="margin:0;min-height:100vh;background:#000;color:white;font-family:Arial, sans-serif;display:flex;align-items:center;justify-content:center;text-align:center;padding:24px;">
            <div><h1>Estamos guardando este momento…</h1></div>
        </body>
        </html>
        """)

    cashout_status = compute_cashout_status(order)
    gift_amount = float(order.get("gift_amount") or 0)

    if cashout_status == "completed":
        return RedirectResponse(url=f"/gracias-cobro/{recipient_token}", status_code=303)

    if cashout_status == "gift_refunded":
        return RedirectResponse(url=f"/gracias-cobro/{recipient_token}", status_code=303)

    amount_text = format_amount_display(order["gift_amount"])
    button_href = f"/iniciar-cobro-real/{safe_attr(recipient_token)}"
    button_text = "Cobrar"

    if gift_amount > 0 and bool(order.get("connect_onboarding_completed")):
        button_text = "Finalizar cobro"

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ETERNA</title>
        <style>
            html, body {{
                margin: 0;
                min-height: 100%;
                background: #000;
            }}
            body {{
                min-height: 100vh;
                background:
                    radial-gradient(circle at top, rgba(255,255,255,0.08), transparent 35%),
                    linear-gradient(180deg, #050505 0%, #000000 100%);
                color: white;
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 24px;
                text-align: center;
            }}
            .card {{
                width: 100%;
                max-width: 760px;
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 28px;
                padding: 40px 28px;
            }}
            h1 {{
                margin: 0 0 16px 0;
                font-size: 40px;
            }}
            .lead {{
                font-size: 18px;
                color: rgba(255,255,255,0.85);
                line-height: 1.8;
            }}
            .amount {{
                margin-top: 24px;
                font-size: 48px;
                font-weight: bold;
            }}
            .btn {{
                margin-top: 28px;
                padding: 16px 24px;
                border-radius: 999px;
                border: 0;
                background: white;
                color: black;
                font-weight: bold;
                cursor: pointer;
                font-size: 15px;
                width: 100%;
                display: block;
                text-decoration: none;
                text-align: center;
            }}
            .soft {{
                margin-top: 18px;
                font-size: 13px;
                color: rgba(255,255,255,0.5);
                line-height: 1.7;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Esto ya es tuyo</h1>

            <div class="lead">
                Para cobrarlo de verdad, Stripe te pedirá tus datos en una página segura.
            </div>

            <div class="amount">{amount_text}</div>

            <a class="btn" href="{button_href}">
                {button_text}
            </a>

            <div class="soft">
                ETERNA no guarda tu IBAN. Stripe se encarga del proceso seguro.
            </div>
        </div>
    </body>
    </html>
    """


# =========================================================
# STRIPE CONNECT ONBOARDING
# =========================================================

@app.get("/iniciar-cobro-real/{recipient_token}")
def iniciar_cobro_real(recipient_token: str):
    order = get_order_by_recipient_token_or_404(recipient_token)

    if not bool(order.get("paid")):
        return RedirectResponse(url=f"/pedido/{recipient_token}", status_code=303)

    if not bool(order.get("experience_started")):
        return RedirectResponse(url=f"/pedido/{recipient_token}", status_code=303)

    if not bool(order.get("experience_completed")):
        return RedirectResponse(url=f"/preview-emocion/{recipient_token}", status_code=303)

    if bool(order.get("gift_refunded")):
        return RedirectResponse(url=f"/gracias-cobro/{recipient_token}", status_code=303)

    gift_amount = float(order.get("gift_amount") or 0)

    if gift_amount <= 0:
        update_order(
            order["id"],
            transfer_completed=1,
            cashout_completed=1,
            connect_onboarding_completed=1,
            transfer_in_progress=0,
        )
        return RedirectResponse(url=f"/gracias-cobro/{recipient_token}", status_code=303)

    if not STRIPE_SECRET_KEY:
        update_order(
            order["id"],
            transfer_completed=1,
            cashout_completed=1,
            connect_onboarding_completed=1,
            transfer_in_progress=0,
        )
        return RedirectResponse(url=f"/gracias-cobro/{recipient_token}", status_code=303)

    if bool(order.get("transfer_completed")):
        return RedirectResponse(url=f"/gracias-cobro/{recipient_token}", status_code=303)

    if bool(order.get("transfer_in_progress")):
        return RedirectResponse(url=f"/verificando-cobro/{recipient_token}", status_code=303)

    if bool(order.get("connect_onboarding_completed")):
        result = process_gift_transfer_for_order(order)
        if result.get("status") in {"ok", "already_transferred", "no_gift", "stripe_disabled_test_mode"}:
            return RedirectResponse(url=f"/gracias-cobro/{recipient_token}", status_code=303)
        return RedirectResponse(url=f"/verificando-cobro/{recipient_token}", status_code=303)

    link_url = create_connect_onboarding_link(order)
    return RedirectResponse(url=link_url, status_code=303)


@app.get("/connect/refresh/{recipient_token}")
def connect_refresh(recipient_token: str):
    order = get_order_by_recipient_token_or_404(recipient_token)

    if bool(order.get("gift_refunded")):
        return RedirectResponse(url=f"/gracias-cobro/{recipient_token}", status_code=303)

    link_url = create_connect_onboarding_link(order)
    return RedirectResponse(url=link_url, status_code=303)


@app.get("/connect/return/{recipient_token}")
def connect_return(recipient_token: str):
    order = get_order_by_recipient_token_or_404(recipient_token)

    if bool(order.get("gift_refunded")):
        return RedirectResponse(url=f"/gracias-cobro/{recipient_token}", status_code=303)

    ready = refresh_connect_status(order)

    if ready:
        result = process_gift_transfer_for_order(order)

        if result.get("status") in {"ok", "already_transferred", "no_gift", "stripe_disabled_test_mode"}:
            return RedirectResponse(url=f"/gracias-cobro/{recipient_token}", status_code=303)

    return RedirectResponse(url=f"/verificando-cobro/{recipient_token}", status_code=303)


# =========================================================
# VERIFICANDO COBRO
# =========================================================

@app.get("/verificando-cobro/{recipient_token}", response_class=HTMLResponse)
def verificando_cobro(recipient_token: str):
    order = get_order_by_recipient_token_or_404(recipient_token)

    if bool(order.get("gift_refunded")):
        return RedirectResponse(url=f"/gracias-cobro/{recipient_token}", status_code=303)

    gift_amount = float(order.get("gift_amount") or 0)

    if gift_amount <= 0:
        if bool(order.get("cashout_completed")):
            return RedirectResponse(url=f"/gracias-cobro/{recipient_token}", status_code=303)
    else:
        if bool(order.get("stripe_connected_account_id")) and not bool(order.get("connect_onboarding_completed")):
            try:
                refresh_connect_status(order)
            except Exception as e:
                log_error("refresh_connect_status error", e)

        refreshed = get_order_by_recipient_token_or_404(recipient_token)

        if bool(refreshed.get("connect_onboarding_completed")) and not bool(refreshed.get("transfer_completed")):
            try:
                result = process_gift_transfer_for_order(refreshed)
                if result.get("status") in {"ok", "already_transferred", "no_gift", "stripe_disabled_test_mode"}:
                    return RedirectResponse(url=f"/gracias-cobro/{recipient_token}", status_code=303)
            except Exception as e:
                log_error("process_gift_transfer_for_order error", e)

        latest = get_order_by_recipient_token_or_404(recipient_token)
        if bool(latest.get("transfer_completed")):
            return RedirectResponse(url=f"/gracias-cobro/{recipient_token}", status_code=303)

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta http-equiv="refresh" content="7">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Verificando cobro</title>
        <style>
            html, body {{
                margin: 0;
                min-height: 100%;
                background: #000;
            }}
            body {{
                min-height: 100vh;
                background:
                    radial-gradient(circle at top, rgba(255,255,255,0.06), transparent 30%),
                    linear-gradient(180deg, #050505 0%, #000000 100%);
                color: white;
                font-family: Arial, sans-serif;
                display: flex;
                align-items: center;
                justify-content: center;
                text-align: center;
                padding: 24px;
            }}
            .card {{
                width: 100%;
                max-width: 760px;
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 28px;
                padding: 42px 30px;
            }}
            h1 {{
                margin: 0 0 18px 0;
                font-size: 40px;
            }}
            .lead {{
                color: rgba(255,255,255,0.88);
                line-height: 1.8;
                font-size: 20px;
            }}
            .soft {{
                margin-top: 18px;
                color: rgba(255,255,255,0.50);
                font-size: 14px;
                line-height: 1.7;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Estamos verificando tu cobro</h1>
            <div class="lead">
                Stripe está terminando el proceso seguro.<br>
                No necesitas volver a empezar.
            </div>
            <div class="soft">
                Esta pantalla se actualizará sola en unos segundos.
            </div>
        </div>
    </body>
    </html>
    """


# =========================================================
# GRACIAS COBRO
# =========================================================

@app.get("/gracias-cobro/{recipient_token}", response_class=HTMLResponse)
def gracias_cobro(recipient_token: str):
    order = get_order_by_recipient_token_or_404(recipient_token)

    if not bool(order.get("experience_started")):
        return RedirectResponse(url=f"/pedido/{recipient_token}", status_code=303)

    if not bool(order.get("experience_completed")):
        return RedirectResponse(url=f"/preview-emocion/{recipient_token}", status_code=303)

    gift_amount = float(order.get("gift_amount") or 0)

    if bool(order.get("gift_refunded")):
        title = "Ya está"
        lead = "El regalo ha quedado cancelado"
        soft = (
            f"Han pasado {GIFT_REFUND_DAYS} días sin completar el cobro. "
            "El importe regalado se ha devuelto al comprador. "
            "La experiencia sigue completada."
        )
    else:
        if gift_amount > 0 and not bool(order.get("transfer_completed")):
            return RedirectResponse(url=f"/verificando-cobro/{recipient_token}", status_code=303)

        if gift_amount <= 0 and not bool(order.get("cashout_completed")):
            return RedirectResponse(url=f"/verificando-cobro/{recipient_token}", status_code=303)

        title = "Ya está"
        lead = "Tu cobro ya está preparado" if gift_amount > 0 else "Todo ha quedado completado"
        soft = (
            "Stripe ya ha recibido tus datos y el cobro ha quedado preparado. El dinero seguirá los tiempos habituales del banco y del proveedor de pago."
            if gift_amount > 0
            else "La experiencia ha quedado cerrada correctamente."
        )

    gift_video_url = order.get("gift_video_url") or DEFAULT_GIFT_VIDEO_URL

    video_block = ""
    if gift_video_url:
        video_type = guess_media_type_from_url(gift_video_url)
        video_block = f"""
            <div class="video-wrap">
                <video controls playsinline preload="metadata">
                    <source src="{safe_attr(gift_video_url)}" type="{safe_attr(video_type)}">
                    Tu navegador no puede reproducir este vídeo.
                </video>
            </div>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ETERNA</title>
        <style>
            html, body {{
                margin: 0;
                min-height: 100%;
                background: #000;
            }}
            body {{
                min-height: 100vh;
                background:
                    radial-gradient(circle at top, rgba(255,255,255,0.06), transparent 30%),
                    linear-gradient(180deg, #050505 0%, #000000 100%);
                color: white;
                font-family: Arial, sans-serif;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 24px;
                text-align: center;
            }}
            .card {{
                width: 100%;
                max-width: 760px;
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 28px;
                padding: 42px 30px;
            }}
            h1 {{
                margin: 0 0 18px 0;
                font-size: 40px;
            }}
            .lead {{
                color: rgba(255,255,255,0.92);
                line-height: 1.8;
                font-size: 24px;
                margin: 0 0 10px 0;
                font-weight: bold;
            }}
            .soft {{
                margin-top: 10px;
                color: rgba(255,255,255,0.55);
                font-size: 14px;
                line-height: 1.7;
            }}
            .video-wrap {{
                margin-top: 28px;
            }}
            video {{
                width: 100%;
                border-radius: 18px;
                background: #111;
                display: block;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>{safe_text(title)}</h1>
            <div class="lead">{safe_text(lead)}</div>
            <div class="soft">{safe_text(soft)}</div>
            {video_block}
        </div>
    </body>
    </html>
    """


# =========================================================
# REACCION
# =========================================================

@app.get("/reaccion/{recipient_token}", response_class=HTMLResponse)
def reaccion(recipient_token: str):
    order = get_order_by_recipient_token_or_404(recipient_token)

    if not bool(order.get("experience_started")):
        return RedirectResponse(url=f"/pedido/{recipient_token}", status_code=303)

    if not bool(order.get("experience_completed")):
        return HTMLResponse("""
        <!DOCTYPE html>
        <html lang="es">
        <body style="margin:0;min-height:100vh;background:#000;color:white;font-family:Arial, sans-serif;display:flex;align-items:center;justify-content:center;text-align:center;padding:24px;">
            <div><h1>Estamos guardando este momento…</h1></div>
        </body>
        </html>
        """)

    return RedirectResponse(url=f"/preview-emocion/{recipient_token}", status_code=303)


# =========================================================
# SENDER PACK
# =========================================================

@app.get("/sender/{sender_token}", response_class=HTMLResponse)
def sender_pack(sender_token: str):
    order = get_order_by_sender_token_or_404(sender_token)

video_url = (
    order.get("reaction_video_public_url")
    or f"{PUBLIC_BASE_URL}/video/sender/{order['sender_token']}"
)
        # =========================================================
# STRIPE WEBHOOK (CON SMS AUTOMÁTICO)
# =========================================================

@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not STRIPE_WEBHOOK_SECRET and STRIPE_SECRET_KEY:
        raise HTTPException(status_code=400, detail="Webhook secret no configurado")

    try:
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=sig_header,
                secret=STRIPE_WEBHOOK_SECRET,
            )
        else:
            event = json.loads(payload.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook inválido: {e}")

    event_type = event.get("type")

    # =====================================================
    # PAGO COMPLETADO → SMS AL REGALADO
    # =====================================================
    if event_type == "checkout.session.completed":
        session = event["data"]["object"]

        order_id = (
            session.get("metadata", {}).get("order_id")
            or session.get("client_reference_id")
        )

        if order_id:
            try:
                existing = get_order_by_id(order_id)
            except HTTPException:
                return {"received": True}

            # marcar como pagado
            update_order(
                order_id,
                paid=1,
                stripe_payment_status="paid",
                stripe_session_id=session.get("id"),
                stripe_payment_intent_id=session.get("payment_intent"),
                gift_refund_deadline_at=existing.get("gift_refund_deadline_at") or gift_refund_deadline_iso(),
            )

            # enviar SMS al regalado
            try:
                updated = get_order_by_id(order_id)
                try_send_recipient_sms(updated)
            except Exception as e:
                log_error("Recipient SMS after payment", e)

    return {"received": True}


# =========================================================
# SUBIDA DE VIDEO → SMS AL REGALANTE
# =========================================================

@app.post("/upload-video")
async def upload_video(
    recipient_token: str = Form(...),
    video: UploadFile = File(...),
):
    order = get_order_by_recipient_token_or_404(recipient_token)

    if not order["paid"]:
        raise HTTPException(status_code=403, detail="Pedido no pagado")

    if bool(order.get("reaction_uploaded")) or reaction_exists(order):
        return JSONResponse({
            "status": "already_uploaded",
            "preview_url": f"{PUBLIC_BASE_URL}/preview-emocion/{order['recipient_token']}",
            "cashout_url": f"{PUBLIC_BASE_URL}/cobrar/{order['recipient_token']}",
            "sender_pack_url": sender_pack_url_from_order(order),
            "public_video_url": order.get("reaction_video_public_url"),
        })

    content_type = (video.content_type or "").lower().strip()
    filename = (video.filename or "").lower().strip()

    is_allowed_type = content_type in ALLOWED_VIDEO_TYPES
    is_allowed_name = filename.endswith(".webm") or filename.endswith(".mp4")

    if not is_allowed_type and not is_allowed_name:
        raise HTTPException(status_code=400, detail="Formato de vídeo no permitido")

    video_extension = detect_video_extension(video)
    filepath = reaction_video_path(order["id"], video_extension)
    final_content_type = "video/mp4" if video_extension == "mp4" else "video/webm"

    total_size = 0

    try:
        with open(filepath, "wb") as f:
            while True:
                chunk = await video.read(1024 * 1024)
                if not chunk:
                    break

                total_size += len(chunk)
                if total_size > MAX_VIDEO_SIZE:
                    f.close()
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    raise HTTPException(status_code=400, detail="Vídeo demasiado grande")

                f.write(chunk)

        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            raise HTTPException(status_code=400, detail="Vídeo vacío")

        public_video_url = None

        try:
            public_video_url = upload_video_to_r2(
                filepath,
                f"{order['id']}.{video_extension}",
                final_content_type,
            )
        except Exception as e:
            log_error("Error subiendo a R2", e)

        # guardar en DB
        update_order(
            order["id"],
            reaction_video_local=filepath,
            reaction_video_public_url=public_video_url,
            reaction_uploaded=1,
            experience_completed=1,
        )

        if public_video_url:
            insert_asset(order["id"], "reaction_video", public_video_url, "r2")
        else:
            insert_asset(
                order["id"],
                "reaction_video",
                f"{PUBLIC_BASE_URL}/video/sender/{order['sender_token']}",
                "local",
            )

        # =====================================================
        # SMS AL REGALANTE (AQUÍ ESTÁ LA MAGIA)
        # =====================================================
        updated_order = get_order_by_id(order["id"])

        try:
            try_send_sender_sms(updated_order)
        except Exception as e:
            log_error("Sender SMS after reaction", e)

        return JSONResponse({
            "status": "ok",
            "preview_url": f"{PUBLIC_BASE_URL}/preview-emocion/{updated_order['recipient_token']}",
            "cashout_url": f"{PUBLIC_BASE_URL}/cobrar/{updated_order['recipient_token']}",
            "sender_pack_url": sender_pack_url_from_order(updated_order),
            "public_video_url": updated_order.get("reaction_video_public_url"),
        })

    finally:
        await video.close()