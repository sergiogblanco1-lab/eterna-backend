import os
import subprocess
from typing import List


class VideoEngine:
    def __init__(self):
        pass

    def generar_video_eterna(self, imagenes: List[str], frases: List[str], output: str):

        if not imagenes:
            raise ValueError("No hay imágenes")

        imagenes = [img for img in imagenes if os.path.exists(img)]

        frases = [self._limpiar_texto_ffmpeg(f) for f in frases if f.strip()]
        if not frases:
            frases = ["ETERNA"]

        os.makedirs(os.path.dirname(output), exist_ok=True)

        lista = os.path.join(os.path.dirname(output), "lista.txt")

        # duración corta para no petar RAM
        duracion = 3

        with open(lista, "w") as f:
            for img in imagenes:
                f.write(f"file '{img}'\n")
                f.write(f"duration {duracion}\n")
            f.write(f"file '{imagenes[-1]}'\n")

        base = os.path.join(os.path.dirname(output), "base.mp4")

        # 🎥 VIDEO BASE (zoom suave)
        comando1 = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", lista,
            "-vf",
            "scale=480:854,zoompan=z='min(zoom+0.0015,1.2)':d=90:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
            "-pix_fmt", "yuv420p",
            base
        ]

        # ✨ TEXTO CON FADE
        filtros_texto = "[0:v]"

        tiempos = [
            (frases[0], 1, 4),
            (frases[1] if len(frases) > 1 else "", 5, 8),
            (frases[2] if len(frases) > 2 else "", 9, 12)
        ]

        for i, (texto, t1, t2) in enumerate(tiempos):
            if not texto:
                continue

            alpha = (
                f"if(lt(t,{t1}),0,"
                f"if(lt(t,{t1+1}),(t-{t1}),"
                f"if(lt(t,{t2-1}),1,"
                f"if(lt(t,{t2}),({t2}-t),0))))"
            )

            filtros_texto += (
                f"drawtext=text='{texto}':"
                f"fontcolor=white:fontsize=32:"
                f"x=(w-text_w)/2:y=h*0.8:"
                f"alpha='{alpha}',"
            )

        filtros_texto = filtros_texto.rstrip(",") + "[v]"

        comando2 = [
            "ffmpeg",
            "-y",
            "-i", base,
            "-vf", filtros_texto,
            "-map", "[v]",
            "-pix_fmt", "yuv420p",
            output
        ]

        try:
            subprocess.run(comando1, check=True)
            subprocess.run(comando2, check=True)
            print("✅ VIDEO EMOCIONAL GENERADO")

        except subprocess.CalledProcessError as e:
            print("❌ ERROR:", e)
            raise RuntimeError("Error generando vídeo")

        return output

    def _limpiar_texto_ffmpeg(self, texto: str) -> str:
        return (
            texto.replace("'", "")
            .replace(":", "")
            .replace("\\", "")
            .replace("%", "")
        )
