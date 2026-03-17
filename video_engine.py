import os
import shutil
import subprocess
from typing import List


class VideoEngine:
    def __init__(self, ffmpeg_bin: str = "ffmpeg"):
        self.ffmpeg_bin = ffmpeg_bin
        self.font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    def _check_ffmpeg(self) -> None:
        if shutil.which(self.ffmpeg_bin) is None:
            raise Exception("FFmpeg no está instalado o no está disponible en el sistema")

        if not os.path.exists(self.font_path):
            raise Exception(f"No se encontró la fuente necesaria: {self.font_path}")

    def _run(self, command: List[str]) -> None:
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(result.stderr.strip() or "Error ejecutando FFmpeg")

    def _escape_drawtext(self, text: str) -> str:
        if not text:
            return ""

        return (
            text.replace("\\", "\\\\")
            .replace(":", "\\:")
            .replace("'", "\\'")
            .replace(",", "\\,")
            .replace("[", "\\[")
            .replace("]", "\\]")
            .replace("%", "\\%")
        )

    def _apply_drawtext(self, input_label: str, output_label: str, text: str, start: float, end: float) -> str:
        text = self._escape_drawtext(text)
        fade = 0.8

        alpha_expr = (
            f"if(lt(t,{start}),0,"
            f"if(lt(t,{start + fade}),(t-{start})/{fade},"
            f"if(lt(t,{end - fade}),1,"
            f"if(lt(t,{end}),({end}-t)/{fade},0))))"
        )

        y_expr = (
            f"h*0.78+"
            f"if(lt(t,{start}),28,"
            f"if(lt(t,{start + fade}),28-28*(t-{start})/{fade},"
            f"if(lt(t,{end - fade}),0,"
            f"if(lt(t,{end}),28*(t-({end - fade}))/{fade},28))))"
        )

        return (
            f"[{input_label}]drawtext="
            f"fontfile='{self.font_path}':"
            f"text='{text}':"
            f"fontcolor=white:"
            f"fontsize=42:"
            f"line_spacing=8:"
            f"shadowcolor=black@0.45:"
            f"shadowx=2:"
            f"shadowy=2:"
            f"x=(w-text_w)/2:"
            f"y={y_expr}:"
            f"alpha='{alpha_expr}'"
            f"[{output_label}]"
        )

    def generate_video(self, order_id: str, photos: list[str], phrases: list[str], output_path: str) -> str:
        self._check_ffmpeg()

        if not photos:
            raise Exception("No hay fotos para generar el vídeo")

        output_path = os.path.abspath(output_path)
        output_dir = os.path.dirname(output_path)
        os.makedirs(output_dir, exist_ok=True)

        duracion_foto = 5.5
        transicion = 0.8
        fps = 30
        frames_por_foto = int(duracion_foto * fps)

        inputs = []
        filter_parts = []

        for i, photo_path in enumerate(photos):
            photo_path = os.path.abspath(photo_path)

            if not os.path.exists(photo_path):
                raise Exception(f"No existe la foto: {photo_path}")

            inputs.extend([
                "-loop", "1",
                "-t", str(duracion_foto),
                "-i", photo_path
            ])

            filter_parts.append(
                f"[{i}:v]"
                f"scale=900:1600:force_original_aspect_ratio=increase,"
                f"crop=720:1280,"
                f"zoompan="
                f"z='min(zoom+0.0008,1.08)':"
                f"x='iw/2-(iw/zoom/2)':"
                f"y='ih/2-(ih/zoom/2)':"
                f"d={frames_por_foto}:s=720x1280:fps={fps},"
                f"setpts=PTS-STARTPTS,"
                f"format=yuv420p"
                f"[v{i}]"
            )

        current = "v0"
        offset = duracion_foto - transicion

        for i in range(1, len(photos)):
            next_v = f"v{i}"
            out = f"x{i}"
            filter_parts.append(
                f"[{current}][{next_v}]"
                f"xfade=transition=fade:duration={transicion}:offset={offset}"
                f"[{out}]"
            )
            current = out
            offset += duracion_foto - transicion

        # Frases
        total_duration = len(photos) * duracion_foto - (len(photos) - 1) * transicion

        frase1_start = 2.0
        frase1_end = min(7.5, total_duration - 1.0)

        frase2_start = max(9.0, total_duration * 0.35)
        frase2_end = min(frase2_start + 5.5, total_duration - 1.0)

        frase3_start = max(16.0, total_duration * 0.68)
        frase3_end = min(frase3_start + 6.0, total_duration - 0.4)

        text_index = 1
        current_text_stream = current

        if len(phrases) > 0 and phrases[0]:
            out_label = f"t{text_index}"
            filter_parts.append(
                self._apply_drawtext(current_text_stream, out_label, phrases[0], frase1_start, frase1_end)
            )
            current_text_stream = out_label
            text_index += 1

        if len(phrases) > 1 and phrases[1]:
            out_label = f"t{text_index}"
            filter_parts.append(
                self._apply_drawtext(current_text_stream, out_label, phrases[1], frase2_start, frase2_end)
            )
            current_text_stream = out_label
            text_index += 1

        if len(phrases) > 2 and phrases[2]:
            out_label = f"t{text_index}"
            filter_parts.append(
                self._apply_drawtext(current_text_stream, out_label, phrases[2], frase3_start, frase3_end)
            )
            current_text_stream = out_label

        filter_complex = ";".join(filter_parts)

        command = [
            self.ffmpeg_bin,
            "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", f"[{current_text_stream}]",
            "-r", str(fps),
            "-pix_fmt", "yuv420p",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            output_path
        ]

        self._run(command)

        if not os.path.exists(output_path):
            raise Exception("El vídeo no se generó correctamente")

        return output_path
