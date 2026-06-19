"""
Motor de generacion de correos .eml para Dynamica Plantillas.

Este script es el nucleo determinista del sistema. No improvisa contenido.
Lee contactos en formato Markdown con frontmatter, ensambla bloques HTML
predefinidos y genera un archivo .eml listo para abrir en Outlook,
Himalaya o cualquier cliente de correo.
"""
from __future__ import annotations

import datetime
import os
import re
from email.message import EmailMessage
from email.policy import EmailPolicy
from pathlib import Path
from typing import Any

import frontmatter
import jinja2

# Rutas base del proyecto (relativas a la ubicacion de este archivo)
BASE_DIR = Path(__file__).resolve().parent.parent
CONTACTS_DIR = BASE_DIR / "contacts"
BLOCKS_DIR = BASE_DIR / "blocks"
OUTPUT_DIR = BASE_DIR / "output"
ASSETS_DIR = BASE_DIR / "assets"

# Campos basicos requeridos para crear un contacto nuevo
CAMPOS_CONTACTO_OBLIGATORIOS = ["nombre", "email", "empresa"]

# Placeholder usado en bloques HTML para el campo personalizado libre
MARCADOR_PERSONALIZADO = "{{PERSONALIZADO}}"


def listar_contactos() -> list[dict[str, Any]]:
    """Devuelve una lista de contactos encontrados en CONTACTS_DIR."""
    contactos: list[dict[str, Any]] = []
    if not CONTACTS_DIR.exists():
        return contactos
    for path in sorted(CONTACTS_DIR.glob("*.md")):
        post = frontmatter.load(str(path))
        contactos.append(
            {
                "archivo": path.name,
                "ruta": path,
                "slug": path.stem,
                "datos": post.metadata,
            }
        )
    return contactos


def cargar_contacto(slug: str) -> dict[str, Any] | None:
    """Carga un contacto por su slug (nombre de archivo sin extension)."""
    ruta = CONTACTS_DIR / f"{slug}.md"
    if not ruta.exists():
        return None
    post = frontmatter.load(str(ruta))
    return {
        "archivo": ruta.name,
        "ruta": ruta,
        "slug": ruta.stem,
        "datos": post.metadata,
        "historial": post.content,
    }


def guardar_contacto(slug: str, datos: dict[str, Any], historial: str = "") -> None:
    """Guarda o actualiza un archivo de contacto con frontmatter."""
    CONTACTS_DIR.mkdir(parents=True, exist_ok=True)
    ruta = CONTACTS_DIR / f"{slug}.md"
    post = frontmatter.Post(historial, **datos)
    with open(ruta, "w", encoding="utf-8") as f:
        frontmatter.dump(post, f)


def listar_bloques(tipo: str) -> list[dict[str, str]]:
    """Lista los bloques disponibles de un tipo (presentacion, cuerpo, despedida)."""
    carpeta = BLOCKS_DIR / tipo
    if not carpeta.exists():
        return []
    bloques: list[dict[str, str]] = []
    for path in sorted(carpeta.glob("*.html")):
        bloques.append(
            {
                "nombre": path.stem,
                "ruta": str(path),
                "contenido": path.read_text(encoding="utf-8"),
            }
        )
    return bloques


def listar_adjuntos() -> list[Path]:
    """Devuelve los archivos adjuntos disponibles en ASSETS_DIR."""
    if not ASSETS_DIR.exists():
        return []
    return sorted(p for p in ASSETS_DIR.iterdir() if p.is_file())


def renderizar_bloque(contenido: str, variables: dict[str, str]) -> str:
    """Renderiza un bloque HTML usando Jinja2 con las variables proporcionadas."""
    # Jinja2 espera llaves dobles; si los bloques usan {{VAR}}, esto funciona directamente.
    plantilla = jinja2.Template(contenido)
    return plantilla.render(**variables)


def detectar_campos_requeridos_html(html: str) -> list[str]:
    """Extrae los placeholders tipo {{VARIABLE}} del HTML."""
    return sorted(set(re.findall(r"\{\{(\w+)\}\}", html)))


def normalizar_slug(nombre: str) -> str:
    """Convierte un nombre en un slug seguro para nombre de archivo."""
    slug = re.sub(r"[^\w\s-]", "", nombre).strip().replace(" ", "_")
    return slug


def construir_asunto(plantilla: str, variables: dict[str, str]) -> str:
    """Renderiza el asunto con Jinja2 usando las variables del contacto."""
    return jinja2.Template(plantilla).render(**variables)


