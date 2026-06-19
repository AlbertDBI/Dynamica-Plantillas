"""
Motor de generacion de correos .eml para Dynamica Plantillas.

Este script es el nucleo determinista del sistema. No improvisa contenido.
Lee plantillas, firmas y contactos desde archivos locales, ensambla bloques
HTML predefinidos y genera un archivo .eml listo para abrir en Outlook,
Himalaya o cualquier cliente de correo.
"""
from __future__ import annotations

import email.utils
import re
import uuid
from email.message import EmailMessage
from email.policy import EmailPolicy
from pathlib import Path
from typing import Any

import frontmatter
import jinja2
import markdown
import yaml

from utils import (
    abrir_archivo,
    fecha_hoy_iso,
    limpiar_output,
    normalizar_slug,
    timestamp_para_archivo,
)

# Rutas base del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
SIGNATURES_DIR = BASE_DIR / "signatures"
SIGNATURES_ADJUNTS_DIR = SIGNATURES_DIR / "adjuntos"
CONTACTS_DIR = BASE_DIR / "contacts"
OUTPUT_DIR = BASE_DIR / "output"
CONFIG_FILE = BASE_DIR / "config.yaml"

# Campos basicos requeridos para un contacto
CAMPOS_CONTACTO_OBLIGATORIOS = ["nombre", "email", "empresa"]


