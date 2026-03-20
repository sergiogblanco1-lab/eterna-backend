import uuid
import urllib.parse
from typing import List, Optional

from fastapi import FastAPI, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI(title="ETERNA")

ORDERS = {}


def clean_phone(phone: str) -> str:
    return "".join(filter(str.isdigit, phone or ""))


def whatsapp_link(phone: str, url: str) -> str:
    msg = f"Hay algo para ti ❤️\n\nÁbrelo cuando estés en un momento tranquilo.\n\n👉 {url}"
    return f"https://wa.me/{clean_phone(phone)}?text={urllib.parse.quote(msg)}"


@app.get("/")
def home():
    return {"status": "ETERNA funcionando"}


@app.post("/crear-eterna")
async def crear_eterna(
    customer_name: str = Form(...),
    customer_email: str = Form(...),
    recipient_name: str = Form(...),
    recipient_phone: str = Form(...),
    phrase_1: str = Form(...),
    phrase_2: str = Form(...),
    phrase_3: str = Form(...),
    money_amount: str = Form("50€"),
    photos: Optional[List[UploadFile]] = File(None),
):
    order_id = str(uuid.uuid4())

    photo_names = []
    if photos:
        for photo in photos:
            if photo and photo.filename:
                photo_names.append(photo.filename)

    ORDERS[order_id] = {
        "paid": True,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "recipient_name": recipient_name,
        "recipient_phone": recipient_phone,
        "phrase_1": phrase_1,
        "phrase_2": phrase_2,
        "phrase_3": phrase_3,
        "money_amount": money_amount,
        "photos": photo_names,
    }

    return RedirectResponse(f"/pedido/{order_id}", status_code=303)