def msg_default_from() -> str:
    """Remitente por defecto para los correos generados."""
    return "tu@correo.com"


def generar_eml(
    contacto: dict[str, Any],
    bloques_presentacion: list[str],
    bloques_cuerpo: list[str],
    bloques_despedida: list[str],
    asunto: str,
    variables_extra: dict[str, str],
    adjuntos: list[Path] | None = None,
    campo_personalizado: str = "",
    from_email: str = "tu@correo.com",
    cc: str = "",
    bcc: str = "",
) -> Path:
    """
    Ensambla el correo HTML a partir de bloques y genera un archivo .eml.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    datos = contacto["datos"]
    variables = {k: str(v) for k, v in datos.items() if v is not None}
    variables.update(variables_extra)

    # Renderizado de cada seccion
    presentacion_html = "\n".join(
        renderizar_bloque(cargar_bloque("presentacion", nombre), variables)
        for nombre in bloques_presentacion
    )
    cuerpo_html = "\n".join(
        renderizar_bloque(cargar_bloque("cuerpo", nombre), variables)
        for nombre in bloques_cuerpo
    )
    despedida_html = "\n".join(
        renderizar_bloque(cargar_bloque("despedida", nombre), variables)
        for nombre in bloques_despedida
    )

    # Campo personalizado: reemplaza el marcador en cualquier bloque
    if campo_personalizado:
        marcador_html = f"<p>{campo_personalizado}</p>"
        presentacion_html = presentacion_html.replace(MARCADOR_PERSONALIZADO, marcador_html)
        cuerpo_html = cuerpo_html.replace(MARCADOR_PERSONALIZADO, marcador_html)
        despedida_html = despedida_html.replace(MARCADOR_PERSONALIZADO, marcador_html)

    # Estructura HTML base del correo
    html_completo = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{asunto}</title>
</head>
<body style="font-family: Arial, sans-serif; color: #333;">
    <div style="max-width: 600px; margin: auto;">
        {presentacion_html}
        {cuerpo_html}
        {despedida_html}
    </div>
</body>
</html>"""

    # Construir mensaje MIME
    msg = EmailMessage(policy=EmailPolicy())
    msg["Subject"] = asunto
    msg["From"] = from_email
    msg["To"] = datos.get("email", "")
    if cc:
        msg["Cc"] = cc
    if bcc:
        msg["Bcc"] = bcc

    # Texto plano fallback
    texto_plano = re.sub(r"<[^>]+>", "", html_completo)
    msg.set_content(texto_plano)
    msg.add_alternative(html_completo, subtype="html")

    # Adjuntos
    for adjunto in adjuntos or []:
        if not adjunto.exists():
            continue
        contenido = adjunto.read_bytes()
        tipo_main = "application"
        tipo_sub = "octet-stream"
        if adjunto.suffix.lower() == ".pdf":
            tipo_sub = "pdf"
        elif adjunto.suffix.lower() in (".jpg", ".jpeg"):
            tipo_main = "image"
            tipo_sub = "jpeg"
        elif adjunto.suffix.lower() == ".png":
            tipo_main = "image"
            tipo_sub = "png"
        msg.add_attachment(
            contenido,
            maintype=tipo_main,
            subtype=tipo_sub,
            filename=adjunto.name,
        )

    # Nombre del archivo de salida
    fecha = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = normalizar_slug(datos.get("empresa", "empresa"))
    nombre_salida = f"{slug}_{fecha}.eml"
    ruta_salida = OUTPUT_DIR / nombre_salida

    with open(ruta_salida, "wb") as f:
        f.write(msg.as_bytes())

    return ruta_salida


def cargar_bloque(tipo: str, nombre: str) -> str:
    """Carga el contenido de un bloque HTML por tipo y nombre."""
    path = BLOCKS_DIR / tipo / f"{nombre}.html"
    if not path.exists():
        raise FileNotFoundError(f"Bloque no encontrado: {path}")
    return path.read_text(encoding="utf-8")


def registrar_envio_en_contacto(contacto: dict[str, Any], ruta_eml: Path) -> None:
    """Anade una linea al historial del contacto con vinculo al .eml generado."""
    fecha = datetime.datetime.now().strftime("%Y-%m-%d")
    linea = f"- [{fecha}] [{ruta_eml.name}]({ruta_eml.name})"
    datos = contacto["datos"]
    historial_actual = contacto.get("historial", "")
    nuevo_historial = (historial_actual.rstrip() + "\n" + linea).strip()
    guardar_contacto(contacto["slug"], datos, nuevo_historial)