def cargar_config() -> dict[str, Any]:
    """Carga la configuracion global desde config.yaml."""
    if not CONFIG_FILE.exists():
        return {
            "remitente_default": "tu@correo.com",
            "firma_default": None,
            "output": {"modo": "dias", "dias": 30},
        }
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def guardar_config(config: dict[str, Any]) -> None:
    """Guarda la configuracion global en config.yaml."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)


# ---------------------------------------------------------------------------
# Gestion de plantillas
# ---------------------------------------------------------------------------

def listar_plantillas() -> list[dict[str, str]]:
    """Lista las carpetas de plantillas disponibles."""
    plantillas: list[dict[str, str]] = []
    if not TEMPLATES_DIR.exists():
        return plantillas
    for path in sorted(TEMPLATES_DIR.iterdir()):
        if path.is_dir() and (path / "diseno.html").exists():
            plantillas.append({"nombre": path.name, "ruta": str(path)})
    return plantillas


def cargar_plantilla(nombre: str) -> dict[str, Any]:
    """Carga una plantilla completa: diseno, campos, texto obligatorio y adjuntos."""
    ruta = TEMPLATES_DIR / nombre
    if not ruta.exists():
        raise FileNotFoundError(f"Plantilla no encontrada: {ruta}")

    diseno_path = ruta / "diseno.html"
    campos_path = ruta / "campos.md"
    texto_path_md = ruta / "texto_obligatorio.md"
    texto_path_html = ruta / "texto_obligatorio.html"
    adjuntos_path = ruta / "adjuntos"

    if not diseno_path.exists():
        raise FileNotFoundError(f"La plantilla no tiene diseno.html: {diseno_path}")

    diseno = diseno_path.read_text(encoding="utf-8")

    campos: dict[str, list[str]] = {}
    asuntos: list[str] = []
    if campos_path.exists():
        campos, asuntos = parsear_campos_md(campos_path.read_text(encoding="utf-8"))

    texto_obligatorio = ""
    if texto_path_html.exists():
        texto_obligatorio = texto_path_html.read_text(encoding="utf-8")
    elif texto_path_md.exists():
        texto_obligatorio = markdown.markdown(texto_path_md.read_text(encoding="utf-8"))

    adjuntos: list[Path] = []
    if adjuntos_path.exists():
        adjuntos = sorted(p for p in adjuntos_path.iterdir() if p.is_file())

    return {
        "nombre": nombre,
        "ruta": ruta,
        "diseno": diseno,
        "campos": campos,
        "asuntos": asuntos,
        "texto_obligatorio": texto_obligatorio,
        "adjuntos": adjuntos,
    }


def parsear_campos_md(texto: str) -> tuple[dict[str, list[str]], list[str]]:
    """
    Parsea un campos.md en secciones.
    La seccion '## asuntos' se devuelve aparte.
    El resto son secciones de bloques.
    """
    secciones: dict[str, list[str]] = {}
    asuntos: list[str] = []
    seccion_actual: str | None = None

    for linea in texto.splitlines():
        linea = linea.rstrip()
        if linea.startswith("## "):
            seccion_actual = linea[3:].strip().lower()
            if seccion_actual not in secciones:
                secciones[seccion_actual] = []
            continue
        if seccion_actual and linea.startswith("- "):
            contenido = linea[2:].strip()
            if contenido:
                if seccion_actual == "asuntos":
                    asuntos.append(contenido)
                else:
                    secciones[seccion_actual].append(contenido)

    return secciones, asuntos


def detectar_slots(html: str) -> list[str]:
    """Detecta todos los slots {{slot}} del HTML, conservando el orden de aparicion."""
    slots = re.findall(r"\{\{([A-Za-z0-9_]+)\}\}", html)
    # Conservar orden y evitar duplicados consecutivos, pero permitir repeticiones no consecutivas
    resultado: list[str] = []
    for slot in slots:
        if not resultado or resultado[-1] != slot:
            resultado.append(slot)
    return resultado


# ---------------------------------------------------------------------------
# Gestion de firmas
# ---------------------------------------------------------------------------

def listar_firmas() -> list[dict[str, Any]]:
    """Lista las firmas disponibles en signatures/."""
    firmas: list[dict[str, Any]] = []
    if not SIGNATURES_DIR.exists():
        return firmas
    for path in sorted(SIGNATURES_DIR.glob("*.md")):
        post = frontmatter.load(str(path))
        firmas.append(
            {
                "archivo": path.name,
                "ruta": path,
                "slug": path.stem,
                "nombre": post.metadata.get("nombre", path.stem),
                "datos": post.metadata,
                "contenido": post.content,
            }
        )
    return firmas


def cargar_firma(slug: str) -> dict[str, Any] | None:
    """Carga una firma por slug."""
    ruta = SIGNATURES_DIR / f"{slug}.md"
    if not ruta.exists():
        return None
    post = frontmatter.load(str(ruta))
    return {
        "archivo": ruta.name,
        "ruta": ruta,
        "slug": ruta.stem,
        "nombre": post.metadata.get("nombre", ruta.stem),
        "datos": post.metadata,
        "contenido": post.content,
    }


def renderizar_firma(firma: dict[str, Any] | None, variables: dict[str, str]) -> tuple[str, list[Path]]:
    """
    Renderiza la firma y devuelve el HTML junto con la lista de imagenes locales
    que deben convertirse a adjuntos inline.
    """
    if not firma:
        return "", []

    datos = {k: str(v) for k, v in firma["datos"].items() if v is not None}
    datos.update(variables)

    html_crudo = markdown.markdown(firma["contenido"])
    plantilla = jinja2.Template(html_crudo)
    html_renderizado = plantilla.render(**datos)

    # Detectar imagenes locales y preparar adjuntos inline
    imagenes: list[Path] = []
    for match in re.finditer(r'src=["\']([^"\']+)["\']', html_renderizado):
        src = match.group(1)
        if src.startswith(("http://", "https://", "mailto:", "tel:", "cid:")):
            continue
        ruta_imagen = Path(src)
        if not ruta_imagen.is_absolute():
            # Buscar en signatures/adjuntos o en la raiz del proyecto
            candidatos = [
                SIGNATURES_ADJUNTS_DIR / src,
                BASE_DIR / src,
            ]
            for candidato in candidatos:
                if candidato.exists():
                    ruta_imagen = candidato
                    break
        if ruta_imagen.exists() and ruta_imagen not in imagenes:
            imagenes.append(ruta_imagen)

    # Reemplazar src por cid correspondiente
    html_final = html_renderizado
    for imagen in imagenes:
        cid = f"img_{uuid.uuid4().hex[:8]}"
        html_final = html_final.replace(f'src="{imagen.name}"', f'src="cid:{cid}"')
        html_final = html_final.replace(f"src='{imagen.name}'", f'src="cid:{cid}"')
        html_final = html_final.replace(f'src="{str(imagen)}"', f'src="cid:{cid}"')
        html_final = html_final.replace(f"src='{str(imagen)}'", f'src="cid:{cid}"')

    return html_final, imagenes


# ---------------------------------------------------------------------------
# Gestion de contactos
# ---------------------------------------------------------------------------

def listar_contactos() -> list[dict[str, Any]]:
    """Lista los contactos disponibles."""
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
                "historial": post.content,
            }
        )
    return contactos


def cargar_contacto_por_email(email: str) -> dict[str, Any] | None:
    """Busca un contacto por su direccion de email."""
    for contacto in listar_contactos():
        if contacto["datos"].get("email", "").strip().lower() == email.strip().lower():
            return contacto
    return None


def cargar_contacto(slug: str) -> dict[str, Any] | None:
    """Carga un contacto por slug."""
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
    """Guarda o actualiza un contacto."""
    CONTACTS_DIR.mkdir(parents=True, exist_ok=True)
    ruta = CONTACTS_DIR / f"{slug}.md"
    post = frontmatter.Post(historial, **datos)
    with open(ruta, "w", encoding="utf-8") as f:
        frontmatter.dump(post, f)


def crear_o_actualizar_contacto(
    nombre: str,
    email: str,
    empresa: str,
    extras: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Crea un contacto nuevo o actualiza el existente si coincide el email."""
    email = email.strip()
    existe = cargar_contacto_por_email(email)

    datos: dict[str, Any] = {
        "nombre": nombre.strip(),
        "email": email,
        "empresa": empresa.strip(),
    }
    if extras:
        for k, v in extras.items():
            if v:
                datos[k] = v

    if existe:
        slug = existe["slug"]
        historial = existe.get("historial", "")
        # Actualizar datos, preservando campos que no se hayan proporcionado
        datos_actualizados = {**existe["datos"], **datos}
    else:
        slug = normalizar_slug(f"{nombre}_{empresa}")
        historial = "### Historial de correos\n"
        datos_actualizados = datos

    guardar_contacto(slug, datos_actualizados, historial)
    contacto = cargar_contacto(slug)
    if contacto is None:
        raise RuntimeError("No se pudo cargar el contacto recien guardado")
    return contacto


