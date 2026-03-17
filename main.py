from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

app = FastAPI(title="ETERNA backend")


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
                font-family: Arial, sans-serif;
                max-width: 760px;
                margin: 0 auto;
                padding: 30px 20px;
            }
            h1 {
                margin-bottom: 8px;
            }
            p {
                color: #cccccc;
                margin-bottom: 24px;
                line-height: 1.5;
            }
            form {
                display: flex;
                flex-direction: column;
                gap: 12px;
            }
            input, textarea, button {
                width: 100%;
                box-sizing: border-box;
                padding: 14px;
                border-radius: 10px;
                border: 1px solid #333;
                font-size: 16px;
            }
            input, textarea {
                background: #171717;
                color: white;
            }
            textarea {
                min-height: 90px;
                resize: vertical;
            }
            button {
                background: #e7c27d;
                color: black;
                border: none;
                font-weight: bold;
                cursor: pointer;
            }
            .box {
                background: #111;
                padding: 20px;
                border-radius: 16px;
                border: 1px solid #222;
            }
            .note {
                font-size: 14px;
                color: #aaa;
            }
            .success-box {
                background: #111;
                padding: 24px;
                border-radius: 16px;
                border: 1px solid #222;
            }
            .ok {
                color: #9fe870;
                font-weight: bold;
            }
            code {
                background: #1b1b1b;
                padding: 3px 6px;
                border-radius: 6px;
                color: #f1f1f1;
                word-break: break-word;
            }
            a.button {
                display: inline-block;
                margin-top: 18px;
                padding: 12px 18px;
                border-radius: 999px;
                background: #e7c27d;
                color: black;
                font-weight: bold;
                text-decoration: none;
            }
        </style>
    </head>
    <body>
        <h1>ETERNA</h1>
        <p>Hay momentos que merecen quedarse para siempre.</p>

        <div class="box">
            <form action="/crear-eterna" method="post" enctype="multipart/form-data" novalidate>
                <input name="nombre" placeholder="Tu nombre">
                <input name="email" placeholder="Tu email">
                <input name="telefono_regalante" placeholder="Tu teléfono">

                <input name="nombre_destinatario" placeholder="Nombre destinatario">
                <input name="telefono_destinatario" placeholder="Teléfono destinatario">

                <textarea name="frase1" placeholder="Frase 1"></textarea>
                <textarea name="frase2" placeholder="Frase 2"></textarea>
                <textarea name="frase3" placeholder="Frase 3"></textarea>

                <label>Sube 6 fotos</label>
                <input name="foto1" type="file">
                <input name="foto2" type="file">
                <input name="foto3" type="file">
                <input name="foto4" type="file">
                <input name="foto5" type="file">
                <input name="foto6" type="file">

                <div class="note">Ahora solo estamos comprobando que el formulario se envía.</div>

                <button type="submit">Crear mi ETERNA</button>
            </form>
        </div>
    </body>
    </html>
    """


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/crear-eterna", response_class=HTMLResponse)
async def crear_eterna(request: Request):
    form = await request.form()

    nombre = form.get("nombre")
    email = form.get("email")
    telefono_regalante = form.get("telefono_regalante")
    nombre_destinatario = form.get("nombre_destinatario")
    telefono_destinatario = form.get("telefono_destinatario")
    frase1 = form.get("frase1")
    frase2 = form.get("frase2")
    frase3 = form.get("frase3")

    fotos = [
        form.get("foto1"),
        form.get("foto2"),
        form.get("foto3"),
        form.get("foto4"),
        form.get("foto5"),
        form.get("foto6"),
    ]

    nombres_fotos = []
    for foto in fotos:
        if foto is not None and getattr(foto, "filename", None):
            nombres_fotos.append(foto.filename)

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Formulario recibido</title>
        <style>
            body {{
                background: #0b0b0b;
                color: white;
                font-family: Arial, sans-serif;
                max-width: 760px;
                margin: 0 auto;
                padding: 30px 20px;
            }}
            .success-box {{
                background: #111;
                padding: 24px;
                border-radius: 16px;
                border: 1px solid #222;
            }}
            .ok {{
                color: #9fe870;
                font-weight: bold;
            }}
            p {{
                color: #ddd;
                line-height: 1.6;
            }}
            code {{
                background: #1b1b1b;
                padding: 3px 6px;
                border-radius: 6px;
                color: #f1f1f1;
                word-break: break-word;
            }}
            a.button {{
                display: inline-block;
                margin-top: 18px;
                padding: 12px 18px;
                border-radius: 999px;
                background: #e7c27d;
                color: black;
                font-weight: bold;
                text-decoration: none;
            }}
        </style>
    </head>
    <body>
        <div class="success-box">
            <h1>FORMULARIO FUNCIONA 🔥</h1>
            <p class="ok">El backend ha recibido la información.</p>

            <p><strong>Nombre:</strong> <code>{nombre}</code></p>
            <p><strong>Email:</strong> <code>{email}</code></p>
            <p><strong>Teléfono regalante:</strong> <code>{telefono_regalante}</code></p>
            <p><strong>Destinatario:</strong> <code>{nombre_destinatario}</code></p>
            <p><strong>Teléfono destinatario:</strong> <code>{telefono_destinatario}</code></p>
            <p><strong>Frase 1:</strong> <code>{frase1}</code></p>
            <p><strong>Frase 2:</strong> <code>{frase2}</code></p>
            <p><strong>Frase 3:</strong> <code>{frase3}</code></p>
            <p><strong>Fotos recibidas:</strong> <code>{", ".join(nombres_fotos) if nombres_fotos else "ninguna"}</code></p>

            <a class="button" href="/">Volver</a>
        </div>
    </body>
    </html>
    """
