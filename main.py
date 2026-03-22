# =========================
# FIXES IMPORTANTES
# =========================

MAX_VIDEO_SIZE = 30 * 1024 * 1024  # 30MB
ALLOWED_VIDEO_TYPES = {"video/webm", "video/mp4"}


def reaction_exists(order: dict) -> bool:
    if order.get("reaction_public_url"):
        return True
    filepath = order.get("reaction_video")
    return bool(filepath) and os.path.exists(filepath)


# =========================
# UPLOAD VIDEO (CORREGIDO)
# =========================

@app.post("/upload-video")
async def upload_video(
    order_id: str = Form(...),
    video: UploadFile = File(...),
):
    order = get_order_or_404(order_id)

    if video.content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(status_code=400, detail="Formato no permitido")

    filepath = reaction_video_path(order_id)
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

        if os.path.getsize(filepath) == 0:
            raise HTTPException(status_code=400, detail="Vídeo vacío")

        order["reaction_video"] = filepath
        order["reaction_uploaded"] = True

        public_video_url = None
        try:
            public_video_url = upload_video_to_r2(filepath, f"{order_id}.webm")
        except Exception as e:
            print("Error R2:", e)

        order["reaction_public_url"] = public_video_url

        return JSONResponse({
            "status": "ok",
            "reaction_url": f"{PUBLIC_BASE_URL}/reaccion/{order_id}",
            "cashout_url": f"{PUBLIC_BASE_URL}/cobrar/{order_id}",
            "public_video_url": public_video_url,
        })

    finally:
        await video.close()


# =========================
# RESUMEN (CAMBIO CLAVE)
# =========================

@app.get("/resumen/{order_id}", response_class=HTMLResponse)
def resumen(order_id: str):
    order = get_order_or_404(order_id)

    experiencia_url = f"{PUBLIC_BASE_URL}/pedido/{order_id}"

    whatsapp_experiencia_url = whatsapp_link(
        order["recipient_phone"],
        f"Hola ❤️\n\n{order['customer_name']} te ha enviado algo especial.\n\n{experiencia_url}"
    )

    has_reaction = reaction_exists(order)

    if has_reaction:
        reaction_share_target = f"{PUBLIC_BASE_URL}/reaccion/{order_id}"

        regalante_whatsapp_url = whatsapp_link(
            order["customer_phone"],
            f"No sé cómo explicarlo... pero este momento ya forma parte de ETERNA ❤️\n\n{reaction_share_target}"
        )

        main_cta = f"""
        <a href="{regalante_whatsapp_url}" target="_blank">
            <button class="light main-btn">Enviar reacción ❤️</button>
        </a>
        <a href="/reaccion/{order_id}" target="_blank">
            <button class="ghost main-btn">Ver emoción</button>
        </a>
        """

    else:
        main_cta = f"""
        <a href="{whatsapp_experiencia_url}" target="_blank">
            <button class="whatsapp main-btn">Enviar ETERNA</button>
        </a>
        """

    return f"""
    <html>
    <body style="background:black;color:white;text-align:center;padding:40px;font-family:Arial;">
        <h1>ETERNA lista ❤️</h1>
        {main_cta}
    </body>
    </html>
    """


# =========================
# REACCIÓN FINAL (MEJORADA)
# =========================

@app.get("/reaccion/{order_id}", response_class=HTMLResponse)
def reaccion(order_id: str):
    order = get_order_or_404(order_id)

    if not reaction_exists(order):
        return HTMLResponse("<h1>Esperando reacción...</h1>")

    if not order.get("cashout_completed"):
        return RedirectResponse(url=f"/cobrar/{order_id}", status_code=303)

    video_source = order.get("reaction_public_url") or f"/video/{order_id}"
    share_url = f"{PUBLIC_BASE_URL}/reaccion/{order_id}"

    return f"""
    <html>
    <body style="background:black;color:white;text-align:center;padding:20px;">
        <h1>ETERNA ❤️</h1>

        <video controls autoplay style="width:100%;max-width:600px;">
            <source src="{video_source}" type="video/webm">
        </video>

        <br><br>

        <a href="{share_url}" target="_blank">
            <button>Compartir</button>
        </a>

        <a href="{video_source}" target="_blank">
            <button>Descargar</button>
        </a>

    </body>
    </html>
    """