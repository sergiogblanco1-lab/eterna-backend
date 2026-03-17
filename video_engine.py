import subprocess
from pathlib import Path


class VideoEngine:

    def generar_video(
        self,
        imagenes,
        salida,
        frases=None,
        music_path=None,
        image_duration=5,
        transition_duration=1,
        width=720,
        height=1280,
        fps=30,
    ):
        """
        Genera un vídeo simple, estable y compatible.
        """

        if not imagenes:
            raise Exception("No hay imágenes para generar el vídeo")

        # Carpeta temporal
        temp_dir = Path(salida).parent

        inputs = []
        filter_complex = ""

        total = len(imagenes)

        # 🔹 PREPARAR INPUTS
        for img in imagenes:
            inputs.extend(["-loop", "1", "-t", str(image_duration), "-i", img])

        # 🔹 ESCALADO + NORMALIZACIÓN
        for i in range(total):
            filter_complex += (
                f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=cover,"
                f"fps={fps},format=yuv420p[v{i}];"
            )

        # 🔹 CONCATENAR TODO
        concat_inputs = "".join([f"[v{i}]" for i in range(total)])

        filter_complex += f"{concat_inputs}concat=n={total}:v=1:a=0[v]"

        # 🔹 COMANDO FINAL
        cmd = [
            "ffmpeg",
            "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-r", str(fps),

            # 👇 CLAVE PARA QUE FUNCIONE EN TODOS LOS DISPOSITIVOS
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",

            salida
        ]

        print("🎬 Ejecutando FFmpeg...")
        print(" ".join(cmd))

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print("❌ ERROR FFMPEG:")
            print(result.stderr)
            raise Exception("Error generando vídeo")

        # 🔹 VALIDACIÓN FINAL
        if not Path(salida).exists():
            raise Exception("El vídeo no se ha generado")

        print("✅ Vídeo generado correctamente:", salida)
