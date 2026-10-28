# Contabilidad local

Este proyecto es un prototipo funcional de un sistema local de procesamiento contable. La idea es validar el flujo base de:

- registro previo del usuario,
- recepción de comprobantes,
- OCR local simple,
- estructuración semántica con reglas básicas,
- validación mínima antes de guardar,
- persistencia local en SQLite.

## Requisitos

- Python 3.10+
- Git
- Tesseract OCR con idioma español (`spa`)
- Poppler (`pdftotext` y `pdftoppm`) para procesar PDFs

## Ejecutar desde local

Desde la raíz del proyecto:

```bash
cd /ruta/al/proyecto/contabilidad
sudo dnf install tesseract tesseract-langpack-spa poppler-utils
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

En Debian o Ubuntu, instala los equivalentes:

```bash
sudo apt install tesseract-ocr tesseract-ocr-spa poppler-utils
```

Si quieres usar el proyecto directamente desde el código fuente, no hace falta instalar el paquete en editable; este repositorio ya soporta la ejecución con:

```bash
python3 -m contabilidad --help
```

## Interfaz gráfica local

Inicia el panel desde la raíz del proyecto:

```bash
python3 -m contabilidad gui
```

Abre en el navegador la dirección que aparece en la terminal, por defecto:

```text
http://127.0.0.1:8765
```

Desde el panel puedes registrar usuarios, subir una imagen o PDF, leer el texto reconocido por OCR y revisar los datos extraídos y guardados. La interfaz solo escucha en `127.0.0.1`, por lo que no queda publicada para otros equipos de la red. Detén el servidor con `Ctrl+C`.

Para probar un archivo:

1. Registra primero el usuario que se asociará al comprobante.
2. Selecciónalo en el formulario de procesamiento.
3. Elige un PDF o imagen (PNG, JPG, TIFF, BMP o WEBP) de hasta 10 MB.
4. Pulsa **Leer y procesar**. Se mostrará el tipo, proveedor, total, nivel de confianza y el texto OCR completo.

Los PDF con texto seleccionable se leen directamente; los escaneados se convierten a imágenes para aplicar OCR. Se procesan hasta 10 páginas por PDF. Si el OCR no encuentra texto, el resultado queda sujeto a revisión en vez de inventar datos. También puedes seguir pegando texto manualmente para probar las reglas de extracción.

Si aparece un error indicando que falta Tesseract o el idioma español, verifica la instalación con `tesseract --list-langs`; debe aparecer `spa`. Para PDF escaneado, también se requieren `pdftotext` y `pdftoppm`. La interfaz es para administración y pruebas locales; WhatsApp continúa siendo el canal previsto para los usuarios de campo.

Para elegir otra base SQLite:

```bash
python3 -m contabilidad --db /tmp/contabilidad-prueba.db gui
```

## Flujo de prueba por línea de comandos

### 1) Registrar un usuario

```bash
python3 -m contabilidad register-user --name "Ana" --phone "+56912345678" --employee-id "EMP-001"
```

### 2) Enviar un comprobante

```bash
python3 -m contabilidad submit-document \
  --phone "+56912345678" \
  --file-name "factura_acme.pdf" \
  --raw-text "Factura - Proveedor ACME
Total: 125000
RUT: 76.123.456-0"
```

### 3) Revisar usuarios registrados

```bash
python3 -m contabilidad list-users
```

### 4) Revisar comprobantes almacenados

```bash
python3 -m contabilidad list-documents
```

### 5) Ejecutar pruebas automáticas

```bash
pytest -q
```

## Base de datos local

La base de datos se guarda por defecto en:

```text
data/accounting_local.db
```

Puedes apuntar a otra base con:

```bash
python3 -m contabilidad --db /tmp/mi_db.sqlite register-user --name "Ana" --phone "+56912345678" --employee-id "EMP-001"
```

## Qué validará esta prueba

Con la ejecución anterior puedes comprobar que el flujo base funciona:

- El usuario se registra correctamente.
- El documento se acepta cuando el usuario está autorizado.
- El sistema reconoce proveedor y total con reglas simples.
- El comprobante queda persistido en SQLite.
- Un usuario no registrado es rechazado.

## Estado actual del proyecto

Este repositorio corresponde a un prototipo funcional de validación de arquitectura y lógica base. Aun no incluye:

- integración real con WhatsApp,
- validación contable avanzada,
- RAG real con recuperación contextual,
- política de seguridad, auditoría y retención robusta.

La interfaz gráfica local admite lectura de imágenes y PDFs mediante Tesseract y Poppler, pero no sustituye los componentes anteriores que siguen pendientes.
