import os
import uuid
from pathlib import Path
from typing import List

from fastapi import FastAPI, Request, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from video_engine import VideoEngine


app = FastAPI(title="ETERNA backend")

BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# IMPORTANTE: esto expone storage/{eterna_id}/video.mp4 como /media/{eterna_id}/video.mp4
app.mount("/media", StaticFiles(directory=str(STORAGE_DIR)), name="media")

video_engine = VideoEngine()


def _safe_text(value: str | None) -> str:
    return (value or "").strip()


def _save_upload_file(upload: UploadFile, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as buffer:
        content = upload.file.read()
        buffer.write(content)


@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ETERNA backend</title>
        <style>
            body {
                background: #0b0b0b;
                color: white;
                font-family: Arial, sans-serif;
                padding: 40px;
                line-height: 1.5;
            }
            h1 { margin-bottom: 10px; }
            .ok { color: #8fd18f; }
            a { color: #9ecbff; }
        </style>
    </head>
    <body>
        <h1>ETERNA backend</h1>
        <p class="ok">Backend online.</p>
        <p>Endpoint principal: <code>POST /crear-eterna</code></p>
        <p>Ruta de medios: <code>/media/&lt;eterna_id&gt;/video.mp4</code></p>
    </body>
    </html>
    """


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/crear-eterna")
async def crear_eterna(request: Request):
    try:
        form = await request.form()

        # Campos de texto
        nombre = _safe_text(form.get("nombre") or form.get("customer_name") or form.get("name"))
        email = _safe_text(form.get("email") or form.get("customer_email"))
        telefono = _safe_text(form.get("telefono") or form.get("customer_phone") or form.get("tlf"))
        destinatario = _safe_text(
            form.get("destinatario")
            or form.get("recipient_name")
            or form.get("nombre_destinatario")
        )
        telefono_destinatario = _safe_text(
            form.get("telefono_destinatario")
            or form.get("recipient_phone")
            or form.get("tlf_destinatario")
        )

        frase1 = _safe_text(form.get("frase1"))
        frase2 = _safe_text(form.get("frase2"))
        frase3 = _safe_text(form.get("frase3"))
        phrases = [frase1, frase2, frase3]

        # Detectar fotos de forma flexible
        uploads: List[UploadFile] = []
        for _, value in form.multi_items():
            if isinstance(value, UploadFile):
                if value.filename and value.content_type and value.content_type.startswith("image/"):
                    uploads.append(value)

        if not uploads:
            raise HTTPException(status_code=400, detail="No se recibieron fotos.")

        eterna_id = str(uuid.uuid4())
        eterna_dir = STORAGE_DIR / eterna_id
        eterna_dir.mkdir(parents=True, exist_ok=True)

        # Guardar datos
        data_txt = eterna_dir / "data.txt"
        data_txt.write_text(
            "\n".join(
                [
                    f"nombre={nombre}",
                    f"email={email}",
                    f"telefono={telefono}",
                    f"destinatario={destinatario}",
                    f"telefono_destinatario={telefono_destinatario}",
                    f"frase1={frase1}",
                    f"frase2={frase2}",
                    f"frase3={frase3}",
                ]
            ),
            encoding="utf-8",
        )

        frases_txt = eterna_dir / "frases.txt"
        frases_txt.write_text("\n".join(phrases), encoding="utf-8")

        # Guardar fotos
        image_paths: List[str] = []
        fotos_guardadas: List[str] = []

        for index, upload in enumerate(uploads[:6], start=1):
            ext = Path(upload.filename).suffix.lower()
            if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
                ext = ".jpg"

            file_name = f"foto{index}{ext}"
            file_path = eterna_dir / file_name
            _save_upload_file(upload, file_path)

            image_paths.append(str(file_path))
            fotos_guardadas.append(file_name)

        if not image_paths:
            raise HTTPException(status_code=400, detail="No se pudieron guardar las fotos.")

        # Generar vídeo
        video_path = eterna_dir / "video.mp4"
        generated_video_path = video_engine.generate_video(
            image_paths=image_paths,
            phrases=phrases,
            output_path=str(video_path),
        )

        # Debug importante
        print("=== ETERNA DEBUG ===")
        print("ETERNA ID:", eterna_id)
        print("VIDEO PATH ESPERADO:", str(video_path))
        print("VIDEO PATH DEVUELTO:", generated_video_path)
        print("VIDEO EXISTE:", video_path.exists())
        print("VIDEO SIZE:", video_path.stat().st_size if video_path.exists() else "NO FILE")
        print("IMAGES:", image_paths)
        print("====================")

        if not video_path.exists():
            raise HTTPException(status_code=500, detail="Se generó la ETERNA, pero no apareció video.mp4.")

        video_url = f"/media/{eterna_id}/video.mp4"
        full_video_url = f"{request.base_url.scheme}://{request.base_url.netloc}{video_url}"
        experience_url = f"{request.base_url.scheme}://{request.base_url.netloc}/e/{eterna_id}"

        return JSONResponse(
            {
                "status": "ok",
                "eterna_id": eterna_id,
                "fotos_recibidas": len(uploads),
                "fotos_guardadas": fotos_guardadas,
                "video_url": full_video_url,
                "experience_url": experience_url,
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        print("=== ERROR /crear-eterna ===")
        print(str(e))
        print("===========================")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "detail": str(e),
            },
        )


@app.get("/e/{eterna_id}", response_class=HTMLResponse)
def ver_eterna(eterna_id: str):
    eterna_dir = STORAGE_DIR / eterna_id
    frases_path = eterna_dir / "frases.txt"
    video_path = eterna_dir / "video.mp4"

    if not eterna_dir.exists():
        return HTMLResponse("<h1>ETERNA no encontrada</h1>", status_code=404)

    frases = ["", "", ""]
    if frases_path.exists():
        lines = frases_path.read_text(encoding="utf-8").splitlines()
        for i in range(min(3, len(lines))):
            frases[i] = lines[i]

    video_html = ""
    if video_path.exists():
        video_html = f"""
        <video controls playsinline style="width:100%;max-width:420px;border-radius:16px;background:black;">
            <source src="/media/{eterna_id}/video.mp4" type="video/mp4">
            Tu navegador no puede reproducir el vídeo.
        </video>
        """
    else:
        video_html = "<p>El vídeo todavía no está disponible.</p>"

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ETERNA</title>
        <style>
            body {{
                margin: 0;
                background: #000;
                color: #fff;
                font-family: Arial, sans-serif;
                text-align: center;
                padding: 32px 20px 60px;
            }}
            h1 {{
                font-size: 34px;
                letter-spacing: 4px;
                margin-bottom: 24px;
            }}
            .wrap {{
                max-width: 480px;
                margin: 0 auto;
            }}
            .frase {{
                font-size: 18px;
                line-height: 1.6;
                margin: 18px 0;
                opacity: 0.9;
            }}
        </style>
    </head>
    <body>
        <div class="wrap">
            <h1>ETERNA</h1>
            {video_html}
            <div class="frase">{frases[0]}</div>
            <div class="frase">{frases[1]}</div>
            <div class="frase">{frases[2]}</div>
        </div>
    </body>
    </html>
    """


@app.get("/eterna/test")
def eterna_test(request: Request):
    eterna_id = "test"
    test_dir = STORAGE_DIR / eterna_id
    test_dir.mkdir(parents=True, exist_ok=True)

    video_path = test_dir / "video.mp4"
    if not video_path.exists():
        # placeholder mínimo si quieres comprobar la ruta /media
        video_path.write_bytes(b"")

    video_url = f"{request.base_url.scheme}://{request.base_url.netloc}/media/{eterna_id}/video.mp4"
    return {
        "status": "ok",
        "video_url": video_url,
    }