# ---------------------------------------------------------------------------
# Ensamblaje y renderizado
# ---------------------------------------------------------------------------

def md_a_html(texto: str) -> str:
    """Convierte Markdown a HTML."""
    return markdown.markdown(texto)


def detectar_variables(texto: str) -> set[str]:
    """Detecta variables tipo {{VARIABLE}} en un texto."""
    return set(re.findall(r"\{\{([A-Za-z0-9_]+)\}\}", texto))


def renderizar_opcion(texto_md: str, variables: dict[str, str]) -> str:
    """Convierte una opcion Markdown a HTML y renderiza sus variables."""
    html = md_a_html(texto_md)
    plantilla = jinja2.Template(html)
    return plantilla.render(**variables)


def ensamblar_html(
    plantilla: dict[str, Any],
    selecciones: dict[str, list[str]],
    variables: dict[str, str],
    firma_html: str,
    personalizados: dict[str, str],
) -> str:
    """
    Ensambla el HTML final sustituyendo cada slot del diseno.html por el
    contenido correspondiente.
    """
    html = plantilla["diseno"]

    # Texto obligatorio
    texto_html = plantilla["texto_obligatorio"]
    for match in re.finditer(r'src=["\']([^"\']+)["\']', texto_html):
        src = match.group(1)
        if src.startswith(("http://", "https://", "mailto:", "tel:", "cid:")):
            continue
        # Imagenes locales del texto obligatorio se manejan como adjuntos normales

    # Slots simples: saludo, cuerpo, despedida, firma, texto_obligatorio
    for slot in plantilla["campos"].keys():
        if slot in ("asuntos",):
            continue
        if slot == "firma":
            continue  # la firma se trata aparte

        opciones = selecciones.get(slot, [])
        fragmentos: list[str] = []
        for opcion_idx in opciones:
            try:
                idx = int(opcion_idx) - 1
                texto_md = plantilla["campos"][slot][idx]
                fragmentos.append(renderizar_opcion(texto_md, variables))
            except (ValueError, IndexError):
                continue
        contenido = "\n".join(fragmentos)
        html = html.replace(f"{{{{{slot}}}}}", contenido)

    # Slot de firma
    html = html.replace("{{firma}}", firma_html)

    # Slot de texto obligatorio
    html = html.replace("{{texto_obligatorio}}", texto_html)

    # Slots personalizados
    for slot, valor in personalizados.items():
        if not valor.strip():
            # Eliminar el slot del HTML si esta vacio (no obligatorio)
            html = html.replace(f"{{{{{slot}}}}}", "")
        else:
            html_renderizado = md_a_html(valor)
            html = html.replace(f"{{{{{slot}}}}}", html_renderizado)

    # Eliminar cualquier slot personalizado vacio no rellenado
    for match in re.finditer(r"\{\{([A-Za-z0-9_]+)\}\}", html):
        slot = match.group(1)
        if slot.startswith("personalizado") and not slot.endswith("_obligatorio"):
            html = html.replace(f"{{{{{slot}}}}}", "")

    # Renderizar cualquier variable adicional del contacto que aparezca en el diseno
    plantilla_jinja = jinja2.Template(html)
    html = plantilla_jinja.render(**variables)

    return html


