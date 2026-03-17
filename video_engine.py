import os
import subprocess
from typing import List


class VideoEngine:
    def __init__(self):
        pass

    def generar_video_eterna(self, imagenes: List[str], frases: List[str], output: str):
        """
        Genera un vídeo vertical con varias fotos y frases repartidas en el tiempo.
        Versión estable para Render + FFmpeg.

        - 6 fotos
        - 7 segundos por foto
        - total aprox 42 segundos
        - 3 frases repartidas
        """

        if not imagenes:
            raise ValueError("No hay imágenes para generar el vídeo")

        imagenes = [img for img in imagenes if os.path.exists(img)]
        if not imagenes:
            raise ValueError("Ninguna imagen existe en disco")

        frases_limpias = []
        for frase in frases:
            if frase and frase.strip():
                frases_limpias.append(self._limpiar_texto_ffmpeg(frase.strip()))

        if not frases_limpias:
            frases_limpias = ["ETERNA"]

        output_dir = os.path.dirname(output)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        duracion_por_foto = 7
        fade_duracion = 1

        comando = ["ffmpeg", "-y"]

        # inputs
        for img in imagenes:
            comando += ["-loop", "1", "-t", str(duracion_por_foto), "-i", img]

        filtros = []

        # preparar cada imagen
        for i in range(len(imagenes)):
            filtros.append(
                f"[{i}:v]"
                f"scale=720:1280:force_original_aspect_ratio=increase,"
                f"crop=720:1280,"
                f"setsar=1,"
                f"format=yuv420p,"
                f"fade=t=in:st=0:d={fade_duracion},"
                f"fade=t=out:st={duracion_por_foto - fade_duracion}:d={fade_duracion}"
                f"[v{i}]"
            )

        # concatenar todas las imágenes
        concat_inputs = "".join([f"[v{i}]" for i in range(len(imagenes))])
        filtros.append(
            f"{concat_inputs}concat=n={len(imagenes)}:v=1:a=0[base]"
        )

        # frases en distintos momentos
        video_total = len(imagenes) * duracion_por_foto

        momentos = []
        if len(frases_limpias) == 1:
            momentos = [(frases_limpias[0], 3, 8)]
        elif len(frases_limpias) == 2:
            momentos = [
                (frases_limpias[0], 4, 10),
                (frases_limpias[1], 18, 24),
            ]
        else:
            momentos = [
                (frases_limpias[0], 4, 10),
                (frases_limpias[1], max(12, video_total // 2 - 3), max(18, video_total // 2 + 3)),
                (frases_limpias[2], video_total - 10, video_total - 4),
            ]

        texto_chain = "[base]"
        for idx, (texto, t_inicio, t_fin) in enumerate(momentos):
            out_label = f"[txt{idx}]"

            # alpha para que aparezca y desaparezca suave
            alpha_expr = (
                f"if(lt(t,{t_inicio}),0,"
                f"if(lt(t,{t_inicio + 1}),(t-{t_inicio})/1,"
                f"if(lt(t,{t_fin - 1}),1,"
                f"if(lt(t,{t_fin}),({t_fin}-t)/1,0))))"
            )

            filtros.append(
                f"{texto_chain}"
                f"drawtext=text='{texto}':"
                f"fontcolor=white:"
                f"fontsize=54:"
                f"x=(w-text_w)/2:"
                f"y=h*0.78:"
                f"alpha='{alpha_expr}'"
                f"{out_label}"
            )
            texto_chain = out_label

        filtros.append(f"{texto_chain}format=yuv420p[vfinal]")

        filter_complex = ";".join(filtros)

        comando += [
            "-filter_complex", filter_complex,
            "-map", "[vfinal]",
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
            raise RuntimeError("El vídeo no se generó")

        if os.path.getsize(output) == 0:
            raise RuntimeError("El vídeo se creó vacío")

        return output

    def _limpiar_texto_ffmpeg(self, texto: str) -> str:
        texto = texto.replace("\\", "")
        texto = texto.replace(":", "")
        texto = texto.replace("'", "")
        texto = texto.replace('"', "")
        texto = texto.replace("%", "")
        texto = texto.replace("\n", " ")
        return texto.strip() or "ETERNA"
