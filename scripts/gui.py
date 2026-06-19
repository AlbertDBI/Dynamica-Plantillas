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


def inicializar_estado() -> None:
    """Inicializa el estado de sesion de Streamlit."""
    defaults = {
        "plantilla_nombre": None,
        "combo_nombre": "",
        "firma_slug": "",
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
        "refresh": False,
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


def actualizar_empresa_correo() -> None:
    """Actualiza 'empresa_correo' a partir del primer destinatario de Para."""
    para = st.session_state.get("para", [])
    empresa_actual = st.session_state.get("empresa_correo", "")
    if para:
        c = contacto_por_email(para[0])
        if c and not empresa_actual:
            st.session_state["empresa_correo"] = c["datos"].get("empresa", "")
    else:
        st.session_state["empresa_correo"] = ""


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
        st.subheader("2. Personas")

        opciones_contactos = contactos_opciones()
        emails_contactos = [email for email, _ in opciones_contactos]
        etiquetas_contactos = {email: etiqueta for email, etiqueta in opciones_contactos}

        with st.expander("Añadir persona"):
            version = st.session_state.get("form_contacto_version", 0)
            form_key = f"form_nuevo_contacto_{version}"
            with st.form(form_key):
                st.text_input("Nombre", key=f"nuevo_nombre_{version}")
                st.text_input("Email", key=f"nuevo_email_{version}")
                st.text_input("Empresa", key=f"nuevo_empresa_{version}")
                submit = st.form_submit_button("Añadir")

            if submit:
                nombre = st.session_state.get(f"nuevo_nombre_{version}", "").strip()
                email = st.session_state.get(f"nuevo_email_{version}", "").strip()
                empresa = st.session_state.get(f"nuevo_empresa_{version}", "").strip()
                if not nombre or not email or not empresa:
                    st.error("Rellena todos los campos")
                elif "@" not in email:
                    st.error("Email no valido")
                elif email in emails_contactos:
                    st.error("Ya existe un contacto con ese email")
                else:
                    try:
                        engine.crear_o_actualizar_contacto(nombre, email, empresa)
                        st.session_state["form_contacto_version"] = version + 1
                        st.success(f"Persona añadida: {nombre}")
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
            st.info("No hay contactos. Añade uno arriba.")

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
        # Se usa session_state para detectar si el primer destinatario cambio
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
        asunto_opciones = ["Personalizado"] + asuntos_renderizados
        asunto_sel = st.selectbox("Asunto base", asunto_opciones, key="asunto_base")
        if asunto_sel == "Personalizado":
            asunto_valor = st.text_input(
                "Asunto",
                value=st.session_state["asunto"],
                key="asunto_input",
            )
        else:
            asunto_valor = st.text_input(
                "Asunto editable",
                value=asunto_sel if not st.session_state["asunto"] else st.session_state["asunto"],
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

            st.markdown("---")
            st.markdown("### Vista previa del correo")
            html = renderizar_preview(plantilla, firma, variables)
            st.components.v1.html(html, height=700, scrolling=True)
        else:
            st.info("Configura los campos para ver la previsualizacion")


if __name__ == "__main__":
    main()
