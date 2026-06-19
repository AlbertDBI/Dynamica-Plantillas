# Dynamica Plantillas

Generador determinista de correos electrónicos en formato `.eml` a partir de plantillas modulares.

## ¿Qué hace?

Dynamica Plantillas permite crear correos electrónicos profesionales de forma rápida y controlada:

- Las plantillas se definen con un archivo `diseno.html` y un archivo `campos.md`.
- Se seleccionan bloques de contenido por sección (`saludo`, `cuerpo`, `despedida`, `firma`, etc.).
- Se pueden añadir varios bloques por sección, cambiar su orden o eliminarlos.
- Se genera un archivo `.eml` listo para abrir en Outlook, Himalaya o cualquier cliente de correo.
- Cada correo generado queda registrado en el historial del contacto.

## Instalación

```bash
# Clonar el repositorio
git clone https://github.com/AlbertDBI/Dynamica-Plantillas.git
cd Dynamica-Plantillas

# Crear entorno virtual (Windows)
python -m venv .venv
.venv\Scripts\Activate.ps1

# Instalar dependencias
pip install -r requirements.txt
```

## Uso

```bash
.venv\Scripts\Activate.ps1
python scripts/cli.py
```

Sigue los pasos interactivos:

1. Selecciona plantilla.
2. Selecciona firma (o ninguna).
3. Introduce destinatario(s), CC y CCO.
4. Selecciona o edita el asunto.
5. Arma cada sección con multiselección y orden.
6. Rellena campos personalizados si aplica.
7. Selecciona adjuntos.
8. Previsualiza el correo en el navegador.
9. Genera el `.eml` y se abre en tu cliente de correo.

## Estructura de una plantilla

Cada plantilla es una carpeta dentro de `templates/`:

```
templates/mi_plantilla/
├── campos.md               # Opciones de cada sección y asuntos
├── diseno.html             # Maqueta con slots {{saludo}}, {{cuerpo}}, etc.
├── texto_obligatorio.md    # Cláusulas legales o textos fijos
└── adjuntos/               # Archivos adjuntos disponibles
```

### Ejemplo de `campos.md`

```markdown
## asuntos
- Propuesta para {{empresa}}
- Seguimiento con {{nombre}} de {{empresa}}

## saludo
- Buenas tardes {{nombre}}, de {{empresa}}
- Buenos días encargado de {{empresa}}

## cuerpo
- Le envío la propuesta actualizada.
- Adjunto el catálogo de productos.

## despedida
- Quedo a su disposición.
- Un saludo cordial.

## firma
- El equipo comercial
- Atentamente,
```

### Ejemplo de `diseno.html`

```html
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; color: #333;">
  <div style="max-width: 600px; margin: auto;">
    {{saludo}}
    {{cuerpo}}
    {{personalizado}}
    {{despedida}}
    {{firma}}
    {{texto_obligatorio}}
  </div>
</body>
</html>
```

## Slots disponibles

El motor detecta automáticamente cualquier slot del tipo `{{nombre_slot}}` en `diseno.html`.

Slots especiales:

- `{{firma}}`: se rellena con la firma seleccionada desde `signatures/`.
- `{{texto_obligatorio}}`: se rellena con `texto_obligatorio.md` o `.html`.
- `{{personalizado}}` y `{{personalizado_N}}`: campos de texto libre.
- `{{personalizado_obligatorio}}`: campo personalizado que no se puede dejar vacío.

## Firmas

Las firmas se guardan en `signatures/` como archivos `.md` con frontmatter:

```markdown
---
nombre: Empresa Demo
email: contacto@empresademo.com
telefono: "+34 600 123 456"
web: https://www.empresademo.com
logo: adjuntos/logo_demo.png
---

<p>
  <strong>{{nombre}}</strong><br>
  <a href="mailto:{{email}}">{{email}}</a> |
  <a href="tel:{{telefono}}">{{telefono}}</a><br>
  <a href="{{web}}">{{web}}</a>
</p>
```

Las imágenes locales se adjuntan inline automáticamente para mejor compatibilidad con Outlook.

## Configuración

Edita `config.yaml`:

```yaml
remitente_default: "tu@correo.com"
firma_default: "empresa_demo"
output:
  modo: "dias"      # guardar | dias | no_mantener
  dias: 30
```

- `guardar`: nunca borra los archivos generados en `output/`.
- `dias`: borra archivos `.eml` y `.html` más antiguos que los días indicados.
- `no_mantener`: vacía `output/` al iniciar el programa.

## CSS inline admitido

El `diseno.html` soporta cualquier propiedad CSS inline estándar:

- `font-family`, `font-size`, `color`, `line-height`
- `text-align`: `left`, `right`, `center`, `justify`
- `margin`, `padding`, `border`
- `background-color`
- `width`, `max-width`

Se recomienda usar tablas (`<table>`) para compatibilidad con Outlook.

## Contactos

Los contactos se guardan en `contacts/` como archivos `.md` con frontmatter:

```markdown
---
nombre: Albert Casanova
email: albert@tips4tics.com
empresa: Tips4Tics
---

### Historial de correos
- [2026-06-19] [Tips4Tics_20260619_120000.eml](Tips4Tics_20260619_120000.eml)
```

## Notas

- El programa no envía correos. Solo genera archivos `.eml` para que el usuario los revise y envíe desde su cliente de correo.
- La lógica es determinista: la IA no improvisa contenido; solo el usuario selecciona y el motor ensambla.

## Licencia

Uso interno. Pendiente de definir.
