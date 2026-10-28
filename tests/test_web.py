import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from contabilidad.services.ocr_service import OCRService
from contabilidad.web import create_server


def _request(server, method, path, payload=None, headers=None):
    response_data = {}

    def send():
        if isinstance(payload, bytes):
            body = payload
        else:
            body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request_headers = dict(headers or {})
        if body is not None and "Content-Type" not in request_headers:
            request_headers["Content-Type"] = "application/json"
        request = Request(
            f"http://127.0.0.1:{server.server_port}{path}",
            data=body,
            headers=request_headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=3) as response:
                response_data["status"] = response.status
                response_data["body"] = response.read()
        except HTTPError as error:
            response_data["status"] = error.code
            response_data["body"] = error.read()

    client = threading.Thread(target=send)
    client.start()
    server.handle_request()
    client.join(timeout=3)
    assert not client.is_alive()
    return response_data["status"], response_data["body"]


def test_local_web_interface_registers_and_processes_document():
    server = create_server(database_path=":memory:", port=0)
    server.timeout = 3
    try:
        status, page = _request(server, "GET", "/")
        assert status == 200
        assert b"Contabilidad local" in page

        status, body = _request(
            server,
            "POST",
            "/api/users",
            {"name": "Ana", "phone": "+56912345678", "employee_id": "EMP-001"},
        )
        assert status == 201
        user = json.loads(body)["user"]
        assert user["phone"] == "+56912345678"

        status, body = _request(
            server,
            "POST",
            "/api/documents",
            {
                "phone": "+56912345678",
                "file_name": "factura_acme.pdf",
                "raw_text": "Factura\nProveedor: ACME\nTotal: 125000",
            },
        )
        assert status == 201
        result = json.loads(body)
        assert result["status"] == "processed"
        assert result["extracted_fields"]["total"] == 125000.0

        status, body = _request(server, "GET", "/api/documents")
        assert status == 200
        assert len(json.loads(body)["documents"]) == 1
    finally:
        server.server_close()


def test_local_web_interface_rejects_unregistered_sender():
    server = create_server(database_path=":memory:", port=0)
    server.timeout = 3
    try:
        status, body = _request(
            server,
            "POST",
            "/api/documents",
            {
                "phone": "+56999999999",
                "file_name": "boleta.txt",
                "raw_text": "Boleta\nTotal: 50000",
            },
        )
        assert status == 400
        assert "debe estar registrado" in json.loads(body)["error"]
    finally:
        server.server_close()


def test_local_web_interface_uploads_image_and_returns_ocr_text():
    server = create_server(database_path=":memory:", port=0)
    server.timeout = 3
    boundary = "local-test-boundary"
    image = b"\x89PNG\r\n\x1a\n" + b"test-image-bytes"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="phone"\r\n\r\n'
        "+56912345678\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="factura.png"\r\n'
        "Content-Type: image/png\r\n\r\n"
    ).encode() + image + f"\r\n--{boundary}--\r\n".encode()

    try:
        status, _ = _request(
            server,
            "POST",
            "/api/users",
            {"name": "Ana", "phone": "+56912345678", "employee_id": "EMP-001"},
        )
        assert status == 201

        with patch.object(OCRService, "extract_file", return_value="Factura\nProveedor: ACME\nTotal: 125000") as extract:
            status, response_body = _request(
                server,
                "POST",
                "/api/documents/upload",
                body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            )

        assert status == 201
        result = json.loads(response_body)
        assert result["status"] == "processed"
        assert result["ocr_text"] == "Factura\nProveedor: ACME\nTotal: 125000"
        extract.assert_called_once_with("factura.png", image)
    finally:
        server.server_close()
