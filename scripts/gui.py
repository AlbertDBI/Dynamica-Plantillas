"""
Interfaz grafica web para Dynamica Plantillas usando Streamlit.

Ejecutar con:
    streamlit run scripts/gui.py
"""
from __future__ import annotations

import sys
from pathlib import Path

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


def inicializar_estado() -> None:
    """Inicializa el estado de sesion de Streamlit."""
    defaults = {
        "plantilla_nombre": None,
        "combo_nombre": "",
        "firma_slug": "",
        "contacto_email": "",
        "empresa_correo": "",
        "cc": "",
        "cco": "",
        "asunto": "",
        "selecciones": {},
        "personalizado": "",
        "adjuntos_seleccionados": [],
        "preview_css": "",
        "html_preview": "",
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


def listar_opciones_con_indices(opciones: list[str]) -> list[tuple[int, str]]:
    """Devuelve lista de opciones con indice 1-based."""
    return [(i + 1, op) for i, op in enumerate(opciones)]


def aplicar_combo() -> None:
    """Aplica un combo guardado al estado actual."""
    nombre_plantilla = st.session_state["plantilla_nombre"]
    combo_nombre = st.session_state["combo_nombre"]
    if not combo_nombre:
        resetear_selecciones()
        return
    combos = engine.listar_combos(nombre_plantilla)
    if combo_nombre in combos:
        st.session_state["selecciones"] = {
            k: [int(v) for v in vals] for k, vals in combos[combo_nombre].items()
        }
        st.toast(f"Combo '{combo_nombre}' cargado")
    else:
        st.toast(f"Combo '{combo_nombre}' no encontrado")


def guardar_combo_ui(plantilla_nombre: str) -> None:
    """Muestra dialogo para guardar el combo actual."""
    with st.popover("Guardar plantilla de plantilla"):
        nombre = st.text_input("Nombre del combo", placeholder="oferta_corta")
        if st.button("Guardar", use_container_width=True):
            if not nombre:
                st.error("Escribe un nombre para el combo")
                return
            combos = engine.listar_combos(plantilla_nombre)
            if nombre in combos:
                st.warning(f"El combo '{nombre}' ya existe. Se sobrescribira.")
                confirmar = st.checkbox("Confirmar sobrescritura")
                if not confirmar:
                    return
            engine.guardar_combo(
                plantilla_nombre,
                nombre,
                st.session_state["selecciones"],
            )
            st.session_state["combo_nombre"] = nombre
            st.success(f"Combo '{nombre}' guardado")
            st.rerun()


def renderizar_preview(
    plantilla: dict,
    firma: dict[str, Any] | None,
    variables: dict[str, str],
) -> str:
    """Renderiza el HTML de previsualizacion y lo guarda temporalmente."""
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


def main() -> None:
    inicializar_estado()

    # Tema
    tema = st.sidebar.radio("Tema", ["Sistema", "Claro", "Oscuro"], horizontal=True)
    if tema == "Claro":
        st.markdown(
            """
            <script>
                const doc = window.parent.document;
                doc.querySelector('[data-testid="stAppViewContainer"]').classList.remove('dark');
                doc.querySelector('[data-testid="stAppViewContainer"]').classList.add('light');
            </script>
            """,
            unsafe_allow_html=True,
        )
    elif tema == "Oscuro":
        st.markdown(
            """
            <script>
                const doc = window.parent.document;
                doc.querySelector('[data-testid="stAppViewContainer"]').classList.remove('light');
                doc.querySelector('[data-testid="stAppViewContainer"]').classList.add('dark');
            </script>
            """,
            unsafe_allow_html=True,
        )

    st.title("📧 Dynamica Plantillas")
    st.markdown("Generador determinista de correos electrónicos")

    # Cargar config y plantillas
    config = engine.cargar_config()
    plantillas = engine.listar_plantillas()
    if not plantillas:
        st.error("No se encontraron plantillas. Crea una carpeta en templates/ con diseno.html y campos.md")
        return

    nombres_plantillas = [p["nombre"] for p in plantillas]

    col_principal, col_preview = st.columns([2, 3])

    with col_principal:
        st.subheader("1. Plantilla y combo")

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
            "Plantilla de plantilla (combo)",
            combo_opciones,
            index=combo_opciones.index(st.session_state["combo_nombre"])
            if st.session_state["combo_nombre"] in combo_opciones
            else 0,
            key="combo_nombre_select",
        )
        if combo_nombre != st.session_state["combo_nombre"]:
            st.session_state["combo_nombre"] = combo_nombre
            aplicar_combo()
            st.rerun()

        st.divider()
        st.subheader("2. Firma")

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
        st.subheader("3. Destinatario")

        contactos = engine.listar_contactos()
        contacto_opciones = [("", "Nuevo contacto")] + [
            (c["datos"].get("email", ""), f"{c['datos'].get('nombre', '')} ({c['datos'].get('empresa', '')})")
            for c in contactos
        ]
        contacto_email = st.selectbox(
            "Contacto",
            options=[email for email, _ in contacto_opciones],
            format_func=lambda x: next(nombre for email, nombre in contacto_opciones if email == x),
            key="contacto_email_select",
        )
        st.session_state["contacto_email"] = contacto_email

        with st.expander("Nuevo contacto", expanded=not contacto_email):
            nuevo_nombre = st.text_input("Nombre", key="nuevo_nombre")
            nuevo_email = st.text_input("Email", key="nuevo_email")
            nuevo_empresa = st.text_input("Empresa", key="nuevo_empresa")
            if st.button("Crear contacto", key="crear_contacto"):
                if not nuevo_nombre or not nuevo_email or not nuevo_empresa:
                    st.error("Rellena todos los campos")
                elif "@" not in nuevo_email:
                    st.error("Email no valido")
                else:
                    engine.crear_o_actualizar_contacto(
                        nuevo_nombre, nuevo_email, nuevo_empresa
                    )
                    st.session_state["contacto_email"] = nuevo_email
                    st.success("Contacto creado")
                    st.rerun()

        contacto_seleccionado = engine.cargar_contacto_por_email(contacto_email) if contacto_email else None
        empresa_default = (
            contacto_seleccionado["datos"].get("empresa", "")
            if contacto_seleccionado
            else ""
        )
        if not st.session_state.get("empresa_correo"):
            st.session_state["empresa_correo"] = empresa_default

        empresa_correo = st.text_input(
            "Empresa para este correo",
            value=st.session_state["empresa_correo"],
            key="empresa_correo_input",
        )
        st.session_state["empresa_correo"] = empresa_correo

        cc = st.text_input("CC", value=st.session_state["cc"], key="cc_input")
        cco = st.text_input("CCO", value=st.session_state["cco"], key="cco_input")
        st.session_state["cc"] = cc
        st.session_state["cco"] = cco

        st.divider()
        st.subheader("4. Asunto")

        asuntos = plantilla.get("asuntos", [])
        if asuntos:
            variables_tmp = {
                "nombre": contacto_seleccionado["datos"].get("nombre", "") if contacto_seleccionado else "",
                "email": contacto_email,
                "empresa": empresa_correo,
            }
            asuntos_renderizados = [
                engine.jinja2.Template(a).render(**variables_tmp) for a in asuntos
            ]
            asunto_opciones = ["Personalizado"] + asuntos_renderizados
            asunto_sel = st.selectbox("Asunto base", asunto_opciones, key="asunto_base")
            if asunto_sel == "Personalizado":
                asunto_valor = st.text_input("Asunto", value=st.session_state["asunto"], key="asunto_input")
            else:
                asunto_valor = st.text_input(
                    "Asunto editable",
                    value=asunto_sel if not st.session_state["asunto"] else st.session_state["asunto"],
                    key="asunto_input",
                )
        else:
            asunto_valor = st.text_input("Asunto", value=st.session_state["asunto"], key="asunto_input")
        st.session_state["asunto"] = asunto_valor

        st.divider()
        st.subheader("5. Bloques del correo")

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
                if st.button("⬆️", key=f"up_{slot}"):
                    if len(seleccionados_nuevos) > 1:
                        st.session_state["selecciones"][slot] = seleccionados_nuevos[-1:] + seleccionados_nuevos[:-1]
                        st.rerun()
                if st.button("⬇️", key=f"down_{slot}"):
                    if len(seleccionados_nuevos) > 1:
                        st.session_state["selecciones"][slot] = seleccionados_nuevos[1:] + seleccionados_nuevos[:1]
                        st.rerun()
                if st.button("🗑️", key=f"clear_{slot}"):
                    st.session_state["selecciones"][slot] = []
                    st.rerun()

            st.session_state["selecciones"][slot] = seleccionados_nuevos

            if seleccionados_nuevos:
                orden_texto = "\n".join(
                    f"{pos}. {next(texto for idx, texto in opciones if idx == i)}"
                    for pos, i in enumerate(seleccionados_nuevos, start=1)
                )
                st.markdown(orden_texto)

        st.divider()
        st.subheader("6. Campo personalizado")

        personalizado = st.text_area(
            "Texto personalizado (Markdown soportado)",
            value=st.session_state["personalizado"],
            height=120,
            key="personalizado_input",
        )
        st.session_state["personalizado"] = personalizado

        st.divider()
        st.subheader("7. Adjuntos")

        adjuntos = plantilla.get("adjuntos", [])
        if adjuntos:
            adjuntos_seleccionados = st.multiselect(
                "Adjuntos",
                options=adjuntos,
                format_func=lambda x: x.name,
                default=st.session_state["adjuntos_seleccionados"],
                key="adjuntos_select",
            )
            st.session_state["adjuntos_seleccionados"] = adjuntos_seleccionados
        else:
            st.info("Esta plantilla no tiene adjuntos")

        st.divider()

        # Variables
        nombre_destinatario = (
            contacto_seleccionado["datos"].get("nombre", "") if contacto_seleccionado else ""
        )
        variables = {
            "nombre": nombre_destinatario,
            "email": contacto_email,
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
                elif not contacto_email:
                    st.error("Selecciona un destinatario")
                elif not asunto_valor:
                    st.error("Escribe un asunto")
                else:
                    destinatarios = [
                        {
                            "tipo": "para",
                            "email": contacto_email,
                            "nombre": nombre_destinatario,
                            "empresa": empresa_correo,
                        }
                    ]
                    if cc:
                        destinatarios.append({"tipo": "cc", "email": cc, "nombre": "", "empresa": ""})
                    if cco:
                        destinatarios.append({"tipo": "cco", "email": cco, "nombre": "", "empresa": ""})

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
                    if contacto_seleccionado:
                        engine.registrar_envio_en_contacto(contacto_seleccionado, ruta_eml)
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
            variables = {
                "nombre": "",
                "email": st.session_state["contacto_email"],
                "empresa": st.session_state["empresa_correo"],
            }
            contacto_preview = None
            if st.session_state["contacto_email"]:
                contacto_preview = engine.cargar_contacto_por_email(st.session_state["contacto_email"])
                if contacto_preview:
                    variables["nombre"] = contacto_preview["datos"].get("nombre", "")

            # --- Tarjeta de metadatos ---
            st.markdown("### Metadatos del correo")
            meta_asunto = st.session_state.get("asunto", "")
            meta_destinatarios: list[str] = []
            if contacto_preview:
                nombre_para = contacto_preview["datos"].get("nombre", "")
                email_para = contacto_preview["datos"].get("email", "")
                meta_destinatarios.append(f"👤 **Para:** {nombre_para} <{email_para}>")
            if st.session_state.get("cc"):
                meta_destinatarios.append(f"👥 **CC:** {st.session_state['cc']}")
            if st.session_state.get("cco"):
                meta_destinatarios.append(f"👁️ **CCO:** {st.session_state['cco']}")
            meta_adjuntos = st.session_state.get("adjuntos_seleccionados", [])

            with st.container(border=True):
                st.markdown(f"📧 **Asunto:** {meta_asunto}")
                for linea in meta_destinatarios:
                    st.markdown(linea)
                if meta_adjuntos:
                    nombres_adjuntos = ", ".join(a.name for a in meta_adjuntos)
                    st.markdown(f"📎 **Adjuntos:** {nombres_adjuntos}")

            st.markdown("---")
            st.markdown("### Vista previa del correo")
            html = renderizar_preview(plantilla, firma, variables)
            st.components.v1.html(html, height=700, scrolling=True)
        else:
            st.info("Configura los campos para ver la previsualizacion")


if __name__ == "__main__":
    main()
