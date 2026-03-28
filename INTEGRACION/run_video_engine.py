import os
import shutil
import subprocess
from pathlib import Path

# =========================================================
# RUTAS BASE
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

VIDEO_ENGINE_DIR = BASE_DIR / "VIDEO_ENGINE_SAGRADO"
INPUTS_DIR = VIDEO_ENGINE_DIR / "inputs"
OUTPUT_DIR = VIDEO_ENGINE_DIR / "renders"

VIDEO_ENGINE_FILE = VIDEO_ENGINE_DIR / "video_engine.py"

# =========================================================
# LIMPIAR INPUTS
# =========================================================

def clean_inputs():
    if INPUTS_DIR.exists():
        for f in INPUTS_DIR.iterdir():
            try:
                f.unlink()
            except:
                pass

# =========================================================
# COPIAR FOTOS
# =========================================================

def copy_photos(photo_paths):
    INPUTS_DIR.mkdir(parents=True, exist_ok=True)

    for i, photo in enumerate(photo_paths, start=1):
        ext = Path(photo).suffix
        dest = INPUTS_DIR / f"foto{i}{ext}"
        shutil.copy(photo, dest)

# =========================================================
# EJECUTAR MOTOR
# =========================================================

def run_engine():
    result = subprocess.run(
        ["python", str(VIDEO_ENGINE_FILE)],
        capture_output=True,
        text=True
    )

    print(result.stdout)
    print(result.stderr)

    if result.returncode != 0:
        raise Exception("Error ejecutando video_engine")

# =========================================================
# OBTENER VIDEO
# =========================================================

def get_latest_video():
    videos = sorted(OUTPUT_DIR.glob("*.mp4"), key=os.path.getmtime, reverse=True)

    if not videos:
        raise Exception("No se generó ningún vídeo")

    return str(videos[0])

# =========================================================
# FUNCIÓN PRINCIPAL
# =========================================================

def generate_video(photo_paths):
    print("🔹 LIMPIANDO INPUTS")
    clean_inputs()

    print("🔹 COPIANDO FOTOS")
    copy_photos(photo_paths)

    print("🔹 EJECUTANDO MOTOR")
    run_engine()

    print("🔹 BUSCANDO VIDEO FINAL")
    video_path = get_latest_video()

    print(f"✅ VIDEO GENERADO: {video_path}")

    return video_path
