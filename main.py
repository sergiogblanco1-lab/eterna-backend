@app.get("/ver/{order_id}", response_class=HTMLResponse)
def ver_eterna(order_id: str):

    order = ORDERS.get(order_id)

    if not order:
        return HTMLResponse("<h1>No existe</h1>")

    return HTMLResponse(f"""
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>

    <body style="background:black;color:white;text-align:center;font-family:Arial;display:flex;justify-content:center;align-items:center;height:100vh;">

        <div id="start">

            <h1 style="font-size:28px;">ETERNA</h1>

            <p style="margin-top:20px;">
                Este momento será guardado para quien lo creó ❤️
            </p>

            <button onclick="startExperience()" style="
                margin-top:40px;
                padding:15px 25px;
                font-size:16px;
                background:white;
                color:black;
                border:none;
                border-radius:10px;
            ">
                Aceptar y continuar
            </button>

        </div>

        <div id="countdown" style="display:none;font-size:60px;">
            3
        </div>

        <div id="experience" style="display:none;">

            <h1>ETERNA</h1>

            <p style="margin-top:20px;">
                Esto se está viviendo contigo ❤️
            </p>

            <div style="margin-top:40px;font-size:24px;">
                <p>{order["phrase_1"]}</p>
                <p>{order["phrase_2"]}</p>
                <p>{order["phrase_3"]}</p>
            </div>

            <h2 style="margin-top:60px;color:#00ff88;">
                Has recibido {order["amount"]}€
            </h2>

            <p style="margin-top:40px;">
                Tu momento ha sido vivido ❤️
            </p>

        </div>

        <script>

        function startExperience() {{

            document.getElementById("start").style.display = "none";
            document.getElementById("countdown").style.display = "block";

            let count = 3;

            let interval = setInterval(() => {{

                count--;

                if (count > 0) {{
                    document.getElementById("countdown").innerText = count;
                }} else {{
                    clearInterval(interval);

                    document.getElementById("countdown").style.display = "none";
                    document.getElementById("experience").style.display = "block";
                }}

            }}, 1000);
        }}

        </script>

    </body>
    </html>
    """)
