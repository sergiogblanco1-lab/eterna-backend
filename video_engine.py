import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional


class VideoEngine:
    """
    Generador de vídeo vertical 720x1280 para ETERNA.
    - Une fotos con transición suave entre ellas
    - Añade un zoom suave cinematográfico
    - Inserta frases con fade in / fade out
    - Exporta MP4 compatible
    """

    DEFAULT_FONT_PATHS = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]

    def __init__(
        self,
        ffmpeg_bin: str = "ffmpeg",
        ffprobe_bin: str = "ffprobe",
        font_path: Optional[str] = None,
    ):
        self.ffmpeg_bin = ffmpeg_bin
        self.ffprobe_bin = ffprobe_bin
        self._check_ffmpeg_tools()
        self.font_path = font_path or self._find_default_font()

        if not self.font_path:
            raise RuntimeError("No se encontró una fuente válida en el servidor para FFmpeg.")

    def _check_ffmpeg_tools(self):
        if shutil.which(self.ffmpeg_bin) is None:
            raise FileNotFoundError(f"No se encontró FFmpeg: {self.ffmpeg_bin}")
        if shutil.which(self.ffprobe_bin) is None:
            raise FileNotFoundError(f"No se encontró FFprobe: {self.ffprobe_bin}")

    def _find_default_font(self) -> Optional[str]:
        for ruta in self.DEFAULT_FONT_PATHS:
            if Path(ruta).exists():
                return ruta
        return None

    def generar_video(
        self,
        imagenes: List[str],
        salida: str,
        frases: Optional[List[str]] = None,
        music_path: Optional[str] = None,
        image_duration: float = 5.5,
        transition_duration: float = 1.0,
        width: int = 720,
        height: int = 1280,
        fps: int = 30,
    ) -> str:
        self._validar_parametros(
            imagenes=imagenes,
            music_path=music_path,
            image_duration=image_duration,
            transition_duration=transition_duration,
        )

        for img in imagenes:
            if not os.path.exists(img):
                raise FileNotFoundError(f"No existe la imagen: {img}")

        output_dir = Path(salida).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        frases_limpias = [
            self._limpiar_texto_ffmpeg(f)
            for f in (frases or [])
            if f and f.strip()
        ][:3]

        total_duration = (len(imagenes) * image_duration) - (
            (len(imagenes) - 1) * transition_duration
        )

        cmd = [self.ffmpeg_bin, "-y"]

        for img in imagenes:
            cmd += ["-loop", "1", "-t", str(image_duration), "-i", img]

        has_music = bool(music_path and os.path.exists(music_path))
        if has_music:
            cmd += ["-stream_loop", "-1", "-i", music_path]

        filter_parts = []

        for i in range(len(imagenes)):
            frames_por_imagen = int(image_duration * fps)

            part = (
                f"[{i}:v]"
                f"scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,"
                f"crop={width * 2}:{height * 2},"
                f"zoompan="
                f"z='min(zoom+0.0007,1.10)':"
                f"x='iw/2-(iw/zoom/2)':"
                f"y='ih/2-(ih/zoom/2)':"
                f"d={frames_por_imagen}:"
                f"s={width}x{height}:"
                f"fps={fps},"
                f"trim=duration={image_duration},"
                f"setpts=PTS-STARTPTS,"
                f"setsar=1,"
                f"format=yuv420p"
                f"[v{i}]"
            )
            filter_parts.append(part)

        if len(imagenes) == 1:
            current_label = "v0"
        else:
            step = image_duration - transition_duration

            filter_parts.append(
                f"[v0][v1]xfade=transition=fade:duration={transition_duration}:offset={step}[x1]"
            )
            current_label = "x1"

            for i in range(2, len(imagenes)):
                offset = step * i
                next_label = f"x{i}"
                filter_parts.append(
                    f"[{current_label}][v{i}]xfade=transition=fade:duration={transition_duration}:offset={offset}[{next_label}]"
                )
                current_label = next_label

        final_video_label = current_label

        if frases_limpias:
            momentos = self._calcular_momentos_frases(total_duration, len(frases_limpias))
            base_label = final_video_label

            for idx, frase in enumerate(frases_limpias):
                in_start, out_start = momentos[idx]
                next_label = f"txt{idx}"

                drawtext = (
                    f"[{base_label}]drawtext="
                    f"fontfile='{self.font_path}':"
                    f"text='{frase}':"
                    f"fontcolor=white:"
                    f"fontsize=46:"
                    f"line_spacing=12:"
                    f"shadowcolor=black@0.75:"
                    f"shadowx=3:"
                    f"shadowy=3:"
                    f"x=(w-text_w)/2:"
                    f"y=h*0.78:"
                    f"alpha='if(lt(t,{in_start}),0,"
                    f"if(lt(t,{in_start + 0.8}),(t-{in_start})/0.8,"
                    f"if(lt(t,{out_start}),1,"
                    f"if(lt(t,{out_start + 0.8}),1-(t-{out_start})/0.8,0))))'"
                    f"[{next_label}]"
                )

                filter_parts.append(drawtext)
                base_label = next_label

            final_video_label = base_label

        filter_complex = ";".join(filter_parts)

        cmd += [
            "-filter_complex", filter_complex,
            "-map", f"[{final_video_label}]",
        ]

        if has_music:
            audio_input_index = len(imagenes)
            cmd += [
                "-map", f"{audio_input_index}:a",
                "-c:a", "aac",
                "-b:a", "192k",
            ]

        cmd += [
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-r", str(fps),
            "-shortest",
            "-movflags", "+faststart",
            salida,
        ]

        proc = subprocess.run(cmd, capture_output=True, text=True)

        if proc.returncode != 0:
            raise RuntimeError(
                "FFmpeg falló.\n\n"
                f"STDOUT:\n{proc.stdout}\n\n"
                f"STDERR:\n{proc.stderr}"
            )

        if not os.path.exists(salida):
            raise RuntimeError("FFmpeg terminó, pero no se creó el vídeo de salida.")

        return salida

    def _validar_parametros(
        self,
        imagenes: List[str],
        music_path: Optional[str],
        image_duration: float,
        transition_duration: float,
    ):
        if not imagenes:
            raise ValueError("No hay imágenes para generar el vídeo.")

        if len(imagenes) < 2:
            raise ValueError("Se requieren al menos 2 imágenes.")

        if image_duration <= 0:
            raise ValueError("image_duration debe ser mayor que 0.")

        if transition_duration <= 0:
            raise ValueError("transition_duration debe ser mayor que 0.")

        if transition_duration >= image_duration:
            raise ValueError("transition_duration debe ser menor que image_duration.")

        if music_path and not os.path.exists(music_path):
            raise FileNotFoundError(f"No existe el archivo de música: {music_path}")

    def _calcular_momentos_frases(self, total_duration: float, cantidad: int):
        if cantidad <= 0:
            return []

        if cantidad == 1:
            return [(2.0, max(4.5, total_duration - 3.0))]

        if cantidad == 2:
            return [
                (2.0, max(4.8, total_duration * 0.38)),
                (max(6.0, total_duration * 0.58), max(8.0, total_duration * 0.84)),
            ]

        return [
            (2.0, max(4.8, total_duration * 0.22)),
            (max(6.0, total_duration * 0.42), max(8.5, total_duration * 0.58)),
            (max(10.0, total_duration * 0.72), max(12.0, total_duration * 0.88)),
        ]

    def _limpiar_texto_ffmpeg(self, text: str) -> str:
        return (
            str(text)
            .replace("\\", "\\\\")
            .replace(":", "\\:")
            .replace("'", "\\'")
            .replace("%", "\\%")
            .replace(",", "\\,")
            .replace("[", "\\[")
            .replace("]", "\\]")
            .replace("\n", " ")
        )