@app.get("/pedido/{order_id}", response_class=HTMLResponse)
def pedido(order_id: str):
    order = ORDERS.get(order_id)

    if not order:
        return HTMLResponse("<h1 style='font-family:Arial'>No existe</h1>", status_code=404)

    link = whatsapp_link(order["recipient_phone"], f"http://localhost:10000/ver/{order_id}")

    return HTMLResponse(f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>ETERNA lista</title>
    </head>
    <body style="background:black;color:white;text-align:center;padding-top:100px;font-family:Arial;">
        <h1>ETERNA lista</h1>
        <p>Enlace directo:</p>
        <p><a href="/ver/{order_id}" style="color:#9ad1ff;">/ver/{order_id}</a></p>
        <br>
        <a href="{link}">
            <button style="padding:20px;background:green;color:white;border:none;border-radius:12px;font-size:18px;cursor:pointer;">
                Enviar por WhatsApp
            </button>
        </a>
    </body>
    </html>
    """)


@app.get("/ver/{order_id}", response_class=HTMLResponse)
def ver_eterna(order_id: str):
    order = ORDERS.get(order_id)

    if not order:
        return HTMLResponse("<h1 style='font-family:Arial'>No existe esta ETERNA</h1>", status_code=404)

    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>ETERNA</title>
        <style>
            * {{
                box-sizing: border-box;
            }}

            body {{
                margin: 0;
                background: #050505;
                color: white;
                font-family: Arial, sans-serif;
                overflow-x: hidden;
            }}

            .screen {{
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                padding: 24px;
                text-align: center;
            }}

            .hidden {{
                display: none !important;
            }}

            .box {{
                width: 100%;
                max-width: 760px;
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 24px;
                padding: 28px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.35);
            }}

            h1 {{
                margin: 0 0 12px 0;
                font-size: 40px;
                letter-spacing: 1px;
            }}

            p {{
                line-height: 1.6;
                opacity: 0.95;
            }}

            button {{
                margin-top: 20px;
                padding: 16px 26px;
                border: none;
                border-radius: 14px;
                background: white;
                color: black;
                font-size: 18px;
                font-weight: bold;
                cursor: pointer;
            }}

            button:hover {{
                transform: scale(1.02);
            }}

            .secondary {{
                background: transparent;
                color: white;
                border: 1px solid rgba(255,255,255,0.25);
            }}

            #cameraPreview {{
                width: 180px;
                height: 240px;
                object-fit: cover;
                border-radius: 18px;
                margin-top: 18px;
                border: 1px solid rgba(255,255,255,0.12);
                background: #111;
            }}

            #countdown {{
                font-size: 90px;
                font-weight: bold;
                margin: 18px 0;
            }}

            .phrase {{
                font-size: 28px;
                margin: 16px 0;
                opacity: 0;
                transform: translateY(12px);
                transition: all 0.8s ease;
            }}

            .phrase.show {{
                opacity: 1;
                transform: translateY(0);
            }}

            #moneyReveal {{
                margin-top: 34px;
                font-size: 64px;
                font-weight: bold;
                opacity: 0;
                transform: scale(0.9);
                transition: all 0.6s ease;
            }}

            #moneyReveal.show {{
                opacity: 1;
                transform: scale(1);
            }}

            #statusText {{
                margin-top: 18px;
                font-size: 14px;
                opacity: 0.7;
            }}

            #downloadWrap {{
                margin-top: 28px;
            }}

            #downloadLink {{
                color: #9ad1ff;
                font-size: 18px;
            }}
        </style>
    </head>
    <body>

        <div id="gateScreen" class="screen">
            <div class="box">
                <h1>ETERNA</h1>
                <p>Hay algo para ti ❤️</p>
                <p>Pero necesito verte cuando lo abras.</p>
                <button id="openBtn">Abrir ETERNA</button>
                <div id="gateError" style="margin-top:18px;color:#ff9b9b;"></div>
            </div>
        </div>

        <div id="blockedScreen" class="screen hidden">
            <div class="box">
                <h1>No puedo entregártelo</h1>
                <p>Sin aceptar la cámara no puedes ver el regalo ni el dinero.</p>
                <button id="retryBtn">Intentar de nuevo</button>
            </div>
        </div>

        <div id="experienceScreen" class="screen hidden">
            <div class="box">
                <h1>ETERNA</h1>
                <p>Esto se está viviendo contigo ❤️</p>

                <video id="cameraPreview" autoplay muted playsinline></video>

                <div id="countdownWrap">
                    <div id="countdown">3</div>
                    <p id="statusText">Preparando tu momento...</p>
                </div>

                <div id="revealWrap" class="hidden">
                    <div id="phrase1" class="phrase">{order["phrase_1"]}</div>
                    <div id="phrase2" class="phrase">{order["phrase_2"]}</div>
                    <div id="phrase3" class="phrase">{order["phrase_3"]}</div>
                    <div id="moneyReveal">+ {order["money_amount"]}</div>
                    <div id="downloadWrap" class="hidden">
                        <p>Tu momento ha sido guardado ❤️</p>
                        <a id="downloadLink" href="#" download="eterna_reaccion.webm">Descargar reacción</a>
                    </div>
                </div>
            </div>
        </div>

        <script>
            let mediaStream = null;
            let mediaRecorder = null;
            let recordedChunks = [];
            let stopTimeout = null;

            const gateScreen = document.getElementById("gateScreen");
            const blockedScreen = document.getElementById("blockedScreen");
            const experienceScreen = document.getElementById("experienceScreen");

            const openBtn = document.getElementById("openBtn");
            const retryBtn = document.getElementById("retryBtn");
            const gateError = document.getElementById("gateError");

            const cameraPreview = document.getElementById("cameraPreview");
            const countdown = document.getElementById("countdown");
            const countdownWrap = document.getElementById("countdownWrap");
            const revealWrap = document.getElementById("revealWrap");

            const phrase1 = document.getElementById("phrase1");
            const phrase2 = document.getElementById("phrase2");
            const phrase3 = document.getElementById("phrase3");
            const moneyReveal = document.getElementById("moneyReveal");
            const downloadWrap = document.getElementById("downloadWrap");
            const downloadLink = document.getElementById("downloadLink");

            function wait(ms) {{
                return new Promise(resolve => setTimeout(resolve, ms));
            }}

            async function askForCameraAndStart() {{
                gateError.textContent = "";

                try {{
                    mediaStream = await navigator.mediaDevices.getUserMedia({{
                        video: {{
                            facingMode: "user",
                            width: {{ ideal: 720 }},
                            height: {{ ideal: 1280 }}
                        }},
                        audio: true
                    }});

                    cameraPreview.srcObject = mediaStream;

                    gateScreen.classList.add("hidden");
                    blockedScreen.classList.add("hidden");
                    experienceScreen.classList.remove("hidden");

                    startRecording();
                    await startCountdownAndReveal();
                }} catch (error) {{
                    gateScreen.classList.add("hidden");
                    blockedScreen.classList.remove("hidden");
                }}
            }}

            function startRecording() {{
                recordedChunks = [];

                let mimeType = "";
                if (MediaRecorder.isTypeSupported("video/webm;codecs=vp9,opus")) {{
                    mimeType = "video/webm;codecs=vp9,opus";
                }} else if (MediaRecorder.isTypeSupported("video/webm;codecs=vp8,opus")) {{
                    mimeType = "video/webm;codecs=vp8,opus";
                }} else {{
                    mimeType = "video/webm";
                }}

                mediaRecorder = new MediaRecorder(mediaStream, {{ mimeType }});

                mediaRecorder.ondataavailable = (event) => {{
                    if (event.data && event.data.size > 0) {{
                        recordedChunks.push(event.data);
                    }}
                }};

                mediaRecorder.onstop = () => {{
                    const blob = new Blob(recordedChunks, {{ type: mediaRecorder.mimeType || "video/webm" }});
                    const url = URL.createObjectURL(blob);
                    downloadLink.href = url;
                    downloadWrap.classList.remove("hidden");

                    if (mediaStream) {{
                        mediaStream.getTracks().forEach(track => track.stop());
                    }}
                }};

                mediaRecorder.start();
            }}

            function stopRecording() {{
                if (mediaRecorder && mediaRecorder.state !== "inactive") {{
                    mediaRecorder.stop();
                }}
            }}

            async function startCountdownAndReveal() {{
                countdown.textContent = "3";
                await wait(1000);
                countdown.textContent = "2";
                await wait(1000);
                countdown.textContent = "1";
                await wait(1000);

                countdownWrap.classList.add("hidden");
                revealWrap.classList.remove("hidden");

                phrase1.classList.add("show");
                await wait(1800);

                phrase2.classList.add("show");
                await wait(1800);

                phrase3.classList.add("show");
                await wait(1800);

                moneyReveal.classList.add("show");

                stopTimeout = setTimeout(() => {{
                    stopRecording();
                }}, 10000);
            }}

            openBtn.addEventListener("click", askForCameraAndStart);

            retryBtn.addEventListener("click", async () => {{
                blockedScreen.classList.add("hidden");
                gateScreen.classList.remove("hidden");
                await askForCameraAndStart();
            }});
        </script>
    </body>
    </html>
    """)
