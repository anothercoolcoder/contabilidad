from __future__ import annotations

import json
import logging
import sqlite3
from email import policy
from email.parser import BytesParser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from contabilidad.config import DEFAULT_DB_PATH
from contabilidad.db import LocalDatabase
from contabilidad.services.ocr_service import (
    MAX_FILE_SIZE,
    OCRConfigurationError,
)
from contabilidad.services.processor import ProcessingPipeline
from contabilidad.services.user_service import UserService

LOGGER = logging.getLogger(__name__)
MAX_REQUEST_SIZE = 1_000_000
MAX_UPLOAD_REQUEST_SIZE = MAX_FILE_SIZE + 128 * 1024
PAGE_PATH = Path(__file__).parent / "static" / "index.html"


class LocalHTTPServer(HTTPServer):
    def __init__(self, server_address, request_handler, database: LocalDatabase):
        self.database = database
        super().__init__(server_address, request_handler)

    def server_close(self) -> None:
        super().server_close()
        self.database.close()


def create_server(
    database_path: str | Path = DEFAULT_DB_PATH,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> HTTPServer:
    if host != "127.0.0.1":
        raise ValueError("La interfaz solo puede enlazarse a 127.0.0.1.")
    if not 0 <= port <= 65535:
        raise ValueError("El puerto debe estar entre 0 y 65535.")

    database = LocalDatabase(database_path)
    user_service = UserService(database)
    pipeline = ProcessingPipeline(database)

    class LocalRequestHandler(BaseHTTPRequestHandler):
        server_version = "ContabilidadLocal/0.1"

        def do_GET(self) -> None:
            if self.path == "/" or self.path == "/index.html":
                try:
                    page = PAGE_PATH.read_bytes()
                except OSError as error:
                    LOGGER.exception("No se pudo leer la interfaz local.")
                    self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "No se pudo cargar la interfaz."})
                    return

                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(page)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; object-src 'none'; frame-ancestors 'none'")
                self.end_headers()
                self.wfile.write(page)
                return

            if self.path == "/api/users":
                self._send_json(HTTPStatus.OK, {"users": database.list_users()})
                return

            if self.path == "/api/documents":
                self._send_json(HTTPStatus.OK, {"documents": database.list_documents()})
                return

            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Ruta no encontrada."})

        def do_POST(self) -> None:
            if self.path not in {"/api/users", "/api/documents", "/api/documents/upload"}:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Ruta no encontrada."})
                return
            if not self._is_local_request():
                self._send_json(HTTPStatus.FORBIDDEN, {"error": "Solicitud local no válida."})
                return

            try:
                if self.path == "/api/users":
                    payload = self._read_json()
                    if payload is None:
                        return
                    user = user_service.register_user(
                        self._required_string(payload, "name"),
                        self._required_string(payload, "phone"),
                        self._required_string(payload, "employee_id"),
                    )
                    self._send_json(HTTPStatus.CREATED, {"user": user})
                    return

                if self.path == "/api/documents/upload":
                    phone, file_name, content = self._read_upload()
                    if phone is None:
                        return
                    if database.get_user_by_phone(phone) is None:
                        raise ValueError("El usuario debe estar registrado antes de enviar comprobantes.")
                    raw_text = pipeline.ocr.extract_file(file_name, content)
                    result = pipeline.process_document(
                        user_phone=phone,
                        file_name=file_name,
                        raw_text=raw_text,
                        source="local_web",
                    )
                    result["ocr_text"] = raw_text
                    self._send_json(HTTPStatus.CREATED, result)
                    return

                payload = self._read_json()
                if payload is None:
                    return
                result = pipeline.process_document(
                    user_phone=self._required_string(payload, "phone"),
                    file_name=self._required_string(payload, "file_name"),
                    raw_text=self._required_string(payload, "raw_text"),
                    source="local_web",
                )
                self._send_json(HTTPStatus.CREATED, result)
            except OCRConfigurationError as error:
                LOGGER.error("El motor local de OCR no está listo: %s", error)
                self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(error)})
            except ValueError as error:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            except sqlite3.IntegrityError as error:
                LOGGER.info("La solicitud no pasó una restricción de integridad: %s", error)
                self._send_json(HTTPStatus.CONFLICT, {"error": "El registro ya existe o no es válido."})
            except sqlite3.Error:
                LOGGER.exception("Error de base de datos durante una solicitud de la interfaz.")
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "Error al guardar o consultar los datos."})

        def log_message(self, format: str, *args: Any) -> None:
            LOGGER.info("%s - %s", self.address_string(), format % args)

        def _is_local_request(self) -> bool:
            expected_host = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get("Host") not in {expected_host, f"localhost:{self.server.server_port}"}:
                return False

            origin = self.headers.get("Origin")
            return origin is None or origin in {
                f"http://127.0.0.1:{self.server.server_port}",
                f"http://localhost:{self.server.server_port}",
            }

        def _read_json(self) -> dict[str, Any] | None:
            content_type = self.headers.get("Content-Type", "").split(";", maxsplit=1)[0].strip().lower()
            if content_type != "application/json":
                self._send_json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "Se requiere Content-Type application/json."})
                return None

            try:
                content_length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Longitud de solicitud no válida."})
                return None

            if content_length <= 0:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "El cuerpo de la solicitud está vacío."})
                return None
            if content_length > MAX_REQUEST_SIZE:
                self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "La solicitud supera el tamaño permitido."})
                return None

            try:
                payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "El cuerpo debe contener JSON UTF-8 válido."})
                return None

            if not isinstance(payload, dict):
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "El cuerpo JSON debe ser un objeto."})
                return None
            return payload

        def _read_upload(self) -> tuple[str | None, str | None, bytes | None]:
            content_type = self.headers.get("Content-Type", "")
            if not content_type.lower().startswith("multipart/form-data;"):
                self._send_json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "La subida requiere multipart/form-data."})
                return None, None, None

            try:
                content_length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Longitud de solicitud no válida."})
                return None, None, None
            if content_length <= 0:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "La subida está vacía."})
                return None, None, None
            if content_length > MAX_UPLOAD_REQUEST_SIZE:
                self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "El archivo supera el límite de 10 MB."})
                return None, None, None

            body = self.rfile.read(content_length)
            message = BytesParser(policy=policy.default).parsebytes(
                f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("ascii") + body
            )
            if not message.is_multipart():
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "El formulario de subida no es válido."})
                return None, None, None

            fields: dict[str, str] = {}
            uploaded_file: tuple[str, bytes] | None = None
            for part in message.iter_parts():
                name = part.get_param("name", header="content-disposition")
                if name == "file":
                    filename = part.get_filename()
                    content = part.get_payload(decode=True) or b""
                    if not filename or uploaded_file is not None:
                        self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Selecciona un único archivo."})
                        return None, None, None
                    safe_name = Path(filename.replace("\\", "/")).name
                    uploaded_file = safe_name, content
                elif name in {"phone"}:
                    value = part.get_payload(decode=True) or b""
                    try:
                        fields[name] = value.decode("utf-8").strip()
                    except UnicodeDecodeError:
                        self._send_json(HTTPStatus.BAD_REQUEST, {"error": "El formulario contiene texto no válido."})
                        return None, None, None

            if uploaded_file is None:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Selecciona una imagen o un PDF para procesar."})
                return None, None, None
            if not fields.get("phone"):
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "El campo 'phone' es obligatorio."})
                return None, None, None
            if len(uploaded_file[1]) > MAX_FILE_SIZE:
                self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "El archivo supera el límite de 10 MB."})
                return None, None, None
            return fields["phone"], uploaded_file[0], uploaded_file[1]

        def _required_string(self, payload: dict[str, Any], key: str) -> str:
            value = payload.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"El campo '{key}' es obligatorio.")
            return value

        def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

    return LocalHTTPServer((host, port), LocalRequestHandler, database)


def run_server(database_path: str | Path = DEFAULT_DB_PATH, port: int = 8765) -> None:
    server = create_server(database_path=database_path, port=port)
    address, actual_port = server.server_address
    print(f"Interfaz local disponible en http://{address}:{actual_port}")
    print("Para detenerla, presiona Ctrl+C.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nCerrando la interfaz local.")
    finally:
        server.server_close()
