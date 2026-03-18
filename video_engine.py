import os
import subprocess
from typing import List, Optional
from PIL import Image, ImageOps


class VideoEngine:
    def generar_video_eterna(
        self,
        imagenes: List[str],
        frases: List[str],
        output: str,
        video_regalante: Optional[str] = None,
        regalo_activo: bool = False,
        regalo_amount_eur: float = 0.0,
        regalo_mensaje: str = "",
        nombre_destinatario: str = "",
        nombre_remitente: str = "",
    ):
        imagenes = [img for img in imagenes if os.path.exists(img)]

        if not imagenes:
            raise ValueError("No hay imágenes válidas")

        if len(imagenes) != 6:
            raise ValueError("ETERNA necesita exactamente 6 imágenes")

        frases_limpias = [self._limpiar_texto_ffmpeg(f) for f in frases if f.strip()]
        if len(frases_limpias) < 3:
            raise ValueError("Se necesitan 3 frases válidas")

        output_dir = os.path.dirname(output)
        os.makedirs(output_dir, exist_ok=True)

        lista = os.path.join(output_dir, "lista.txt")
        base = os.path.join(output_dir, "base.mp4")
        texto_video = os.path.join(output_dir, "texto.mp4")
        final_lista = os.path.join(output_dir, "final_lista.txt")
        final_temp = os.path.join(output_dir, "final_temp.mp4")

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
                f.write("duration 5\n")
            f.write(f"file '{imagenes_normalizadas[-1]}'\n")

        filtro_base = (
            "zoompan="
            "z='if(lte(on,1),1.0,min(zoom+0.0008,1.10))':"
            "x='iw/2-(iw/zoom/2)':"
            "y='ih/2-(ih/zoom/2)':"
            "d=125:"
            "s=720x1280,"
            "fps=25,"
            "eq=saturation='if(lt(t,10),0, if(lt(t,20),(t-10)/10,1))',"
            "format=yuv420p"
        )

        comando1 = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", lista,
            "-vf", filtro_base,
            "-pix_fmt", "yuv420p",
            "-c:v", "libx264",
            "-preset", "veryfast",
            base
        ]

        duracion_total = 30
        filtros_texto = []

        overlays = [
            ("Hay momentos que merecen quedarse para siempre", 0, 4),
            (frases_limpias[0], 5, 9),
            (frases_limpias[1], 12, 16),
            (frases_limpias[2], 19, 23),
            ("Este momento es para ti", 25, 28),
        ]

        if regalo_activo and regalo_amount_eur > 0:
            overlays.append((f"Y además... {regalo_amount_eur:.2f}€ para ti", 28, 30))

        for texto, inicio, fin in overlays:
            texto = self._limpiar_texto_ffmpeg(texto)
            filtros_texto.append(
                f"drawtext=text='{texto}':"
                f"fontcolor=white:"
                f"fontsize=36:"
                f"shadowcolor=black:"
                f"shadowx=2:"
                f"shadowy=2:"
                f"x=(w-text_w)/2:"
                f"y=h*0.82:"
                f"enable='between(t,{inicio},{fin})':"
                f"alpha='if(lt(t,{inicio + 0.5}), (t-{inicio})/0.5, if(lt(t,{fin - 0.5}), 1, ({fin}-t)/0.5))'"
            )

        filtro_final = ",".join(filtros_texto) if filtros_texto else "null"

        comando2 = [
            "ffmpeg",
            "-y",
            "-i", base,
            "-vf", filtro_final,
            "-pix_fmt", "yuv420p",
            "-c:v", "libx264",
            "-preset", "veryfast",
            texto_video
        ]

        with open(final_lista, "w", encoding="utf-8") as f:
            f.write(f"file '{os.path.abspath(texto_video).replace(chr(92), '/')}'\n")
            if video_regalante and os.path.exists(video_regalante):
                f.write(f"file '{os.path.abspath(video_regalante).replace(chr(92), '/')}'\n")

        comando3 = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", final_lista,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-pix_fmt", "yuv420p",
            "-preset", "veryfast",
            final_temp
        ]

        try:
            subprocess.run(comando1, check=True, capture_output=True, text=True)
            subprocess.run(comando2, check=True, capture_output=True, text=True)
            subprocess.run(comando3, check=True, capture_output=True, text=True)

            os.replace(final_temp, output)
            print("✅ VIDEO FINAL GUARDADO EN:", output)
        except subprocess.CalledProcessError as e:
            print("❌ ERROR FFMPEG")
            print(e.stderr)
            raise RuntimeError(f"FFmpeg falló: {e.stderr}") from e

        if not os.path.exists(output):
            raise RuntimeError(f"El vídeo no se generó en: {output}")

        if os.path.getsize(output) == 0:
            raise RuntimeError("El vídeo se creó vacío")

        return output

    def _normalizar_imagen(self, origen: str, destino: str):
        with Image.open(origen) as img:
            img = ImageOps.exif_transpose(img)

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
