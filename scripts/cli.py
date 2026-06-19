"""
CLI interactivo manual para Dynamica Plantillas.

Flujo definitivo:
  1. Seleccionar plantilla.
  2. Seleccionar firma (con 'Sin firma' y preseleccion por defecto).
  3. Gestionar destinatarios (Para, CC, CCO).
  4. Seleccionar/editar asunto.
  5. Para cada slot detectado en diseno.html, armar lista ordenada de bloques.
  6. Rellenar campos personalizados.
  7. Seleccionar adjuntos.
  8. Resumen y previsualizacion.
  9. Generar .eml y registrar en contactos.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Agregar la carpeta padre al path para importar engine y utils
sys.path.insert(0, str(Path(__file__).resolve().parent))

import engine
import utils


def pedir_input(mensaje: str, obligatorio: bool = True) -> str:
    while True:
        valor = input(mensaje).strip()
        if valor or not obligatorio:
            return valor
        print("Este campo es obligatorio.")


def pedir_texto_multilinea(mensaje: str) -> str:
    print(mensaje)
    print("Escribe tu texto. Cuando termines, envia una linea que solo contenga ###FIN###")
    lineas: list[str] = []
    while True:
        try:
            linea = input()
        except EOFError:
            break
        if linea.strip() == "###FIN###":
            break
        lineas.append(linea)
    return "\n".join(lineas).strip()


def seleccionar_indice(titulo: str, opciones: list[dict], permitir_cero: bool = True, cero_texto: str = "Ninguno") -> dict | None:
    print(f"\n{titulo}")
    for idx, op in enumerate(opciones, start=1):
        print(f"  {idx}. {op.get('nombre', op.get('archivo', str(idx)))}")
    if permitir_cero:
        print(f"  0. {cero_texto}")
    while True:
        try:
            seleccion = int(input("Selecciona una opcion: "))
            if permitir_cero and seleccion == 0:
                return None
            if 1 <= seleccion <= len(opciones):
                return opciones[seleccion - 1]
        except ValueError:
            pass
        print("Opcion no valida.")


def menu_multiseleccion(titulo: str, opciones: list[str]) -> list[int]:
    """
    Menu interactivo para armar una lista ordenada de opciones.
    Devuelve una lista de indices (1-based) en el orden seleccionado.
    """
    seleccionados: list[int] = []

    while True:
        print(f"\n=== {titulo.upper()} ===")
        print("Opciones disponibles:")
        for idx, op in enumerate(opciones, start=1):
            marcador = " [x]" if idx in seleccionados else " [ ]"
            print(f"  {idx}.{marcador} {op}")
        print("\nSeleccion actual:")
        if seleccionados:
            for pos, idx in enumerate(seleccionados, start=1):
                print(f"  {pos}. {opciones[idx - 1]}")
        else:
            print("  (vacio)")

        print("\nComandos:")
        print("  [numero]   Anadir opcion")
        print("  q [N]      Quitar opcion en posicion N")
        print("  s [N]      Subir opcion en posicion N")
        print("  b [N]      Bajar opcion en posicion N")
        print("  l          Listo, siguiente seccion")

        comando = input("Comando: ").strip().lower()
        if comando == "l":
            break
        if comando.startswith("q "):
            try:
                pos = int(comando.split()[1]) - 1
                if 0 <= pos < len(seleccionados):
                    seleccionados.pop(pos)
            except (ValueError, IndexError):
                pass
            continue
        if comando.startswith("s "):
            try:
                pos = int(comando.split()[1]) - 1
                if 0 < pos < len(seleccionados):
                    seleccionados[pos - 1], seleccionados[pos] = (
                        seleccionados[pos],
                        seleccionados[pos - 1],
                    )
            except (ValueError, IndexError):
                pass
            continue
        if comando.startswith("b "):
            try:
                pos = int(comando.split()[1]) - 1
                if 0 <= pos < len(seleccionados) - 1:
                    seleccionados[pos], seleccionados[pos + 1] = (
                        seleccionados[pos + 1],
                        seleccionados[pos],
                    )
            except (ValueError, IndexError):
                pass
            continue

        # Intentar anadir por numero
        try:
            idx = int(comando)
            if 1 <= idx <= len(opciones):
                seleccionados.append(idx)
            else:
                print("Numero fuera de rango.")
        except ValueError:
            print("Comando no reconocido.")

    return seleccionados


def validar_email(email: str) -> bool:
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None


def gestionar_destinatarios() -> list[dict[str, str]]:
    """Gestiona la lista de destinatarios (para, cc, cco)."""
    destinatarios: list[dict[str, str]] = []

    while True:
        print("\n--- Destinatario principal ---")
        email = ""
        while not validar_email(email):
            email = pedir_input("Email: ")
            if not validar_email(email):
                print("Email no valido.")

        contactos = engine.listar_contactos()
        contacto_existente = engine.cargar_contacto_por_email(email)

        if contacto_existente:
            print(f"Contacto existente: {contacto_existente['datos'].get('nombre')} ({contacto_existente['datos'].get('empresa')})")
            nombre = contacto_existente["datos"].get("nombre", "")
            empresa = contacto_existente["datos"].get("empresa", "")
        else:
            nombre = pedir_input("Nombre: ")
            empresa = pedir_input("Empresa: ")

        empresa_editada = input(f"Empresa para este correo [{empresa}]: ").strip()
        if empresa_editada:
            empresa = empresa_editada

        destinatarios.append(
            {
                "tipo": "para",
                "email": email,
                "nombre": nombre,
                "empresa": empresa,
            }
        )

        # Guardar o actualizar contacto
        extras = {}
        engine.crear_o_actualizar_contacto(nombre, email, empresa, extras)

        otro = input("\nAnadir otro destinatario principal? (s/n): ").strip().lower()
        if otro != "s":
            break

    # CC y CCO
    while True:
        cc = input("CC (email, vacio para omitir): ").strip()
        if not cc:
            break
        if validar_email(cc):
            destinatarios.append({"tipo": "cc", "email": cc, "nombre": "", "empresa": ""})
        else:
            print("Email no valido.")

    while True:
        cco = input("CCO (email, vacio para omitir): ").strip()
        if not cco:
            break
        if validar_email(cco):
            destinatarios.append({"tipo": "cco", "email": cco, "nombre": "", "empresa": ""})
        else:
            print("Email no valido.")

    return destinatarios


def seleccionar_firma(config: dict) -> dict[str, Any] | None:
    """Muestra las firmas disponibles con preseleccion de la firma por defecto."""
    firmas = engine.listar_firmas()
    if not firmas:
        print("\nNo se encontraron firmas en signatures/.")
        return None

    opciones = [{"nombre": "Sin firma", "slug": "", "archivo": ""}] + firmas
    default_slug = config.get("firma_default", "")
    default_idx = 0
    for idx, f in enumerate(opciones):
        if f.get("slug") == default_slug:
            default_idx = idx
            break

    print(f"\n--- Seleccionar firma (por defecto: {opciones[default_idx].get('nombre', 'Sin firma')}) ---")
    for idx, f in enumerate(opciones, start=1):
        marker = " *" if idx - 1 == default_idx else "  "
        print(f"{marker}{idx}. {f.get('nombre', f.get('archivo', ''))}")

    while True:
        try:
            seleccion = int(input("Selecciona firma: "))
            if 1 <= seleccion <= len(opciones):
                elegida = opciones[seleccion - 1]
                if elegida.get("slug"):
                    return engine.cargar_firma(elegida["slug"])
                return None
        except ValueError:
            pass
        print("Opcion no valida.")


def seleccionar_asunto(plantilla: dict[str, Any], variables: dict[str, str]) -> str:
    """Permite elegir un asunto de la lista o editarlo."""
    asuntos = plantilla.get("asuntos", [])
    if asuntos:
        print("\n--- Asunto ---")
        for idx, a in enumerate(asuntos, start=1):
            renderizado = engine.jinja2.Template(a).render(**variables)
            print(f"  {idx}. {renderizado}")
        print("  0. Escribir asunto manualmente")
        while True:
            try:
                op = int(input("Selecciona asunto: "))
                if op == 0:
                    break
                if 1 <= op <= len(asuntos):
                    asunto_base = asuntos[op - 1]
                    asunto_renderizado = engine.jinja2.Template(asunto_base).render(**variables)
                    editado = input(f"Asunto [{asunto_renderizado}]: ").strip()
                    return editado if editado else asunto_renderizado
            except ValueError:
                pass
            print("Opcion no valida.")
    return pedir_input("Asunto del correo: ")


def detectar_slots_personalizados(diseno_html: str) -> tuple[list[str], list[str]]:
    """Devuelve (personalizados_opcionales, personalizados_obligatorios)."""
    todos = engine.detectar_variables(diseno_html)
    opcionales = []
    obligatorios = []
    for slot in todos:
        if slot.startswith("personalizado"):
            if slot.endswith("_obligatorio"):
                obligatorios.append(slot)
            else:
                opcionales.append(slot)
    return opcionales, obligatorios


def main() -> None:
    print("=" * 60)
    print("  Dynamica Plantillas - Generador de correos .eml")
    print("=" * 60)

    # Cargar config
    config = engine.cargar_config()

    # Aplicar politica de limpieza de output
    utils.limpiar_output(
        engine.OUTPUT_DIR,
        config.get("output", {}).get("modo", "dias"),
        config.get("output", {}).get("dias", 30),
    )

    # 1. Seleccionar plantilla
    plantillas = engine.listar_plantillas()
    if not plantillas:
        print("\nNo se encontraron plantillas en templates/.")
        print("Crea una carpeta con diseno.html y campos.md.")
        sys.exit(1)

    plantilla_elegida = seleccionar_indice("Plantillas disponibles:", plantillas, permitir_cero=False)
    if not plantilla_elegida:
        sys.exit(1)

    plantilla = engine.cargar_plantilla(plantilla_elegida["nombre"])

    # 2. Seleccionar firma
    firma = seleccionar_firma(config)

    # 3. Destinatarios
    destinatarios = gestionar_destinatarios()
    if not destinatarios:
        print("Debe haber al menos un destinatario.")
        sys.exit(1)

    # Variables base: del primer destinatario principal
    variables = {
        "nombre": destinatarios[0].get("nombre", ""),
        "email": destinatarios[0].get("email", ""),
        "empresa": destinatarios[0].get("empresa", ""),
    }

    # 4. Asunto
    asunto = seleccionar_asunto(plantilla, variables)

    # 5. Armar cada slot detectado en diseno.html
    slots = engine.detectar_slots(plantilla["diseno"])
    selecciones: dict[str, list[int]] = {}

    for slot in slots:
        if slot in ("firma", "texto_obligatorio"):
            continue
        if slot.startswith("personalizado"):
            continue
        if slot not in plantilla["campos"]:
            continue
        opciones = plantilla["campos"][slot]
        if not opciones:
            continue
        seleccionados = menu_multiseleccion(slot, opciones)
        selecciones[slot] = seleccionados

    # 6. Campos personalizados
    personalizados_opcionales, personalizados_obligatorios = detectar_slots_personalizados(plantilla["diseno"])
    personalizados: dict[str, str] = {}

    for slot in personalizados_obligatorios + personalizados_opcionales:
        obligatorio = slot in personalizados_obligatorios
        while True:
            texto = pedir_texto_multilinea(f"Texto para {{{{{slot}}}}} {'(obligatorio)' if obligatorio else '(dejar vacio para omitir)'}:")
            if obligatorio and not texto.strip():
                print("Este campo es obligatorio.")
                continue
            personalizados[slot] = texto
            break

    # 7. Adjuntos
    adjuntos_seleccionados: list[Path] = []
    adjuntos_disponibles = plantilla.get("adjuntos", [])
    if adjuntos_disponibles:
        print("\n--- Adjuntos disponibles ---")
        for idx, a in enumerate(adjuntos_disponibles, start=1):
            print(f"  {idx}. {a.name}")
        print("  0. Ninguno")
        seleccion = input("Selecciona adjuntos separados por comas: ").strip()
        if seleccion and seleccion != "0":
            for item in seleccion.split(","):
                try:
                    idx = int(item.strip()) - 1
                    if 0 <= idx < len(adjuntos_disponibles):
                        adjuntos_seleccionados.append(adjuntos_disponibles[idx])
                except ValueError:
                    continue

    # Renderizar firma
    firma_html, imagenes_firma = engine.renderizar_firma(firma, variables)

    # Ensamblar HTML final
    html_final = engine.ensamblar_html(
        plantilla=plantilla,
        selecciones=selecciones,
        variables=variables,
        firma_html=firma_html,
        personalizados=personalizados,
    )

    # Validar placeholders obligatorios
    errores = engine.validar_html_final(html_final)
    if errores:
        print("\nERROR: Hay campos obligatorios sin rellenar:")
        for e in errores:
            print(f"  - {{{{{e}}}}}")
        sys.exit(1)

    # 8. Resumen
    print("\n" + "=" * 60)
    print("  RESUMEN")
    print("=" * 60)
    print(f"Plantilla: {plantilla['nombre']}")
    print(f"Asunto: {asunto}")
    print("Destinatarios:")
    for d in destinatarios:
        etiqueta = d["tipo"].upper()
        print(f"  [{etiqueta}] {d.get('nombre', '')} <{d['email']}> ({d.get('empresa', '')})")
    print("Bloques seleccionados:")
    for slot, indices in selecciones.items():
        nombres = [plantilla["campos"][slot][i - 1] for i in indices]
        print(f"  {slot}: {len(nombres)} item(s)")
    if adjuntos_seleccionados:
        print("Adjuntos:")
        for a in adjuntos_seleccionados:
            print(f"  - {a.name}")

    # 9. Previsualizacion en HTML temporal
    preview_path = utils.guardar_preview_temporal(
        html_final, f"preview_{plantilla['nombre']}"
    )
    print(f"\n[PREVIEW] Abriendo previsualizacion temporal: {preview_path}")
    utils.abrir_archivo(preview_path)

    confirmar = input("\n¿Generar correo .eml? (s/n): ").strip().lower()
    if confirmar != "s":
        print("Generacion cancelada.")
        # Borrar preview temporal si se cancela
        try:
            preview_path.unlink(missing_ok=True)
        except Exception:
            pass
        sys.exit(0)

    # 10. Generar .eml
    from_email = input(f"Remitente [{config.get('remitente_default', 'tu@correo.com')}]: ").strip()
    if not from_email:
        from_email = config.get("remitente_default", "tu@correo.com")

    ruta_eml = engine.generar_eml(
        destinatarios=destinatarios,
        asunto=asunto,
        html_final=html_final,
        from_email=from_email,
        adjuntos=adjuntos_seleccionados,
        imagenes_inline=imagenes_firma,
    )

    print(f"\n[OK] Correo generado: {ruta_eml}")

    # 11. Registrar en contactos de destinatarios principales
    for d in destinatarios:
        if d["tipo"] == "para":
            contacto = engine.cargar_contacto_por_email(d["email"])
            if contacto:
                engine.registrar_envio_en_contacto(contacto, ruta_eml)
                print(f"[OK] Registrado en {contacto['archivo']}")

    # 12. Abrir .eml
    utils.abrir_archivo(ruta_eml)

    # 13. Limpiar preview temporal tras generar
    try:
        preview_path.unlink(missing_ok=True)
        # Si la carpeta temporal queda vacia, intentar borrarla
        carpeta_preview = preview_path.parent
        if carpeta_preview.exists() and not any(carpeta_preview.iterdir()):
            carpeta_preview.rmdir()
    except Exception:
        pass


if __name__ == "__main__":
    main()
