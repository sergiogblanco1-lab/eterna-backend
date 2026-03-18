import os
import uuid
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from video_engine import VideoEngine

app = FastAPI(title="ETERNA LAB")

STORAGE = "storage"
TEMP_STORAGE = os.path.join(STORAGE, "temp")

os.makedirs(STORAGE, exist_ok=True)
os.makedirs(TEMP_STORAGE, exist_ok=True)

video_engine = VideoEngine()


def safe_text(value: str) -> str:
    return (value or "").replace("\x00", "").strip()


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
            body {
                background: #0b0b0b;
                color: white;
                font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                text-align: center;
                padding: 20px;
            }
            .box {
                max-width: 720px;
            }
            h1 {
                font-size: 42px;
                margin-bottom: 10px;
            }
            p {
                font-size: 18px;
                color: #cccccc;
            }
            a {
                color: white;
            }
        </style>
    </head>
    <body>
        <div class="box">
            <h1>ETERNA backend activo</h1>
            <p>La API está funcionando.</p>
            <p>Prueba la documentación en <a href="/docs">/docs</a></p>
        </div>
    </body>
    </html>
    """


@app.post("/crear-eterna")
async def crear_eterna(
    nombre: str = Form(...),
    email: str = Form(...),
    telefono_regalante: str = Form(""),
    nombre_destinatario: str = Form(""),
    telefono_destinatario: str = Form(""),
    frase1: str = Form(...),
    frase2: str = Form(...),
    frase3: str = Form(...),
    incluye_reaccion: bool = Form(True),
    regalo_activo: bool = Form(False),
    regalo_amount_eur: float = Form(0.0),
    regalo_mensaje: str = Form(""),
    fotos: List[UploadFile] = File(...),
    video_regalante: Optional[UploadFile] = File(None),
):
    if len(fotos) != 6:
        raise HTTPException(status_code=400, detail="Debes subir exactamente 6 fotos")

    nombre = safe_text(nombre)
    email = safe_text(email)
    telefono_regalante = safe_text(telefono_regalante)
    nombre_destinatario = safe_text(nombre_destinatario)
    telefono_destinatario = safe_text(telefono_destinatario)
    frases = [safe_text(frase1), safe_text(frase2), safe_text(frase3)]
    regalo_mensaje = safe_text(regalo_mensaje)

    if not nombre:
        raise HTTPException(status_code=400, detail="Falta el nombre")
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Email inválido")
    if any(len(f) < 2 for f in frases):
        raise HTTPException(status_code=400, detail="Las 3 frases deben tener contenido")
    if regalo_amount_eur < 0:
        raise HTTPException(status_code=400, detail="El regalo económico no puede ser negativo")

    eterna_id = str(uuid.uuid4())
    folder = os.path.join(TEMP_STORAGE, eterna_id)
    os.makedirs(folder, exist_ok=True)

    imagenes = []

    with open(os.path.join(folder, "datos.txt"), "w", encoding="utf-8") as f:
        f.write(f"nombre={nombre}\n")
        f.write(f"email={email}\n")
        f.write(f"telefono_regalante={telefono_regalante}\n")
        f.write(f"nombre_destinatario={nombre_destinatario}\n")
        f.write(f"telefono_destinatario={telefono_destinatario}\n")
        f.write(f"incluye_reaccion={str(incluye_reaccion).lower()}\n")
        f.write(f"regalo_activo={str(regalo_activo).lower()}\n")
        f.write(f"regalo_amount_eur={regalo_amount_eur}\n")
        f.write(f"regalo_mensaje={regalo_mensaje}\n")

    with open(os.path.join(folder, "frases.txt"), "w", encoding="utf-8") as f:
        for frase in frases:
            f.write(frase + "\n")

    for i, foto in enumerate(fotos, start=1):
        extension = os.path.splitext(foto.filename or "")[1].lower()
        if extension not in [".jpg", ".jpeg", ".png", ".webp"]:
            extension = ".jpg"

        ruta = os.path.join(folder, f"foto{i}{extension}")
        contenido = await foto.read()

        if not contenido:
            raise HTTPException(status_code=400, detail=f"La foto {i} está vacía")

        with open(ruta, "wb") as f:
            f.write(contenido)

        imagenes.append(ruta)

    video_regalante_path = None
    if video_regalante and video_regalante.filename:
        ext_video = os.path.splitext(video_regalante.filename)[1].lower()
        if ext_video not in [".mp4", ".mov", ".webm", ".m4v"]:
            ext_video = ".mp4"

        video_regalante_path = os.path.join(folder, f"video_regalante{ext_video}")
        contenido_video = await video_regalante.read()

        if not contenido_video:
            raise HTTPException(status_code=400, detail="El vídeo del regalante está vacío")

        with open(video_regalante_path, "wb") as f:
            f.write(contenido_video)

    video_path = os.path.join(folder, "video.mp4")

    try:
        video_generado = video_engine.generar_video_eterna(
            imagenes=imagenes,
            frases=frases,
            output=video_path,
            video_regalante=video_regalante_path,
            regalo_activo=regalo_activo,
            regalo_amount_eur=regalo_amount_eur,
            regalo_mensaje=regalo_mensaje,
            nombre_destinatario=nombre_destinatario,
            nombre_remitente=nombre,
        )
        print("🎬 VIDEO GENERADO EN:", video_generado)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando vídeo: {str(e)}")

    if not os.path.exists(video_path):
        raise HTTPException(status_code=500, detail="El vídeo no se generó")

    return {
        "ok": True,
        "eterna_id": eterna_id,
        "nombre": nombre,
        "email": email,
        "telefono_regalante": telefono_regalante,
        "nombre_destinatario": nombre_destinatario,
        "telefono_destinatario": telefono_destinatario,
        "frases": frases,
        "total_fotos": len(imagenes),
        "incluye_reaccion": incluye_reaccion,
        "regalo_activo": regalo_activo,
        "regalo_amount_eur": regalo_amount_eur,
        "video_url": f"/video/{eterna_id}",
        "preview_url": f"/preview/{eterna_id}",
        "message": "ETERNA creada correctamente"
    }


@app.get("/video/{eterna_id}")
def obtener_video(eterna_id: str):
    ruta = os.path.join(TEMP_STORAGE, eterna_id, "video.mp4")

    if not os.path.exists(ruta):
        return JSONResponse(
            status_code=404,
            content={"detail": "Vídeo no encontrado"}
        )

    return FileResponse(ruta, media_type="video/mp4", filename="video.mp4")


@app.post("/reaccion/{eterna_id}")
async def guardar_reaccion(
    eterna_id: str,
    reaction_file: UploadFile = File(...),
    permiso_publicar: bool = Form(False),
):
    folder = os.path.join(TEMP_STORAGE, eterna_id)
    if not os.path.exists(folder):
        raise HTTPException(status_code=404, detail="ETERNA no encontrada")

    ext = os.path.splitext(reaction_file.filename or "")[1].lower()
    if ext not in [".webm", ".mp4", ".mov", ".m4v"]:
        ext = ".webm"

    ruta = os.path.join(folder, f"reaccion{ext}")
    contenido = await reaction_file.read()

    if not contenido:
        raise HTTPException(status_code=400, detail="La reacción está vacía")

    with open(ruta, "wb") as f:
        f.write(contenido)

    with open(os.path.join(folder, "reaccion_info.txt"), "w", encoding="utf-8") as f:
        f.write(f"permiso_publicar={str(permiso_publicar).lower()}\n")

    return {
        "ok": True,
        "message": "Reacción guardada correctamente",
        "reaction_url": f"/reaccion/{eterna_id}/ver"
    }


@app.get("/reaccion/{eterna_id}/ver")
def ver_reaccion(eterna_id: str):
    folder = os.path.join(TEMP_STORAGE, eterna_id)
    if not os.path.exists(folder):
        raise HTTPException(status_code=404, detail="ETERNA no encontrada")

    for nombre in os.listdir(folder):
        if nombre.startswith("reaccion."):
            ruta = os.path.join(folder, nombre)
            ext = os.path.splitext(nombre)[1].lower()

            media_type = "video/webm"
            if ext in [".mp4", ".m4v"]:
                media_type = "video/mp4"
            elif ext == ".mov":
                media_type = "video/quicktime"

            return FileResponse(ruta, media_type=media_type, filename=nombre)

    raise HTTPException(status_code=404, detail="Reacción no encontrada")


@app.get("/preview/{eterna_id}", response_class=HTMLResponse)
def preview_video(
    eterna_id: str,
    autoplay: bool = Query(True),
):
    ruta = os.path.join(TEMP_STORAGE, eterna_id, "video.mp4")
    datos_path = os.path.join(TEMP_STORAGE, eterna_id, "datos.txt")

    if not os.path.exists(ruta):
        raise HTTPException(status_code=404, detail="Vídeo no encontrado")

    incluye_reaccion = True
    regalo_activo = False
    regalo_amount_eur = "0"
    regalo_mensaje = ""

    if os.path.exists(datos_path):
        with open(datos_path, "r", encoding="utf-8") as f:
            contenido = f.read()
            incluye_reaccion = "incluye_reaccion=true" in contenido
            regalo_activo = "regalo_activo=true" in contenido

            for linea in contenido.splitlines():
                if linea.startswith("regalo_amount_eur="):
                    regalo_amount_eur = linea.split("=", 1)[1].strip()
                if linea.startswith("regalo_mensaje="):
                    regalo_mensaje = linea.split("=", 1)[1].strip()

    video_url = f"/video/{eterna_id}"
    autoplay_attr = "autoplay" if autoplay else ""

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
                background: #0b0b0b;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                color: white;
                font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif;
                flex-direction: column;
                padding: 20px;
            }}
            .wrap {{
                width: 100%;
                max-width: 430px;
                text-align: center;
            }}
            .card {{
                width: 100%;
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 24px;
                padding: 20px;
                box-sizing: border-box;
                box-shadow: 0 0 30px rgba(255,255,255,0.05);
            }}
            video {{
                width: 100%;
                border-radius: 18px;
                background: black;
            }}
            h1 {{
                margin-bottom: 14px;
                font-size: 24px;
            }}
            p {{
                color: #cccccc;
                line-height: 1.5;
            }}
            .btn {{
                display: block;
                width: 100%;
                padding: 15px;
                border-radius: 16px;
                border: none;
                cursor: pointer;
                font-weight: 700;
                margin-top: 12px;
                font-size: 16px;
            }}
            .btn-primary {{
                background: white;
                color: #111;
            }}
            .btn-secondary {{
                background: #1a1a1a;
                color: white;
                border: 1px solid rgba(255,255,255,0.08);
            }}
            .hidden {{
                display: none;
            }}
            .muted {{
                font-size: 14px;
                color: #aaaaaa;
            }}
            .box {{
                margin-top: 16px;
                padding: 14px;
                border-radius: 16px;
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.08);
            }}
        </style>
    </head>
    <body>
        <div class="wrap">
            <div class="card">
                <div id="introScreen">
                    <h1>Alguien ha preparado algo para ti</h1>
                    <p>Hay momentos que merecen quedarse para siempre.</p>
                    <button class="btn btn-primary" id="btnStart">Ver mi ETERNA</button>
                </div>

                <div id="prepareScreen" class="hidden">
                    <h1>Antes de empezar…</h1>
                    <p>Vívelo con calma. Puede ser un momento especial.</p>
                    {"<p class='muted'>Puedes activar la cámara ahora. Solo decidirás al final si quieres guardar tu reacción.</p>" if incluye_reaccion else ""}
                    {"<button class='btn btn-primary' id='btnCamera'>Activar cámara y continuar</button>" if incluye_reaccion else ""}
                    <button class="btn btn-secondary" id="btnContinue">Continuar</button>
                </div>

                <div id="cameraBox" class="hidden box">
                    <p class="muted">Cámara preparada</p>
                    <video id="cameraPreview" autoplay muted playsinline></video>
                </div>

                <div id="videoBox" class="hidden">
                    <video id="eternaVideo" controls playsinline preload="auto" {autoplay_attr}>
                        <source src="{video_url}" type="video/mp4">
                        Tu navegador no soporta vídeo.
                    </video>
                </div>

                <div id="pauseBox" class="hidden box">
                    <p>...</p>
                </div>

                <div id="afterVideo" class="hidden">
                    <h1>Este momento también puede quedarse para siempre</h1>
                    <p id="afterText">Gracias por vivirlo.</p>

                    <div id="giftBox" class="hidden box">
                        <p><strong>Y además…</strong></p>
                        <p>{regalo_amount_eur}€ para ti</p>
                        {f"<p class='muted'>{regalo_mensaje}</p>" if regalo_mensaje else ""}
                    </div>

                    <div id="reactionReveal" class="hidden">
                        <button class="btn btn-primary" id="btnShowSaveReaction">Guardar mi reacción</button>
                        <button class="btn btn-secondary" id="btnSkipReaction">Ahora no</button>
                    </div>

                    <div id="permissionBox" class="hidden">
                        <label class="muted" style="display:block;margin:14px 0;">
                            <input type="checkbox" id="permisoPublicar" />
                            Doy permiso para que ETERNA use mi reacción con fines promocionales
                        </label>
                        <button class="btn btn-primary" id="btnUploadReaction">Enviar reacción</button>
                    </div>

                    <div id="shareBox" class="hidden">
                        <button class="btn btn-secondary" id="btnCopyLink">Copiar enlace</button>
                        <a class="btn btn-secondary" id="btnWhatsapp" target="_blank" style="text-decoration:none;box-sizing:border-box;">Compartir por WhatsApp</a>
                    </div>
                </div>
            </div>
        </div>

        <script>
        const allowReaction = {str(incluye_reaccion).lower()};
        const giftActive = {str(regalo_activo).lower()};
        const shareUrl = window.location.href;

        const introScreen = document.getElementById('introScreen');
        const prepareScreen = document.getElementById('prepareScreen');
        const cameraBox = document.getElementById('cameraBox');
        const cameraPreview = document.getElementById('cameraPreview');
        const videoBox = document.getElementById('videoBox');
        const videoEl = document.getElementById('eternaVideo');
        const pauseBox = document.getElementById('pauseBox');
        const afterVideo = document.getElementById('afterVideo');
        const giftBox = document.getElementById('giftBox');
        const reactionReveal = document.getElementById('reactionReveal');
        const permissionBox = document.getElementById('permissionBox');
        const btnStart = document.getElementById('btnStart');
        const btnCamera = document.getElementById('btnCamera');
        const btnContinue = document.getElementById('btnContinue');
        const btnShowSaveReaction = document.getElementById('btnShowSaveReaction');
        const btnSkipReaction = document.getElementById('btnSkipReaction');
        const btnUploadReaction = document.getElementById('btnUploadReaction');
        const permisoPublicar = document.getElementById('permisoPublicar');
        const btnCopyLink = document.getElementById('btnCopyLink');
        const btnWhatsapp = document.getElementById('btnWhatsapp');

        let stream = null;
        let recorder = null;
        let chunks = [];
        let recordedBlob = null;
        let cameraArmed = false;

        function stopStream() {{
            if (stream) {{
                stream.getTracks().forEach(track => track.stop());
                stream = null;
            }}
            if (cameraPreview) {{
                cameraPreview.srcObject = null;
            }}
        }}

        async function armCamera() {{
            if (!navigator.mediaDevices || !window.MediaRecorder) {{
                return false;
            }}
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
                return true;
            }} catch (err) {{
                console.error(err);
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

            videoEl.play().catch(() => {{}});
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

        videoEl.addEventListener('ended', () => {{
            if (cameraArmed && recorder && recorder.state !== 'inactive') {{
                try {{
                    recorder.stop();
                }} catch (err) {{
                    console.error(err);
                }}
            }}

            pauseBox.classList.remove('hidden');

            setTimeout(() => {{
                pauseBox.classList.add('hidden');
                afterVideo.classList.remove('hidden');

                if (giftActive) {{
                    giftBox.classList.remove('hidden');
                }}

                if (allowReaction && recordedBlob) {{
                    reactionReveal.classList.remove('hidden');
                }} else {{
                    prepareShare();
                }}

                afterVideo.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
            }}, 1200);
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
                formData.append('reaction_file', file);
                formData.append('permiso_publicar', permisoPublicar.checked ? 'true' : 'false');

                try {{
                    const res = await fetch('/reaccion/{eterna_id}', {{
                        method: 'POST',
                        body: formData
                    }});

                    const data = await res.json();
                    if (!res.ok) throw new Error(data.detail || 'No se pudo subir la reacción');

                    permissionBox.classList.add('hidden');
                    prepareShare();
                }} catch (err) {{
                    console.error(err);
                    btnUploadReaction.disabled = false;
                    btnUploadReaction.textContent = 'Enviar reacción';
                    alert(err.message || 'Error al subir la reacción');
                }}
            }});
        }}

        function prepareShare() {{
            const shareBox = document.getElementById('shareBox');
            shareBox.classList.remove('hidden');

            const text = encodeURIComponent("Quiero compartir contigo este momento de ETERNA");
            const url = encodeURIComponent(shareUrl);
            btnWhatsapp.href = `https://wa.me/?text=${{text}}%20${{url}}`;
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
    </body>
    </html>
    """
