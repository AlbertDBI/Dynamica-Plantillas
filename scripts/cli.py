"""
CLI interactivo manual para Dynamica Plantillas.

Flujo:
  1. Seleccionar o crear contacto.
  2. Validar/rellenar datos obligatorios (nombre, email, empresa).
  3. Seleccionar bloques de presentacion, cuerpo y despedida.
  4. Rellenar campos variables detectados en los bloques.
  5. Rellenar campo personalizado si aplica.
  6. Seleccionar adjuntos opcionales.
  7. Generar .eml y registrarlo en el historial del contacto.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Agregar la carpeta padre al path para importar engine
sys.path.insert(0, str(Path(__file__).resolve().parent))

import engine


def pedir_input(mensaje: str, obligatorio: bool = True) -> str:
    while True:
        valor = input(mensaje).strip()
        if valor or not obligatorio:
            return valor
        print("Este campo es obligatorio.")


def mostrar_opciones(titulo: str, opciones: list[dict]) -> dict | None:
    print(f"\n{titulo}")
    for idx, op in enumerate(opciones, start=1):
        print(f"  {idx}. {op['nombre']}")
    print("  0. Ninguno / Cancelar")
    while True:
        try:
            seleccion = int(input("Selecciona una opcion: "))
            if seleccion == 0:
                return None
            if 1 <= seleccion <= len(opciones):
                return opciones[seleccion - 1]
        except ValueError:
            pass
        print("Opcion no valida.")


def seleccionar_multiples(titulo: str, opciones: list[dict]) -> list[str]:
    """Permite seleccionar varios elementos por numero separados por comas."""
    print(f"\n{titulo}")
    for idx, op in enumerate(opciones, start=1):
        print(f"  {idx}. {op['nombre']}")
    print("  0. Ninguno")
    seleccion = input("Selecciona opciones separadas por comas (ej: 1,3): ").strip()
    if not seleccion or seleccion == "0":
        return []
    nombres: list[str] = []
    for item in seleccion.split(","):
        try:
            idx = int(item.strip()) - 1
            if 0 <= idx < len(opciones):
                nombres.append(opciones[idx]["nombre"])
        except ValueError:
            continue
    return nombres


def crear_o_seleccionar_contacto() -> dict:
    contactos = engine.listar_contactos()
    if contactos:
        print("\nContactos existentes:")
        for idx, c in enumerate(contactos, start=1):
            datos = c["datos"]
            print(
                f"  {idx}. {datos.get('nombre', 'Sin nombre')} - {datos.get('empresa', 'Sin empresa')} ({datos.get('email', 'Sin email')})"
            )
        print("  0. Crear nuevo contacto")
        while True:
            try:
                op = int(input("Selecciona un contacto: "))
                if op == 0:
                    break
                if 1 <= op <= len(contactos):
                    return contactos[op - 1]
            except ValueError:
                pass
            print("Opcion no valida.")
    else:
        print("\nNo hay contactos. Vamos a crear uno nuevo.")

    # Crear nuevo contacto
    nombre = pedir_input("Nombre del contacto: ")
    empresa = pedir_input("Empresa: ")
    email = pedir_input("Email: ")
    cc = pedir_input("CC (opcional): ", obligatorio=False)
    bcc = pedir_input("CCO (opcional): ", obligatorio=False)

    datos = {
        "nombre": nombre,
        "empresa": empresa,
        "email": email,
    }
    if cc:
        datos["cc"] = cc
    if bcc:
        datos["cco"] = bcc

    slug = engine.normalizar_slug(f"{nombre}_{empresa}")
    engine.guardar_contacto(slug, datos, "### Historial de correos\n")
    return engine.cargar_contacto(slug)


def validar_y_completar_contacto(contacto: dict) -> dict:
    datos = contacto["datos"].copy()
    print("\nValidando datos del contacto...")
    for campo in engine.CAMPOS_CONTACTO_OBLIGATORIOS:
        if not datos.get(campo):
            datos[campo] = pedir_input(f"{campo.capitalize()} (falta): ")
    # Guardar cambios si se relleno algo
    if datos != contacto["datos"]:
        engine.guardar_contacto(
            contacto["slug"], datos, contacto.get("historial", "### Historial de correos\n")
        )
    contacto = engine.cargar_contacto(contacto["slug"])
    return contacto


def recopilar_variables_detectadas(bloques_seleccionados: list[str], tipo: str, variables: dict) -> dict:
    """Detecta placeholders en los bloques seleccionados y pide valores si faltan."""
    campos_detectados: set[str] = set()
    for nombre in bloques_seleccionados:
        try:
            contenido = engine.cargar_bloque(tipo, nombre)
            campos_detectados.update(engine.detectar_campos_requeridos_html(contenido))
        except FileNotFoundError:
            continue

    # Eliminar campos que ya vienen del contacto o son especiales
    campos_faltantes = campos_detectados - set(variables.keys()) - {"PERSONALIZADO"}
    for campo in sorted(campos_faltantes):
        variables[campo] = pedir_input(f"Valor para '{{{{{campo}}}}}': ")
    return variables


def main() -> None:
    print("=" * 50)
    print("  Dynamica Plantillas - Generador de correos")
    print("=" * 50)

    # 1. Contacto
    contacto = crear_o_seleccionar_contacto()
    contacto = validar_y_completar_contacto(contacto)
    datos = contacto["datos"]

    variables_extra: dict[str, str] = {}

    # 2. Asunto
    asunto = input(f"Asunto del correo [Propuesta para {datos.get('empresa', '')}]: ").strip()
    if not asunto:
        asunto = f"Propuesta para {datos.get('empresa', '')}"

    # 3. Seleccion de bloques
    presentaciones = engine.listar_bloques("presentacion")
    cuerpos = engine.listar_bloques("cuerpo")
    despedidas = engine.listar_bloques("despedida")

    if not presentaciones or not cuerpos or not despedidas:
        print("\nERROR: No se encontraron bloques suficientes en la carpeta blocks/.")
        print("Crea al menos un bloque en presentacion/, cuerpo/ y despedida/.")
        sys.exit(1)

    pres = seleccionar_multiples("PRESENTACION (puedes elegir varias):", presentaciones)
    cuer = seleccionar_multiples("CUERPO (puedes elegir varias):", cuerpos)
    desped = seleccionar_multiples("DESPEDIDA (puedes elegir varias):", despedidas)

    if not pres or not cuer or not desped:
        print("Debes seleccionar al menos un bloque de cada seccion.")
        sys.exit(1)

    # 4. Detectar y rellenar variables adicionales de los bloques
    variables_base = {k: str(v) for k, v in datos.items() if v is not None}
    variables_extra = recopilar_variables_detectadas(pres, "presentacion", variables_base)
    variables_extra = recopilar_variables_detectadas(cuer, "cuerpo", variables_extra)
    variables_extra = recopilar_variables_detectadas(desped, "despedida", variables_extra)

    # 5. Campo personalizado
    campo_personalizado = ""
    if engine.MARCADOR_PERSONALIZADO in "\n".join(
        engine.cargar_bloque(t, n)
        for t, lista in [("presentacion", pres), ("cuerpo", cuer), ("despedida", desped)]
        for n in lista
    ):
        sugerencia = input("\nEl bloque contiene {{PERSONALIZADO}}. ¿Quieres que la IA te sugiera texto? (s/n): ").strip().lower()
        if sugerencia == "s":
            print("(En modo manual, escribe directamente el texto deseado)")
        campo_personalizado = pedir_input("Texto personalizado a insertar: ", obligatorio=False)

    # 6. Adjuntos
    adjuntos_disponibles = engine.listar_adjuntos()
    adjuntos_seleccionados: list[Path] = []
    if adjuntos_disponibles:
        print("\nAdjuntos disponibles:")
        for idx, a in enumerate(adjuntos_disponibles, start=1):
            print(f"  {idx}. {a.name}")
        print("  0. Ninguno")
        seleccion_adj = input("Selecciona adjuntos separados por comas: ").strip()
        if seleccion_adj and seleccion_adj != "0":
            for item in seleccion_adj.split(","):
                try:
                    idx = int(item.strip()) - 1
                    if 0 <= idx < len(adjuntos_disponibles):
                        adjuntos_seleccionados.append(adjuntos_disponibles[idx])
                except ValueError:
                    continue

    # 7. Generar
    cc = datos.get("cc", "")
    bcc = datos.get("cco", "")
    from_email = input(f"Remitente [{engine.msg_default_from()}]: ").strip()
    if not from_email:
        from_email = engine.msg_default_from()

    ruta_eml = engine.generar_eml(
        contacto=contacto,
        bloques_presentacion=pres,
        bloques_cuerpo=cuer,
        bloques_despedida=desped,
        asunto=asunto,
        variables_extra=variables_extra,
        adjuntos=adjuntos_seleccionados,
        campo_personalizado=campo_personalizado,
        from_email=from_email,
        cc=cc,
        bcc=bcc,
    )

    engine.registrar_envio_en_contacto(contacto, ruta_eml)
    print(f"\n[OK] Correo generado: {ruta_eml}")
    print(f"[OK] Registro anadido al historial de {contacto['archivo']}")


# Pequena utilidad: remitente por defecto para el CLI
if not hasattr(engine, "msg_default_from"):
    def msg_default_from():
        return "tu@correo.com"
    engine.msg_default_from = msg_default_from  # type: ignore[attr-defined]


if __name__ == "__main__":
    main()
