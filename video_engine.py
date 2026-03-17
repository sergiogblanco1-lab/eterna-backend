import subprocess
import shutil
from typing import List, Optional


class VideoEngine:
    def __init__(self, ffmpeg_bin: str = "ffmpeg"):
        self.ffmpeg_bin = ffmpeg_bin

        if shutil.which(self.ffmpeg_bin) is None:
            raise Exception("FFmpeg no está instalado")

    def generar_video(
        self,
        imagenes: List[str],
        salida: str,
        frases: Optional[List[str]] = None,
        music_path: Optional[str] = None,
        image_duration: int = 5,
        transition_duration: int = 1,
        width: int = 720,
        height: int = 1280,
        fps: int = 30,
    ):
        if not imagenes:
            raise Exception("No hay imágenes")

        inputs = []
        filtros = []

        fade = 1

        for i, img in enumerate(imagenes):
            inputs.extend(["-loop", "1", "-t", str(image_duration), "-i", img])

            frames = image_duration * fps

            filtros.append(
                f"[{i}:v]"
                f"scale=1280:720:force_original_aspect_ratio=increase,"
                f"crop=720:1280,"
                f"zoompan=z='min(zoom+0.0005,1.1)':d={frames}:s={width}x{height},"
                f"fade=t=in:st=0:d={fade},"
                f"fade=t=out:st={image_duration-fade}:d={fade},"
                f"setpts=PTS-STARTPTS"
                f"[v{i}]"
            )

        concat_inputs = "".join([f"[v{i}]" for i in range(len(imagenes))])
        filtros.append(f"{concat_inputs}concat=n={len(imagenes)}:v=1:a=0[v]")

        if frases:
            base = "[v]"
            for i, frase in enumerate(frases[:3]):
                frase_limpia = (
                    str(frase)
                    .replace("\\", "\\\\")
                    .replace(":", "\\:")
                    .replace("'", "\\'")
                    .replace("%", "\\%")
                )

                start = 3 + (i * 10)
                end = start + 5
                out = f"[txt{i}]"

                filtros.append(
                    f"{base}drawtext="
                    f"text='{frase_limpia}':"
                    f"fontcolor=white:"
                    f"fontsize=48:"
                    f"x=(w-text_w)/2:"
                    f"y=h*0.75:"
                    f"shadowcolor=black@0.7:"
                    f"shadowx=2:"
                    f"shadowy=2:"
                    f"alpha='if(lt(t,{start}),0,"
                    f"if(lt(t,{start+1}),(t-{start}),"
                    f"if(lt(t,{end}),1,"
                    f"if(lt(t,{end+1}),1-(t-{end}),0))))'"
                    f"{out}"
                )
                base = out

            final = base
        else:
            final = "[v]"

        filter_complex = ";".join(filtros)

        cmd = [
            self.ffmpeg_bin,
            "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", final,
            "-r", str(fps),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            salida
        ]

        print("🎬 COMANDO:", " ".join(cmd))

        proc = subprocess.run(cmd, capture_output=True, text=True)

        print("STDOUT:", proc.stdout)
        print("STDERR:", proc.stderr)

        if proc.returncode != 0:
            raise Exception(proc.stderr)

        return salida
