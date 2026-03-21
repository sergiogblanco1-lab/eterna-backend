from pathlib import Path
from typing import List, Dict
from fastapi import UploadFile


class StorageService:
    def __init__(self, base_dir: Path | None = None):
        if base_dir is None:
            base_dir = Path(__file__).resolve().parent

        self.base_dir = base_dir
        self.storage_dir = self.base_dir / "storage"
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def crear_carpeta_eterna(self, eterna_id: str) -> Path:
        carpeta = self.storage_dir / eterna_id
        carpeta.mkdir(parents=True, exist_ok=True)
        return carpeta

    def guardar_datos(self, carpeta: Path, datos: Dict[str, str]) -> Path:
        ruta = carpeta / "data.txt"

        with open(ruta, "w", encoding="utf-8") as f:
            for clave, valor in datos.items():
                f.write(f"{clave}: {valor}\n")

        return ruta

    def guardar_estado_inicial(self, carpeta: Path) -> Path:
        ruta = carpeta / "status.txt"

        with open(ruta, "w", encoding="utf-8") as f:
            f.write("estado: pendiente_pago\n")
            f.write("video: no_generado\n")
            f.write("reaccion: no_grabada\n")

        return ruta

    async def guardar_fotos(self, carpeta: Path, fotos: List[UploadFile]) -> List[str]:
        fotos_guardadas = []

        for i, foto in enumerate(fotos):
            if not foto.filename:
                continue

            contenido = await foto.read()

            if not contenido:
                continue

            ext = self.extension_segura(foto.filename)
            nombre_archivo = f"foto{i+1}{ext}"
            ruta = carpeta / nombre_archivo

            with open(ruta, "wb") as f:
                f.write(contenido)

            fotos_guardadas.append(nombre_archivo)

        return fotos_guardadas

    def extension_segura(self, filename: str) -> str:
        ext = Path(filename).suffix.lower()
        extensiones_validas = [".jpg", ".jpeg", ".png", ".webp"]

        if ext in extensiones_validas:
            return ext

        return ".jpg"
