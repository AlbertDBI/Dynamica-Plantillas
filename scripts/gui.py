"""
Interfaz grafica web para Dynamica Plantillas usando Streamlit.

Ejecutar con:
    streamlit run scripts/gui.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

import engine
import utils
from utils import guardar_preview_temporal


st.set_page_config(
    page_title="Dynamica Plantillas",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="expanded",
)


THEME_CSS = {
    "Claro": """
        html, body, [data-testid="stApp"], [data-testid="stAppViewContainer"] {
            background-color: #ffffff !important;
            color: #1a1a1a !important;
        }
        [data-testid="stSidebar"] {
            background-color: #f7f7f7 !important;
        }
        h1, h2, h3, h4, h5, h6, p, label, span {
            color: #1a1a1a !important;
        }
    """,
    "Oscuro": """
        html, body, [data-testid="stApp"], [data-testid="stAppViewContainer"] {
            background-color: #0e1117 !important;
            color: #fafafa !important;
        }
        [data-testid="stSidebar"] {
            background-color: #1c2128 !important;
        }
        h1, h2, h3, h4, h5, h6, p, label, span {
            color: #fafafa !important;
        }
    """,
    "Sistema": "",
}


def inicializar_estado() -> None:
    """Inicializa el estado de sesion de Streamlit."""
    config = engine.cargar_config()
    defaults = {
        "plantilla_nombre": None,
        "combo_nombre": "",
        "firma_slug": config.get("firma_default", ""),
        "para": [],
        "cc": [],
        "cco": [],
        "empresa_correo": "",
        "asunto": "",
        "selecciones": {},
        "personalizado": "",
        "adjuntos_seleccionados": [],
        "preview_css": "",
        "html_preview": "",
        "tema": "Sistema",
        "ultimo_eml_generado": "",
        "_slot_orden_activo": {},
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def resetear_selecciones() -> None:
    """Borra las selecciones de bloques cuando cambia la plantilla."""
    st.session_state["selecciones"] = {}
    st.session_state["combo_nombre"] = ""
    st.session_state["asunto"] = ""
    st.session_state["personalizado"] = ""
    st.session_state["adjuntos_seleccionados"] = []
    st.session_state["_slot_orden_activo"] = {}


def contactos_opciones() -> list[tuple[str, str]]:
    """Devuelve lista de (email, etiqueta) de contactos."""
    contactos = engine.listar_contactos()
    opciones: list[tuple[str, str]] = []
    for c in contactos:
        email = c["datos"].get("email", "")
        nombre = c["datos"].get("nombre", "")
        empresa = c["datos"].get("empresa", "")
        etiqueta = f"{nombre} <{email}> ({empresa})"
        opciones.append((email, etiqueta))
    return opciones


def contacto_por_email(email: str) -> dict[str, Any] | None:
    """Alias seguro para cargar contacto por email."""
    if not email:
        return None
    return engine.cargar_contacto_por_email(email)


def listar_opciones_con_indices(opciones: list[str]) -> list[tuple[int, str]]:
    """Devuelve lista de opciones con indice 1-based."""
    return [(i + 1, op) for i, op in enumerate(opciones)]


def aplicar_combo(nombre_plantilla: str, combo_nombre: str) -> None:
    """Aplica un combo guardado al estado actual."""
    if not combo_nombre:
        resetear_selecciones()
        return
    combos = engine.listar_combos(nombre_plantilla)
    if combo_nombre in combos:
        combo = combos[combo_nombre]
        st.session_state["selecciones"] = {
            k: [int(v) for v in vals] for k, vals in combo.items() if k not in ("asunto", "personalizado", "adjuntos_seleccionados")
        }
        st.session_state["asunto"] = combo.get("asunto", "")
        st.session_state["personalizado"] = combo.get("personalizado", "")
        st.session_state["adjuntos_seleccionados"] = combo.get("adjuntos_seleccionados", [])
        st.toast(f"Combinacion '{combo_nombre}' cargada")
    else:
        st.toast(f"Combinacion '{combo_nombre}' no encontrada")


def guardar_combo_ui(plantilla_nombre: str) -> None:
    """Muestra dialogo para guardar la combinacion actual."""
    selecciones = st.session_state["selecciones"]
    payload: dict[str, Any] = {}
    payload.update({k: [int(v) for v in vals] for k, vals in selecciones.items()})
    payload["asunto"] = st.session_state.get("asunto", "")
    payload["personalizado"] = st.session_state.get("personalizado", "")
    payload["adjuntos_seleccionados"] = st.session_state.get("adjuntos_seleccionados", [])

    with st.popover("Guardar combinacion"):
        nombre = st.text_input("Nombre de la combinacion", placeholder="oferta_corta")
        if st.button("Guardar", use_container_width=True):
            if not nombre:
                st.error("Escribe un nombre para la combinacion")
                return
            combos = engine.listar_combos(plantilla_nombre)
            if nombre in combos:
                st.warning(f"La combinacion '{nombre}' ya existe. Se sobrescribira.")
                confirmar = st.checkbox("Confirmar sobrescritura")
                if not confirmar:
                    return
            engine.guardar_combo(plantilla_nombre, nombre, payload)
            st.session_state["combo_nombre"] = nombre
            st.success(f"Combinacion '{nombre}' guardada")
            st.rerun()


def renderizar_preview(
    plantilla: dict,
    firma: dict[str, Any] | None,
    variables: dict[str, str],
) -> str:
    """Renderiza el HTML de previsualizacion."""
    firma_html, _ = engine.renderizar_firma(firma, variables)
    html = engine.ensamblar_html(
        plantilla=plantilla,
        selecciones=st.session_state["selecciones"],
        variables=variables,
        firma_html=firma_html,
        personalizados={"personalizado": st.session_state["personalizado"]},
    )

    css_extra = st.session_state.get("preview_css", "")
    if css_extra:
        html = html.replace("</head>", f"<style>{css_extra}</style></head>")

    return html


def mostrar_estado_validacion(html: str) -> tuple[bool, list[str], list[str]]:
    """Muestra caja de estado en la preview y devuelve (ok, obligatorios, pendientes)."""
    obligatorios, pendientes = engine.detectar_variables_pendientes(html)
    para = st.session_state.get("para", [])
    asunto = st.session_state.get("asunto", "")
    ultimo = st.session_state.get("ultimo_eml_generado", "")

    todo_ok = not obligatorios and para and asunto

    with st.container(border=True):
        if ultimo:
            st.success(f"Correo generado en esta sesion: {ultimo}")
        if not para:
            st.warning("Falta al menos un destinatario en 'Para'")
        if not asunto:
            st.warning("Falta el asunto")
        if obligatorios:
            st.error(f"Campos obligatorios sin rellenar: {', '.join(obligatorios)}")
        if pendientes:
            st.info(f"Campos pendientes (no obligatorios): {', '.join(pendientes)}")
        if todo_ok:
            st.success("Listo para generar el correo")

    return todo_ok, obligatorios, pendientes


def panel_configuracion() -> None:
    """Muestra panel de configuracion en la barra lateral."""
    config = engine.cargar_config()

    with st.sidebar.expander("⚙️ Configuracion", expanded=False):
        st.markdown("Valores por defecto")

        plantillas = engine.listar_plantillas()
        nombres_plantillas = [p["nombre"] for p in plantillas]
        plantilla_default = st.selectbox(
            "Plantilla por defecto",
            options=[""] + nombres_plantillas,
            index=([""] + nombres_plantillas).index(config.get("plantilla_default", ""))
            if config.get("plantilla_default", "") in ([""] + nombres_plantillas)
            else 0,
            key="cfg_plantilla_default",
        )

        firmas = engine.listar_firmas()
        firma_opciones = [""] + [f["slug"] for f in firmas]
        firma_default = st.selectbox(
            "Firma por defecto",
            options=firma_opciones,
            index=firma_opciones.index(config.get("firma_default", ""))
            if config.get("firma_default", "") in firma_opciones
            else 0,
            key="cfg_firma_default",
        )

        remitente_default = st.text_input(
            "Remitente por defecto",
            value=config.get("remitente_default", "tu@correo.com"),
            key="cfg_remitente_default",
        )

        plantilla_sel = plantilla_default or (nombres_plantillas[0] if nombres_plantillas else "")
        combos = engine.listar_combos(plantilla_sel) if plantilla_sel else {}
        combo_opciones = [""] + list(combos.keys())
        combo_default = st.selectbox(
            "Combinacion por defecto",
            options=combo_opciones,
            index=combo_opciones.index(config.get("combo_default", ""))
            if config.get("combo_default", "") in combo_opciones
            else 0,
            key="cfg_combo_default",
        )

        if st.button("Guardar configuracion", use_container_width=True):
            config["plantilla_default"] = plantilla_default or None
            config["firma_default"] = firma_default or None
            config["combo_default"] = combo_default or ""
            config["remitente_default"] = remitente_default.strip() or "tu@correo.com"
            engine.guardar_config(config)
            st.success("Configuracion guardada")


def aplicar_config_inicial(config: dict[str, Any], plantillas: list[dict[str, str]]) -> None:
    """Carga plantilla/combo por defecto si el estado aun no esta fijado."""
    nombres_plantillas = [p["nombre"] for p in plantillas]
    if not nombres_plantillas:
        return

    if st.session_state["plantilla_nombre"] is None:
        plantilla_default = config.get("plantilla_default")
        if plantilla_default and plantilla_default in nombres_plantillas:
            st.session_state["plantilla_nombre"] = plantilla_default
        else:
            st.session_state["plantilla_nombre"] = nombres_plantillas[0]

        # Aplicar combo por defecto si coincide con la plantilla cargada
        combo_default = config.get("combo_default", "")
        if combo_default:
            combos = engine.listar_combos(st.session_state["plantilla_nombre"])
            if combo_default in combos:
                st.session_state["combo_nombre"] = combo_default
                aplicar_combo(st.session_state["plantilla_nombre"], combo_default)

    if not st.session_state.get("firma_slug"):
        st.session_state["firma_slug"] = config.get("firma_default", "")


def main() -> None:
    inicializar_estado()

    # Cargar config y plantillas
    config = engine.cargar_config()
    plantillas = engine.listar_plantillas()
    if not plantillas:
        st.error("No se encontraron plantillas. Crea una carpeta en templates/ con diseno.html y campos.md")
        return

    aplicar_config_inicial(config, plantillas)

    nombres_plantillas = [p["nombre"] for p in plantillas]

    # Tema en sidebar
    st.sidebar.markdown("### Apariencia")
    tema = st.sidebar.radio(
        "Tema",
        ["Sistema", "Claro", "Oscuro"],
        horizontal=True,
        index=["Sistema", "Claro", "Oscuro"].index(st.session_state.get("tema", "Sistema")),
        key="tema_select",
    )
    st.session_state["tema"] = tema
    css_tema = THEME_CSS.get(tema, "")
    if css_tema:
        st.markdown(f"<style>{css_tema}</style>", unsafe_allow_html=True)

    panel_configuracion()

    st.title("📧 Dynamica Plantillas")
    st.markdown("Generador determinista de correos electronicos")

    col_principal, col_preview = st.columns([2, 3])

    with col_principal:
        st.subheader("1. Plantilla y combinacion")

        plantilla_nombre = st.selectbox(
            "Plantilla",
            nombres_plantillas,
            index=nombres_plantillas.index(st.session_state["plantilla_nombre"])
            if st.session_state["plantilla_nombre"] in nombres_plantillas
            else 0,
            key="plantilla_nombre_select",
        )

        if plantilla_nombre != st.session_state["plantilla_nombre"]:
            st.session_state["plantilla_nombre"] = plantilla_nombre
            resetear_selecciones()
            st.rerun()

        plantilla = engine.cargar_plantilla(plantilla_nombre)
        slots = engine.detectar_slots(plantilla["diseno"])

        combos = engine.listar_combos(plantilla_nombre)
        combo_opciones = [""] + list(combos.keys())
        combo_nombre = st.selectbox(
            "Combinacion",
            combo_opciones,
            index=combo_opciones.index(st.session_state["combo_nombre"])
            if st.session_state["combo_nombre"] in combo_opciones
            else 0,
            key="combo_nombre_select",
        )
        if combo_nombre != st.session_state["combo_nombre"]:
            st.session_state["combo_nombre"] = combo_nombre
            aplicar_combo(plantilla_nombre, combo_nombre)
            st.rerun()

        st.divider()
        st.subheader("2. Personas")

        opciones_contactos = contactos_opciones()
        emails_contactos = [email for email, _ in opciones_contactos]
        etiquetas_contactos = {email: etiqueta for email, etiqueta in opciones_contactos}

        with st.expander("Anadir persona"):
            with st.form("form_nuevo_contacto", clear_on_submit=True):
                nombre_input = st.text_input("Nombre", key="nuevo_nombre")
                email_input = st.text_input("Email", key="nuevo_email")
                empresa_input = st.text_input("Empresa", key="nuevo_empresa")
                submit = st.form_submit_button("Anadir")

            if submit:
                nombre = nombre_input.strip()
                email = email_input.strip()
                empresa = empresa_input.strip()
                if not nombre or not email or not empresa:
                    st.error("Rellena todos los campos")
                elif "@" not in email:
                    st.error("Email no valido")
                elif email in emails_contactos:
                    st.error("Ya existe un contacto con ese email")
                else:
                    try:
                        engine.crear_o_actualizar_contacto(nombre, email, empresa)
                        st.success(f"Persona anadida: {nombre}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar contacto: {e}")

        if opciones_contactos:
            with st.expander("Editar o eliminar persona"):
                email_editar = st.selectbox(
                    "Selecciona contacto",
                    options=[email for email, _ in opciones_contactos],
                    format_func=lambda x: etiquetas_contactos.get(x, x),
                    key="persona_editar_select",
                )
                if email_editar:
                    c = engine.cargar_contacto_por_email(email_editar)
                    if c:
                        datos = c["datos"]
                        edit_nombre = st.text_input(
                            "Nombre",
                            value=datos.get("nombre", ""),
                            key="edit_nombre",
                        )
                        edit_email = st.text_input(
                            "Email",
                            value=datos.get("email", ""),
                            key="edit_email",
                        )
                        edit_empresa = st.text_input(
                            "Empresa",
                            value=datos.get("empresa", ""),
                            key="edit_empresa",
                        )
                        col_g1, col_g2 = st.columns(2)
                        with col_g1:
                            if st.button("Guardar cambios", key="guardar_persona"):
                                if not edit_nombre or not edit_email or not edit_empresa:
                                    st.error("Rellena todos los campos")
                                elif "@" not in edit_email:
                                    st.error("Email no valido")
                                else:
                                    engine.guardar_contacto(
                                        c["slug"],
                                        {
                                            "nombre": edit_nombre,
                                            "email": edit_email,
                                            "empresa": edit_empresa,
                                        },
                                        c.get("historial", ""),
                                    )
                                    # Actualizar destinatarios si el email cambio
                                    if edit_email != email_editar:
                                        for campo in ["para", "cc", "cco"]:
                                            st.session_state[campo] = [
                                                edit_email if x == email_editar else x
                                                for x in st.session_state.get(campo, [])
                                            ]
                                    st.success("Persona actualizada")
                                    st.rerun()
                        with col_g2:
                            if st.button("Eliminar", key="eliminar_persona"):
                                engine.eliminar_contacto(c["slug"])
                                # Limpiar de destinatarios si estaba
                                for campo in ["para", "cc", "cco"]:
                                    st.session_state[campo] = [
                                        x for x in st.session_state.get(campo, []) if x != email_editar
                                    ]
                                # Limpiar empresa si el eliminado era el primer destinatario
                                if st.session_state.get("para") and st.session_state["para"][0] == email_editar:
                                    st.session_state["empresa_correo"] = ""
                                st.success("Persona eliminada")
                                st.rerun()
        else:
            st.info("No hay contactos. Anade uno arriba.")

        st.divider()
        st.subheader("3. Destinatarios")

        # Filtrar duplicados: un contacto solo puede estar en una categoria
        para = st.multiselect(
            "Para",
            options=emails_contactos,
            format_func=lambda x: etiquetas_contactos.get(x, x),
            default=st.session_state.get("para", []),
            key="para_select",
        )
        st.session_state["para"] = para

        disponibles_cc = [e for e in emails_contactos if e not in para]
        etiquetas_cc = {k: v for k, v in etiquetas_contactos.items() if k in disponibles_cc}
        cc = st.multiselect(
            "CC",
            options=disponibles_cc,
            format_func=lambda x: etiquetas_cc.get(x, x),
            default=[e for e in st.session_state.get("cc", []) if e in disponibles_cc],
            key="cc_select",
        )
        st.session_state["cc"] = cc

        disponibles_cco = [e for e in emails_contactos if e not in para and e not in cc]
        etiquetas_cco = {k: v for k, v in etiquetas_contactos.items() if k in disponibles_cco}
        cco = st.multiselect(
            "CCO",
            options=disponibles_cco,
            format_func=lambda x: etiquetas_cco.get(x, x),
            default=[e for e in st.session_state.get("cco", []) if e in disponibles_cco],
            key="cco_select",
        )
        st.session_state["cco"] = cco

        # Actualizar empresa del correo segun primer destinatario de Para
        primer_para_anterior = st.session_state.get("_primer_para_anterior", "")
        primer_para_actual = para[0] if para else ""
        if primer_para_actual != primer_para_anterior:
            st.session_state["_primer_para_anterior"] = primer_para_actual
            if primer_para_actual:
                c = contacto_por_email(primer_para_actual)
                if c:
                    st.session_state["empresa_correo"] = c["datos"].get("empresa", "")
            else:
                st.session_state["empresa_correo"] = ""

        st.divider()
        st.subheader("4. Empresa para este correo")

        empresa_correo = st.text_input(
            "Empresa",
            value=st.session_state.get("empresa_correo", ""),
            key="empresa_correo_input",
        )
        st.session_state["empresa_correo"] = empresa_correo

        st.divider()
        st.subheader("5. Asunto")

        asuntos = plantilla.get("asuntos", [])
        variables_asunto = {
            "nombre": contacto_por_email(para[0])["datos"].get("nombre", "") if para else "",
            "email": para[0] if para else "",
            "empresa": empresa_correo,
        }
        asuntos_renderizados = [
            engine.jinja2.Template(a).render(**variables_asunto) for a in asuntos
        ]

        asunto_sel = st.selectbox(
            "Asunto base",
            asuntos_renderizados,
            index=asuntos_renderizados.index(st.session_state["asunto"])
            if st.session_state["asunto"] in asuntos_renderizados
            else 0,
            key="asunto_base",
        )

        # Detectar si el usuario acaba de cambiar el asunto base
        if st.session_state.get("_asunto_base_anterior") != asunto_sel:
            st.session_state["asunto"] = asunto_sel
            st.session_state["_asunto_base_anterior"] = asunto_sel

        asunto_valor = st.text_input(
            "Asunto editable",
            value=st.session_state.get("asunto", ""),
            key="asunto_input",
        )
        st.session_state["asunto"] = asunto_valor

        st.divider()
        st.subheader("6. Archivos adjuntos")

        adjuntos = plantilla.get("adjuntos", [])
        if adjuntos:
            adjuntos_seleccionados = st.multiselect(
                "Adjuntos",
                options=adjuntos,
                format_func=lambda x: f"📎 {x.name}",
                default=st.session_state["adjuntos_seleccionados"],
                key="adjuntos_select",
            )
            st.session_state["adjuntos_seleccionados"] = adjuntos_seleccionados
        else:
            st.info("Esta plantilla no tiene adjuntos")

        st.divider()
        st.subheader("7. Bloques del correo")

        for slot in slots:
            if slot in ("firma", "texto_obligatorio"):
                continue
            if slot.startswith("personalizado"):
                continue
            if slot not in plantilla["campos"] or not plantilla["campos"][slot]:
                continue

            st.markdown(f"**{slot.capitalize()}**")
            opciones = listar_opciones_con_indices(plantilla["campos"][slot])
            seleccion_actual = st.session_state["selecciones"].get(slot, [])
            activo = st.session_state.get("_slot_orden_activo", {}).get(slot)

            col1, col2 = st.columns([3, 1])
            with col1:
                seleccionados_nuevos = st.multiselect(
                    f"Opciones de {slot}",
                    options=[idx for idx, _ in opciones],
                    format_func=lambda x: next(texto for idx, texto in opciones if idx == x),
                    default=seleccion_actual,
                    key=f"multiselect_{slot}",
                )
            with col2:
                st.caption("Orden")
                # Seleccionar cual elemento mover
                opciones_activas = [
                    (idx, texto) for idx, texto in opciones if idx in seleccionados_nuevos
                ]
                if opciones_activas:
                    nombres_opciones = {idx: texto for idx, texto in opciones_activas}
                    activo = st.selectbox(
                        "Mover",
                        options=[idx for idx, _ in opciones_activas],
                        format_func=lambda x: nombres_opciones[x][:40],
                        index=0,
                        key=f"orden_activo_{slot}",
                        label_visibility="collapsed",
                    )
                    st.session_state["_slot_orden_activo"][slot] = activo
                    col_up, col_down = st.columns(2)
                    with col_up:
                        if st.button("⬆️", key=f"up_{slot}"):
                            if activo in seleccionados_nuevos:
                                idx_pos = seleccionados_nuevos.index(activo)
                                if idx_pos > 0:
                                    nueva = list(seleccionados_nuevos)
                                    nueva[idx_pos - 1], nueva[idx_pos] = nueva[idx_pos], nueva[idx_pos - 1]
                                    st.session_state["selecciones"][slot] = nueva
                                    st.rerun()
                    with col_down:
                        if st.button("⬇️", key=f"down_{slot}"):
                            if activo in seleccionados_nuevos:
                                idx_pos = seleccionados_nuevos.index(activo)
                                if idx_pos < len(seleccionados_nuevos) - 1:
                                    nueva = list(seleccionados_nuevos)
                                    nueva[idx_pos], nueva[idx_pos + 1] = nueva[idx_pos + 1], nueva[idx_pos]
                                    st.session_state["selecciones"][slot] = nueva
                                    st.rerun()
                else:
                    st.session_state["_slot_orden_activo"][slot] = None
                    st.caption("Selecciona opciones")

                if st.button("🗑️", key=f"clear_{slot}"):
                    st.session_state["selecciones"][slot] = []
                    st.session_state["_slot_orden_activo"][slot] = None
                    st.rerun()

            st.session_state["selecciones"][slot] = seleccionados_nuevos

            if seleccionados_nuevos:
                orden_texto = "\n".join(
                    f"{pos}. {next(texto for idx, texto in opciones if idx == i)}"
                    for pos, i in enumerate(seleccionados_nuevos, start=1)
                )
                st.markdown(orden_texto)

        st.divider()
        st.subheader("8. Campo personalizado")

        personalizado = st.text_area(
            "Texto personalizado (Markdown soportado)",
            value=st.session_state["personalizado"],
            height=120,
            key="personalizado_input",
        )
        st.session_state["personalizado"] = personalizado

        st.divider()
        st.subheader("9. Firma")

        firmas = engine.listar_firmas()
        firma_opciones = [("", "Sin firma")] + [(f["slug"], f["nombre"]) for f in firmas]
        firma_default = config.get("firma_default", "")
        default_index = next(
            (i for i, (slug, _) in enumerate(firma_opciones) if slug == firma_default),
            0,
        )
        firma_slug = st.selectbox(
            "Firma",
            options=[slug for slug, _ in firma_opciones],
            format_func=lambda x: next(nombre for slug, nombre in firma_opciones if slug == x),
            index=default_index,
            key="firma_slug_select",
        )
        st.session_state["firma_slug"] = firma_slug
        firma = engine.cargar_firma(firma_slug) if firma_slug else None

        st.divider()

        # Variables base del primer destinatario principal
        primer_contacto = contacto_por_email(para[0]) if para else None
        nombre_destinatario = primer_contacto["datos"].get("nombre", "") if primer_contacto else ""
        variables = {
            "nombre": nombre_destinatario,
            "email": para[0] if para else "",
            "empresa": empresa_correo,
        }

        html_preview = renderizar_preview(plantilla, firma, variables)
        st.session_state["html_preview"] = html_preview

        # Botones de accion
        col_guardar, col_generar = st.columns(2)
        with col_guardar:
            guardar_combo_ui(plantilla_nombre)

        with col_generar:
            if st.button("Generar .eml", type="primary", use_container_width=True):
                errores = engine.validar_html_final(html_preview)
                if errores:
                    st.error("Hay campos obligatorios sin rellenar: " + ", ".join(errores))
                elif not para:
                    st.error("Selecciona al menos un destinatario en 'Para'")
                elif not asunto_valor:
                    st.error("Escribe un asunto")
                else:
                    destinatarios: list[dict[str, str]] = []
                    for email in para:
                        c = contacto_por_email(email)
                        destinatarios.append(
                            {
                                "tipo": "para",
                                "email": email,
                                "nombre": c["datos"].get("nombre", "") if c else "",
                                "empresa": empresa_correo,
                            }
                        )
                    for email in cc:
                        c = contacto_por_email(email)
                        destinatarios.append(
                            {
                                "tipo": "cc",
                                "email": email,
                                "nombre": c["datos"].get("nombre", "") if c else "",
                                "empresa": empresa_correo,
                            }
                        )
                    for email in cco:
                        c = contacto_por_email(email)
                        destinatarios.append(
                            {
                                "tipo": "cco",
                                "email": email,
                                "nombre": c["datos"].get("nombre", "") if c else "",
                                "empresa": empresa_correo,
                            }
                        )

                    from_email = config.get("remitente_default", "tu@correo.com")
                    firma_html, imagenes_firma = engine.renderizar_firma(firma, variables)
                    html_final = engine.ensamblar_html(
                        plantilla=plantilla,
                        selecciones=st.session_state["selecciones"],
                        variables=variables,
                        firma_html=firma_html,
                        personalizados={"personalizado": personalizado},
                    )
                    ruta_eml = engine.generar_eml(
                        destinatarios=destinatarios,
                        asunto=asunto_valor,
                        html_final=html_final,
                        from_email=from_email,
                        adjuntos=st.session_state["adjuntos_seleccionados"],
                        imagenes_inline=imagenes_firma,
                    )
                    # Registrar en todos los destinatarios principales
                    for email in para:
                        c = contacto_por_email(email)
                        if c:
                            engine.registrar_envio_en_contacto(c, ruta_eml)
                    st.session_state["ultimo_eml_generado"] = ruta_eml.name
                    st.success(f"Correo generado: {ruta_eml.name}")
                    utils.abrir_archivo(ruta_eml)

    with col_preview:
        st.subheader("Previsualizacion")

        with st.expander("Editar CSS de preview"):
            css_extra = st.text_area(
                "CSS adicional (solo afecta a esta previsualizacion)",
                value=st.session_state.get("preview_css", ""),
                height=100,
                key="preview_css_input",
            )
            st.session_state["preview_css"] = css_extra

        if st.session_state.get("html_preview"):
            # Renderizar de nuevo si cambia CSS
            plantilla = engine.cargar_plantilla(st.session_state["plantilla_nombre"])
            firma = engine.cargar_firma(st.session_state["firma_slug"]) if st.session_state["firma_slug"] else None

            para_emails = st.session_state.get("para", [])
            primer_email = para_emails[0] if para_emails else None
            primer_contacto = contacto_por_email(primer_email) if primer_email else None
            variables = {
                "nombre": primer_contacto["datos"].get("nombre", "") if primer_contacto else "",
                "email": primer_email or "",
                "empresa": st.session_state.get("empresa_correo", ""),
            }

            cc_emails = st.session_state.get("cc", [])
            cco_emails = st.session_state.get("cco", [])

            # --- Tarjeta de metadatos ---
            st.markdown("### Metadatos del correo")
            meta_asunto = st.session_state.get("asunto", "")

            def etiqueta_contacto(email: str) -> str:
                c = contacto_por_email(email)
                if not c:
                    return email
                nombre = c["datos"].get("nombre", "")
                return f"{nombre} <{email}>"

            with st.container(border=True):
                st.markdown(f"📧 **Asunto:** {meta_asunto}")
                if para_emails:
                    st.markdown(f"👤 **Para:** {', '.join(etiqueta_contacto(e) for e in para_emails)}")
                if cc_emails:
                    st.markdown(f"👥 **CC:** {', '.join(etiqueta_contacto(e) for e in cc_emails)}")
                if cco_emails:
                    st.markdown(f"👁️ **CCO:** {', '.join(etiqueta_contacto(e) for e in cco_emails)}")
                st.markdown(f"🏢 **Empresa:** {st.session_state.get('empresa_correo', '')}")
                meta_adjuntos = st.session_state.get("adjuntos_seleccionados", [])
                if meta_adjuntos:
                    nombres_adjuntos = ", ".join(a.name for a in meta_adjuntos)
                    st.markdown(f"📎 **Adjuntos:** {nombres_adjuntos}")

            # --- Estado de validacion ---
            html = renderizar_preview(plantilla, firma, variables)
            mostrar_estado_validacion(html)

            st.markdown("---")
            st.markdown("### Vista previa del correo")
            st.components.v1.html(html, height=700, scrolling=True)
        else:
            st.info("Configura los campos para ver la previsualizacion")


if __name__ == "__main__":
    main()
