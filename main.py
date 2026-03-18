from fastapi import FastAPI, UploadFile, File, Form
from typing import List, Optional
import uuid
from pathlib import Path

app = FastAPI()

# =========================
# CONFIGURACIÓN STORAGE
# =========================

BASE_DIR = Path(__file__).resolve().parent
STORAGE = BASE_DIR / "storage"
STORAGE.mkdir(exist_ok=True)


# =========================
# UTILIDADES
# =========================

def limpiar_texto(valor: Optional[str]) -> str:
    """
    Limpia un texto eliminando espacios y valores None.
    """
    if valor is None:
        return ""
    return valor.strip()


def extension_segura(filename: str) -> str:
    """
    Devuelve una extensión válida de imagen.
    """
    ext = Path(filename).suffix.lower()

    extensiones_validas = [".jpg", ".jpeg", ".png", ".webp"]

    if ext in extensiones_validas:
        return ext

    return ".jpg"


# =========================
# HEALTH CHECK
# =========================

@app.get("/")
def home():
    return {
        "status": "ETERNA OK",
        "version": "v2"
    }


# =========================
# CREAR ETERNA
# =========================

@app.post("/crear-eterna")
async def crear_eterna(
    nombre: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    telefono: Optional[str] = Form(None),
    nombre_destinatario: Optional[str] = Form(None),
    telefono_destinatario: Optional[str] = Form(None),
    frase1: Optional[str] = Form(None),
    frase2: Optional[str] = Form(None),
    frase3: Optional[str] = Form(None),
    fotos: List[UploadFile] = File(...)
):
    try:
        # =========================
        # LIMPIEZA DE DATOS
        # =========================

        nombre = limpiar_texto(nombre)
        email = limpiar_texto(email)
        telefono = limpiar_texto(telefono)
        nombre_destinatario = limpiar_texto(nombre_destinatario)
        telefono_destinatario = limpiar_texto(telefono_destinatario)
        frase1 = limpiar_texto(frase1)
        frase2 = limpiar_texto(frase2)
        frase3 = limpiar_texto(frase3)

        # =========================
        # VALIDACIONES
        # =========================

        if len(fotos) == 0:
            return {
                "status": "error",
                "detalle": "Debes subir al menos 1 foto"
            }

        if len(fotos) > 6:
            return {
                "status": "error",
                "detalle": "Máximo 6 fotos"
            }

        # =========================
        # CREAR ID Y CARPETA
        # =========================

        eterna_id = str(uuid.uuid4())
        carpeta = STORAGE / eterna_id
        carpeta.mkdir(parents=True, exist_ok=True)

        # =========================
        # GUARDAR DATOS
        # =========================

        with open(carpeta / "data.txt", "w", encoding="utf-8") as f:
            f.write(f"nombre: {nombre}\n")
            f.write(f"email: {email}\n")
            f.write(f"telefono: {telefono}\n")
            f.write(f"destinatario: {nombre_destinatario}\n")
            f.write(f"telefono_dest: {telefono_destinatario}\n")
            f.write(f"frase1: {frase1}\n")
            f.write(f"frase2: {frase2}\n")
            f.write(f"frase3: {frase3}\n")

        # =========================
        # GUARDAR ESTADO
        # =========================

        with open(carpeta / "status.txt", "w") as f:
            f.write("estado: pendiente_pago\n")
            f.write("video: no_generado\n")

        # =========================
        # GUARDAR FOTOS
        # =========================

        fotos_guardadas = []

        for i, foto in enumerate(fotos):
            if not foto.filename:
                continue

            contenido = await foto.read()

            if not contenido:
                continue

            ext = extension_segura(foto.filename)
            nombre_archivo = f"foto{i+1}{ext}"
            ruta = carpeta / nombre_archivo

            with open(ruta, "wb") as f:
                f.write(contenido)

            fotos_guardadas.append(nombre_archivo)

        if len(fotos_guardadas) == 0:
            return {
                "status": "error",
                "detalle": "Las fotos no son válidas"
            }

        # =========================
        # RESPUESTA + PAGO (PREPARADO)
        # =========================

        payment_url = f"/pagar/{eterna_id}"

        return {
            "status": "ok",
            "eterna_id": eterna_id,
            "fotos_recibidas": len(fotos_guardadas),
            "payment_url": payment_url
        }

    except Exception as e:
        return {
            "status": "error",
            "detalle": str(e)
        }
