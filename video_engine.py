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

        output_dir = os.path.dirname(output)
        os.makedirs(output_dir, exist_ok=True)

        normalizadas_dir = os.path.join(output_dir, "normalizadas")
        os.makedirs(normalizadas_dir, exist_ok=True)

        imagenes_normalizadas = []
        for i, img_path in enumerate(imagenes, start=1):
            nueva = os.path.join(normalizadas_dir, f"img_{i}.jpg")
            self._normalizar_imagen(img_path, nueva)
            imagenes_normalizadas.append(os.path.abspath(nueva))

        clips = []

        for i, img in enumerate(imagenes_normalizadas, start=1):
            clip_path = os.path.join(output_dir, f"clip_{i}.mp4")

            comando_clip = [
                "ffmpeg",
                "-y",
                "-loop", "1",
                "-i", img,
                "-t", "4",
                "-vf", (
                    "scale=720:1280:force_original_aspect_ratio=increase,"
                    "crop=720:1280,"
                    "format=yuv420p"
                ),
                "-r", "25",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                clip_path
            ]

            self._run_ffmpeg(comando_clip)
            clips.append(os.path.abspath(clip_path))

        if frases:
            frases = [self._limpiar_texto_ffmpeg(f) for f in frases if f.strip()]

        if frases:
            texto_clip = os.path.join(output_dir, "texto_final.mp4")
            texto = frases[-1] if frases else "ETERNA"

            comando_texto = [
                "ffmpeg",
                "-y",
                "-f", "lavfi",
                "-i", "color=c=black:s=720x1280:d=3",
                "-vf",
                (
                    f"drawtext=text='{texto}':"
                    "fontcolor=white:"
                    "fontsize=42:"
                    "x=(w-text_w)/2:"
                    "y=(h-text_h)/2"
                ),
                "-r", "25",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                texto_clip
            ]

            self._run_ffmpeg(comando_texto)
            clips.append(os.path.abspath(texto_clip))

        if regalo_activo and regalo_amount_eur > 0:
            regalo_clip = os.path.join(output_dir, "regalo.mp4")
            regalo_texto = f"{regalo_amount_eur:.2f} EUR para ti"
            regalo_texto = self._limpiar_texto_ffmpeg(regalo_texto)

            comando_regalo = [
                "ffmpeg",
                "-y",
                "-f", "lavfi",
                "-i", "color=c=black:s=720x1280:d=3",
                "-vf",
                (
                    f"drawtext=text='{regalo_texto}':"
                    "fontcolor=white:"
                    "fontsize=42:"
                    "x=(w-text_w)/2:"
                    "y=(h-text_h)/2"
                ),
                "-r", "25",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                regalo_clip
            ]

            self._run_ffmpeg(comando_regalo)
            clips.append(os.path.abspath(regalo_clip))

        if video_regalante and os.path.exists(video_regalante):
            video_regalante_clip = os.path.join(output_dir, "video_regalante_final.mp4")

            comando_regalante = [
                "ffmpeg",
                "-y",
                "-i", video_regalante,
                "-vf",
                (
                    "scale=720:1280:force_original_aspect_ratio=increase,"
                    "crop=720:1280,"
                    "format=yuv420p"
                ),
                "-r", "25",
                "-c:v", "libx264",
                "-c:a", "aac",
                "-pix_fmt", "yuv420p",
                video_regalante_clip
            ]

            self._run_ffmpeg(comando_regalante)
            clips.append(os.path.abspath(video_regalante_clip))

        lista_concat = os.path.join(output_dir, "concat.txt")
        with open(lista_concat, "w", encoding="utf-8") as f:
            for clip in clips:
                f.write(f"file '{clip}'\n")

        comando_final = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", lista_concat,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-pix_fmt", "yuv420p",
            output
        ]

        self._run_ffmpeg(comando_final)

        if not os.path.exists(output):
            raise RuntimeError(f"El vídeo no se generó en: {output}")

        if os.path.getsize(output) == 0:
            raise RuntimeError("El vídeo se creó vacío")

        print("✅ VIDEO FINAL GUARDADO EN:", output)
        return output

    def _normalizar_imagen(self, origen: str, destino: str):
        with Image.open(origen) as img:
            img = ImageOps.exif_transpose(img)
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

    def _run_ffmpeg(self, comando: List[str]):
        try:
            resultado = subprocess.run(
                comando,
                check=True,
                capture_output=True,
                text=True
            )
            return resultado
        except subprocess.CalledProcessError as e:
            print("❌ ERROR FFMPEG")
            print("COMANDO:", " ".join(comando))
            print("STDERR:", e.stderr)
            raise RuntimeError(f"FFmpeg falló: {e.stderr}") from e
