import os
import subprocess
from typing import List
from PIL import Image, ImageOps


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

        # carpeta temporal para imágenes corregidas
        normalizadas_dir = os.path.join(output_dir, "normalizadas")
        os.makedirs(normalizadas_dir, exist_ok=True)

        imagenes_normalizadas = []
        for i, img_path in enumerate(imagenes, start=1):
            nueva = os.path.join(normalizadas_dir, f"img_{i}.jpg")
            self._normalizar_imagen(img_path, nueva)
            imagenes_normalizadas.append(os.path.abspath(nueva).replace("\\", "/"))

        with open(lista, "w", encoding="utf-8") as f:
            for img in imagenes_normalizadas:
                f.write(f"file '{img}'\n")
                f.write("duration 2\n")
            f.write(f"file '{imagenes_normalizadas[-1]}'\n")

        # NO deformar: escalar manteniendo proporción + fondo negro vertical
        comando1 = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", lista,
            "-vf",
            (
                "scale=360:640:force_original_aspect_ratio=decrease,"
                "pad=360:640:(ow-iw)/2:(oh-ih)/2:black"
            ),
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
            (
                f"drawtext=text='{texto}':"
                "fontcolor=white:"
                "fontsize=28:"
                "x=(w-text_w)/2:"
                "y=h*0.82"
            ),
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

    def _normalizar_imagen(self, origen: str, destino: str):
        with Image.open(origen) as img:
            # corrige fotos giradas del móvil
            img = ImageOps.exif_transpose(img)

            # asegurar modo compatible
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            elif img.mode == "L":
                img = img.convert("RGB")

            img.save(destino, "JPEG", quality=92)

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
