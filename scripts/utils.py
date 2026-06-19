"""
Utilidades auxiliares para Dynamica Plantillas.

Incluye helpers multiplataforma para abrir archivos, limpiar output,
normalizar nombres y gestionar fechas.
"""
from __future__ import annotations

import datetime
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path


def abrir_archivo(ruta: Path) -> None:
    """Abre un archivo con la aplicacion predeterminada del sistema operativo."""
    sistema = platform.system()
    try:
        if sistema == "Windows":
            os.startfile(str(ruta))  # type: ignore[attr-defined]
        elif sistema == "Darwin":  # macOS
            subprocess.run(["open", str(ruta)], check=True)
        else:  # Linux y otros Unix
            subprocess.run(["xdg-open", str(ruta)], check=True)
    except Exception as e:
        print(f"No se pudo abrir el archivo automaticamente: {e}")
        print(f"Puedes abrirlo manualmente desde: {ruta}")


def normalizar_slug(nombre: str) -> str:
    """Convierte un nombre en un slug seguro para nombre de archivo."""
    slug = re.sub(r"[^\w\s-]", "", nombre).strip()
    slug = re.sub(r"[-\s]+", "_", slug)
    return slug


def limpiar_output(carpeta: Path, modo: str, dias: int = 30) -> None:
    """
    Aplica la politica de limpieza de la carpeta output.

    modos:
      - "guardar": no borra nada.
      - "dias": borra archivos .eml y .html de preview mas antiguos que X dias.
      - "no_mantener": borra todo el contenido de output/.
    """
    if not carpeta.exists():
        return

    if modo == "no_mantener":
        for item in carpeta.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        return

    if modo == "dias":
        ahora = datetime.datetime.now()
        umbral = ahora - datetime.timedelta(days=dias)
        for item in carpeta.iterdir():
            if item.is_file() and item.suffix.lower() in (".eml", ".html"):
                mtime = datetime.datetime.fromtimestamp(item.stat().st_mtime)
                if mtime < umbral:
                    item.unlink()

    # modo "guardar": no hacer nada


def timestamp_para_archivo() -> str:
    """Devuelve un timestamp formato yyyymmdd_HHMMSS."""
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def fecha_hoy_iso() -> str:
    """Devuelve la fecha actual en formato ISO (YYYY-MM-DD)."""
    return datetime.date.today().isoformat()
