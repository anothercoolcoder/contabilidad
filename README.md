# Contabilidad local

Este proyecto implementa una base funcional para un sistema local de procesamiento contable conforme al contexto del proyecto descrito en el archivo de referencia.

## Alcance inicial

- Registro previo del usuario para garantizar trazabilidad por operario.
- Recepción de comprobantes desde WhatsApp como canal principal.
- Flujo de procesamiento con OCR y RAG en una capa local.
- Validación automática antes de persistir los datos.
- Persistencia local usando SQLite para una primera versión ejecutable sin dependencias complejas.

## Estructura

- `contabilidad/config.py`: configuración global del sistema.
- `contabilidad/db.py`: almacenamiento local en SQLite.
- `contabilidad/services/user_service.py`: registro y validación de usuarios.
- `contabilidad/services/ocr_service.py`: adaptador para OCR.
- `contabilidad/services/rag_service.py`: estructuración semántica de los documentos.
- `contabilidad/services/processor.py`: pipeline principal de procesamiento.
- `contabilidad/cli.py`: interfaz de línea de comandos para pruebas iniciales.
- `tests/test_core_flow.py`: pruebas del flujo principal.

## Uso rápido

1. Crear un usuario:
   `python3 -m contabilidad.cli register-user --name "Ana" --phone "+56912345678" --employee-id "EMP-001"`
2. Enviar un comprobante para procesamiento:
   `python3 -m contabilidad.cli submit-document --phone "+56912345678" --file-name "factura_acme.pdf" --raw-text "Factura - Proveedor ACME\nTotal: 125000"`

## Estado

Es un prototipo inicial orientado a validar los principios arquitectónicos y la lógica de negocio base antes de escalar a OCR local real, integración con WhatsApp, validación más estricta y almacenamiento de producción.