def validar_html_final(html: str) -> list[str]:
    """Devuelve una lista de slots obligatorios que siguen vacios."""
    errores: list[str] = []
    for match in re.finditer(r"\{\{([A-Za-z0-9_]+)_obligatorio\}\}", html):
        errores.append(match.group(1) + "_obligatorio")
    return errores


# ---------------------------------------------------------------------------
# Generacion del correo .eml
# ---------------------------------------------------------------------------

def generar_eml(
    destinatarios: list[dict[str, str]],
    asunto: str,
    html_final: str,
    from_email: str,
    adjuntos: list[Path],
    imagenes_inline: list[Path],
    reply_to: str = "",
) -> Path:
    """Genera el archivo .eml multipart con HTML, texto plano y adjuntos."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    msg = EmailMessage(policy=EmailPolicy())
    msg["Subject"] = asunto
    msg["From"] = from_email

    # Construir cabeceras To, Cc, Bcc
    to_list = [d["email"] for d in destinatarios if d.get("tipo", "para") == "para"]
    cc_list = [d["email"] for d in destinatarios if d.get("tipo") == "cc"]
    bcc_list = [d["email"] for d in destinatarios if d.get("tipo") == "cco"]

    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    if bcc_list:
        msg["Bcc"] = ", ".join(bcc_list)

    if reply_to:
        msg["Reply-To"] = reply_to

    # Texto plano fallback
    texto_plano = re.sub(r"<[^>]*>", " ", html_final)
    texto_plano = re.sub(r"\s+", " ", texto_plano).strip()
    msg.set_content(texto_plano)
    msg.add_alternative(html_final, subtype="html")

    # Adjuntos inline (imagenes de firma)
    cids: dict[Path, str] = {}
    for imagen in imagenes_inline:
        cid = f"img_{uuid.uuid4().hex[:8]}"
        cids[imagen] = cid
        tipo_main, tipo_sub = _tipo_mime(imagen)
        with open(imagen, "rb") as f:
            datos = f.read()
        msg.add_attachment(
            datos,
            maintype=tipo_main,
            subtype=tipo_sub,
            cid=f"<{cid}>",
            filename=imagen.name,
            disposition="inline",
        )

    # Reemplazar referencias cid en el HTML si aun no se hizo
    for imagen, cid in cids.items():
        html_final = html_final.replace(str(imagen), f"cid:{cid}")
        html_final = html_final.replace(imagen.name, f"cid:{cid}")

    # Si se modificó el HTML, actualizar la parte alternativa
    if cids:
        msg.set_content(texto_plano)
        msg.add_alternative(html_final, subtype="html")

    # Adjuntos normales
    for adjunto in adjuntos:
        if not adjunto.exists():
            continue
        tipo_main, tipo_sub = _tipo_mime(adjunto)
        with open(adjunto, "rb") as f:
            datos = f.read()
        msg.add_attachment(
            datos,
            maintype=tipo_main,
            subtype=tipo_sub,
            filename=adjunto.name,
        )

    # Nombre del archivo de salida
    fecha = timestamp_para_archivo()
    if destinatarios:
        nombre_base = normalizar_slug(destinatarios[0].get("empresa", "empresa"))
    else:
        nombre_base = "sin_empresa"
    ruta_salida = OUTPUT_DIR / f"{nombre_base}_{fecha}.eml"

    with open(ruta_salida, "wb") as f:
        f.write(msg.as_bytes(policy=EmailPolicy(linesep="\r\n")))

    return ruta_salida


def _tipo_mime(ruta: Path) -> tuple[str, str]:
    """Devuelve el tipo MIME principal y secundario segun la extension."""
    ext = ruta.suffix.lower()
    mapping = {
        ".pdf": ("application", "pdf"),
        ".jpg": ("image", "jpeg"),
        ".jpeg": ("image", "jpeg"),
        ".png": ("image", "png"),
        ".gif": ("image", "gif"),
        ".txt": ("text", "plain"),
        ".html": ("text", "html"),
        ".docx": ("application", "vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ".xlsx": ("application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    }
    return mapping.get(ext, ("application", "octet-stream"))


# ---------------------------------------------------------------------------
# Registro de envios
# ---------------------------------------------------------------------------

def registrar_envio_en_contacto(contacto: dict[str, Any], ruta_eml: Path) -> None:
    """Anade una linea al historial del contacto con vinculo al .eml generado."""
    fecha = fecha_hoy_iso()
    linea = f"- [{fecha}] [{ruta_eml.name}]({ruta_eml.name})"
    datos = contacto["datos"]
    historial_actual = contacto.get("historial", "")
    nuevo_historial = (historial_actual.rstrip() + "\n" + linea).strip()
    guardar_contacto(contacto["slug"], datos, nuevo_historial)
