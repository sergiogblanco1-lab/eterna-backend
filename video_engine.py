import os
import subprocess


class VideoEngine:
    def __init__(self):
        pass

    def generar_video_eterna(self, imagenes, frases, output):
        """
        Versión simple y robusta para comprobar que FFmpeg funciona en Render.

        Hace esto:
        - usa la primera imagen
        - pone la primera frase
        - genera un vídeo vertical de 5 segundos
        """

        if not imagenes:
            raise ValueError("No hay imágenes para generar el vídeo")

        img = imagenes[0]

        if not os.path.exists(img):
            raise FileNotFoundError(f"La imagen no existe: {img}")

        texto = "ETERNA"
        if frases and len(frases) > 0 and frases[0].strip():
            texto = frases[0].strip()

        texto = self._limpiar_texto_ffmpeg(texto)

        output_dir = os.path.dirname(output)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        filtro = (
            "scale=720:1280:force_original_aspect_ratio=increase,"
            "crop=720:1280,"
            f"drawtext=text='{texto}':"
            "fontcolor=white:"
            "fontsize=48:"
            "x=(w-text_w)/2:"
            "y=(h-text_h)/2"
        )

        comando = [
            "ffmpeg",
            "-y",
            "-loop", "1",
            "-i", img,
            "-t", "5",
            "-vf", filtro,
            "-r", "30",
            "-pix_fmt", "yuv420p",
            "-c:v", "libx264",
            output
        ]

        print("🎬 Ejecutando FFmpeg...")
        print(" ".join(comando))

        try:
            resultado = subprocess.run(
                comando,
                check=True,
                capture_output=True,
                text=True
            )
            print("✅ VIDEO GENERADO:", output)
            print("STDOUT:", resultado.stdout)
            print("STDERR:", resultado.stderr)

        except subprocess.CalledProcessError as e:
            print("❌ ERROR AL GENERAR VIDEO")
            print("Código:", e.returncode)
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)
            raise RuntimeError(f"FFmpeg falló: {e.stderr}") from e

        if not os.path.exists(output):
            raise RuntimeError("FFmpeg terminó pero el archivo de vídeo no existe")

        size = os.path.getsize(output)
        if size == 0:
            raise RuntimeError("El vídeo se creó vacío")

        return output

    def _limpiar_texto_ffmpeg(self, texto: str) -> str:
        """
        Limpia caracteres que suelen romper drawtext.
        """
        texto = texto.replace("\\", "")
        texto = texto.replace(":", "")
        texto = texto.replace("'", "")
        texto = texto.replace('"', "")
        texto = texto.replace("%", "")
        texto = texto.replace("\n", " ")
        return texto.strip() or "ETERNA"
