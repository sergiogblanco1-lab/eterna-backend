from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from typing import List
import os
import uuid
import subprocess
import threading

app = FastAPI()

STORAGE = "storage"
EXPORT = "exports"
REACTIONS = "reactions"

os.makedirs(STORAGE, exist_ok=True)
os.makedirs(EXPORT, exist_ok=True)
os.makedirs(REACTIONS, exist_ok=True)


# --------------------------------------------------
# WEB
# --------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def home():

    return """
<html>

<head>

<title>ETERNA</title>

<style>

body{
background:#0f0f0f;
color:white;
font-family:Arial;
display:flex;
justify-content:center;
padding-top:40px;
}

.card{
background:#1c1c1c;
padding:40px;
border-radius:12px;
width:420px;
box-shadow:0 0 30px rgba(0,0,0,0.6);
}

input{
width:100%;
padding:10px;
margin-top:6px;
margin-bottom:10px;
border-radius:6px;
border:none;
background:#2b2b2b;
color:white;
}

button{
width:100%;
padding:14px;
margin-top:20px;
border:none;
border-radius:8px;
background:white;
color:black;
font-weight:bold;
cursor:pointer;
}

</style>

</head>

<body>

<div class="card">

<h2>ETERNA</h2>

<p>Convierte 6 fotos y 3 frases en un recuerdo emocional.</p>

<form action="/crear-eterna" method="post" enctype="multipart/form-data">

<label>Frase 1</label>
<input name="frase1" required>

<label>Frase 2</label>
<input name="frase2" required>

<label>Frase 3</label>
<input name="frase3" required>

<label>Foto 1</label>
<input type="file" name="fotos" required>

<label>Foto 2</label>
<input type="file" name="fotos" required>

<label>Foto 3</label>
<input type="file" name="fotos" required>

<label>Foto 4</label>
<input type="file" name="fotos" required>

<label>Foto 5</label>
<input type="file" name="fotos" required>

<label>Foto 6</label>
<input type="file" name="fotos" required>

<button type="submit">Crear mi ETERNA</button>

</form>

</div>

</body>
</html>
"""


# --------------------------------------------------
# GENERAR VIDEO
# --------------------------------------------------

def generar_video(eterna_id, imagenes):

    carpeta = os.path.join(STORAGE, eterna_id)

    lista = os.path.join(carpeta, "lista.txt")

    with open(lista,"w") as f:

        for img in imagenes:

            f.write(f"file '{img}'\n")
            f.write("duration 3\n")

    video = os.path.join(EXPORT, f"{eterna_id}.mp4")

    cmd = [

        "ffmpeg",
        "-y",
        "-f","concat",
        "-safe","0",
        "-i",lista,
        "-vf","scale=720:1280",
        "-pix_fmt","yuv420p",
        video

    ]

    subprocess.run(cmd)



# --------------------------------------------------
# CREAR ETERNA
# --------------------------------------------------

@app.post("/crear-eterna")
async def crear_eterna(

    frase1: str = Form(...),
    frase2: str = Form(...),
    frase3: str = Form(...),
    fotos: List[UploadFile] = File(...)

):

    eterna_id = str(uuid.uuid4())

    carpeta = os.path.join(STORAGE, eterna_id)

    os.makedirs(carpeta, exist_ok=True)

    frases = [frase1,frase2,frase3]

    with open(os.path.join(carpeta,"frases.txt"),"w") as f:

        for frase in frases:

            f.write(frase+"\n")

    imagenes = []

    for i,foto in enumerate(fotos):

        contenido = await foto.read()

        ruta = os.path.join(carpeta,f"{i}.jpg")

        with open(ruta,"wb") as f:

            f.write(contenido)

        imagenes.append(ruta)


    thread = threading.Thread(target=generar_video,args=(eterna_id,imagenes))

    thread.start()

    return HTMLResponse(f"""

<html>

<body style="background:black;color:white;text-align:center;padding-top:80px;font-family:Arial">

<h2>Estamos creando tu ETERNA...</h2>

<p>Esto puede tardar unos segundos.</p>

<script>

setInterval(async ()=>{{

let r = await fetch("/estado/{eterna_id}")

let j = await r.json()

if(j.status==="ready"){{

window.location="/ver/{eterna_id}"

}}

}},3000)

</script>

</body>

</html>

""")


# --------------------------------------------------
# ESTADO
# --------------------------------------------------

@app.get("/estado/{eterna_id}")
def estado(eterna_id:str):

    video = os.path.join(EXPORT,f"{eterna_id}.mp4")

    if os.path.exists(video):

        return {"status":"ready"}

    return {"status":"processing"}



# --------------------------------------------------
# VER VIDEO
# --------------------------------------------------

@app.get("/ver/{eterna_id}")
def ver(eterna_id:str):

    video = os.path.join(EXPORT,f"{eterna_id}.mp4")

    return FileResponse(video,media_type="video/mp4")



# --------------------------------------------------
# REACCION
# --------------------------------------------------

@app.post("/reaccion/{eterna_id}")
async def reaccion(

    eterna_id:str,
    video: UploadFile = File(...)

):

    ruta = os.path.join(REACTIONS,f"{eterna_id}.mp4")

    contenido = await video.read()

    with open(ruta,"wb") as f:

        f.write(contenido)

    return {"status":"ok"}
