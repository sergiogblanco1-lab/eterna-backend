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

        # VIDEO BASE (sin deformar)
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

        duracion_total = len(imagenes_normalizadas) * 2

        filtros_texto = []

        # FRASE 1 (inicio)
        if len(frases_limpias) >= 1:
            filtros_texto.append(
                f"drawtext=text='{frases_limpias[0]}':"
                "fontcolor=white:"
                "fontsize=34:"
                "shadowcolor=black:"
                "shadowx=2:"
                "shadowy=2:"
                "x=(w-text_w)/2:"
                "y=h*0.82:"
                "alpha='if(lt(t,0),0, if(lt(t,0.5),(t-0)/0.5, if(lt(t,1.5),1, if(lt(t,2),(2-t)/0.5,0))))'"
            )

        # FRASE 2 (mitad)
        if len(frases_limpias) >= 2:
            inicio_2 = duracion_total / 2
            medio_2 = inicio_2 + 0.5
            fin_fijo_2 = inicio_2 + 1.5
            fin_2 = inicio_2 + 2

            filtros_texto.append(
                f"drawtext=text='{frases_limpias[1]}':"
                "fontcolor=white:"
                "fontsize=34:"
                "shadowcolor=black:"
                "shadowx=2:"
                "shadowy=2:"
                "x=(w-text_w)/2:"
                "y=h*0.82:"
                f"alpha='if(lt(t,{inicio_2}),0, if(lt(t,{medio_2}),(t-{inicio_2})/0.5, if(lt(t,{fin_fijo_2}),1, if(lt(t,{fin_2}),({fin_2}-t)/0.5,0))))'"
            )

        # FRASE 3 (final)
        if len(frases_limpias) >= 3:
            inicio_3 = max(duracion_total - 2, 0)
            medio_3 = inicio_3 + 0.5
            fin_fijo_3 = inicio_3 + 1.5
            fin_3 = duracion_total

            filtros_texto.append(
                f"drawtext=text='{frases_limpias[2]}':"
                "fontcolor=white:"
                "fontsize=34:"
                "shadowcolor=black:"
                "shadowx=2:"
                "shadowy=2:"
                "x=(w-text_w)/2:"
                "y=h*0.82:"
                f"alpha='if(lt(t,{inicio_3}),0, if(lt(t,{medio_3}),(t-{inicio_3})/0.5, if(lt(t,{fin_fijo_3}),1, if(lt(t,{fin_3}),({fin_3}-t)/0.5,0))))'"
            )

        filtro_final = ",".join(filtros_texto)

        comando2 = [
            "ffmpeg",
            "-y",
            "-i", base,
            "-vf", filtro_final,
            "-pix_fmt", "yuv420p",
            "-c:v", "libx264",
            "-preset", "veryfast",
            output_absoluto
        ]

        try:
            subprocess.run(comando1, check=True, capture_output=True, text=True)
            subprocess.run(comando2, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            print("❌ ERROR FFMPEG")
            print(e.stderr)
            raise RuntimeError(f"FFmpeg falló: {e.stderr}") from e

        if not os.path.exists(output_absoluto):
            raise RuntimeError("El vídeo no se generó")

        if os.path.getsize(output_absoluto) == 0:
            raise RuntimeError("El vídeo se creó vacío")

        return output_absoluto

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
