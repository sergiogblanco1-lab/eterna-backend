import os
import subprocess
from typing import List


class VideoEngine:
    def generar_video_eterna(self, imagenes: List[str], frases: List[str], output: str):
        imagenes = [img for img in imagenes if os.path.exists(img)]

        if not imagenes:
            raise ValueError("No hay imágenes válidas")

        frases_limpias = [self._limpiar_texto_ffmpeg(f) for f in frases if f.strip()]
        if not frases_limpias:
            frases_limpias = ["ETERNA"]

        output_dir = os.path.dirname(output)
        os.makedirs(output_dir, exist_ok=True)

        lista = os.path.abspath(os.path.join(output_dir, "lista.txt"))
        base = os.path.abspath(os.path.join(output_dir, "base.mp4"))
        output_absoluto = os.path.abspath(output)

        imagenes_absolutas = [os.path.abspath(img).replace("\\", "/") for img in imagenes]

        with open(lista, "w", encoding="utf-8") as f:
            for img in imagenes_absolutas:
                f.write(f"file '{img}'\n")
                f.write("duration 2\n")
            f.write(f"file '{imagenes_absolutas[-1]}'\n")

        comando1 = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", lista,
            "-vf", "scale=360:640",
            "-pix_fmt", "yuv420p",
            "-c:v", "libx264",
            "-preset", "veryfast",
            base
        ]

        texto = frases_limpias[0]

        comando2 = [
            "ffmpeg",
            "-y",
            "-i", base,
            "-vf",
            f"drawtext=text='{texto}':fontcolor=white:fontsize=28:x=(w-text_w)/2:y=h*0.8",
            "-pix_fmt", "yuv420p",
            "-c:v", "libx264",
            "-preset", "veryfast",
            output_absoluto
        ]

        try:
            resultado1 = subprocess.run(
                comando1,
                check=True,
                capture_output=True,
                text=True
            )
            print("✅ BASE VIDEO GENERADO")
            print(resultado1.stderr)

            resultado2 = subprocess.run(
                comando2,
                check=True,
                capture_output=True,
                text=True
            )
            print("✅ VIDEO FINAL GENERADO")
            print(resultado2.stderr)

        except subprocess.CalledProcessError as e:
            print("❌ ERROR FFMPEG")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)
            raise RuntimeError(f"FFmpeg falló: {e.stderr}") from e

        if not os.path.exists(output_absoluto):
            raise RuntimeError("El vídeo no se generó")

        if os.path.getsize(output_absoluto) == 0:
            raise RuntimeError("El vídeo se creó vacío")

        return output_absoluto

    def _limpiar_texto_ffmpeg(self, texto: str) -> str:
        return (
            texto.replace("'", "")
            .replace('"', "")
            .replace(":", "")
            .replace("\\", "")
            .replace("%", "")
            .replace("\n", " ")
            .strip()
        )
