from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

from contabilidad.services.ocr_service import (
    DocumentReadError,
    OCRConfigurationError,
    OCRService,
)


def test_image_ocr_uses_local_tesseract():
    image = b"\x89PNG\r\n\x1a\n" + b"test-image"

    def run(command, **kwargs):
        if command[1:] == ["--list-langs"]:
            return CompletedProcess(command, 0, "List of available languages:\neng\nspa\n", "")
        return CompletedProcess(command, 0, "Factura\nTotal: 125000", "")

    with patch("contabilidad.services.ocr_service.shutil.which", return_value="/usr/bin/tesseract"), patch(
        "contabilidad.services.ocr_service.subprocess.run", side_effect=run
    ) as run_process:
        text = OCRService().extract_file("factura.png", image)

    assert text == "Factura\nTotal: 125000"
    assert run_process.call_count == 2
    assert run_process.call_args.args[0][-2:] == ["--psm", "6"]


def test_pdf_uses_embedded_text_before_page_ocr():
    pdf = b"%PDF-1.7\nfake pdf"

    def run(command, **kwargs):
        if command[1:] == ["--list-langs"]:
            return CompletedProcess(command, 0, "eng\nspa\n", "")
        return CompletedProcess(command, 0, "Factura ACME\nTotal 125000\n", "")

    def find_tool(name):
        return f"/usr/bin/{name}" if name == "pdftotext" else None

    with patch("contabilidad.services.ocr_service.shutil.which", side_effect=find_tool), patch(
        "contabilidad.services.ocr_service.subprocess.run", side_effect=run
    ) as run_process:
        text = OCRService().extract_file("factura.pdf", pdf)

    assert text == "Factura ACME\nTotal 125000"
    assert run_process.call_count == 1
    assert run_process.call_args.args[0][0] == "/usr/bin/pdftotext"


def test_scanned_pdf_renders_pages_and_applies_ocr():
    pdf = b"%PDF-1.7\nscanned pdf"

    def run(command, **kwargs):
        if command[1:] == ["--list-langs"]:
            return CompletedProcess(command, 0, "spa\n", "")
        if command[0] == "/usr/bin/pdftotext":
            return CompletedProcess(command, 0, "\n", "")
        if command[0] == "/usr/bin/pdftoppm":
            Path(f"{command[-1]}-1.png").write_bytes(b"\x89PNG\r\n\x1a\npage")
            return CompletedProcess(command, 0, b"", b"")
        return CompletedProcess(command, 0, "Boleta\nTotal: 50000", "")

    def find_tool(name):
        return f"/usr/bin/{name}" if name in {"tesseract", "pdftotext", "pdftoppm"} else None

    with patch("contabilidad.services.ocr_service.shutil.which", side_effect=find_tool), patch(
        "contabilidad.services.ocr_service.subprocess.run", side_effect=run
    ):
        text = OCRService().extract_file("boleta.pdf", pdf)

    assert text == "Boleta\nTotal: 50000"


@pytest.mark.parametrize(
    ("name", "content", "message"),
    [
        ("factura.exe", b"MZinvalid", "Formato no compatible"),
        ("factura.png", b"not a png", "no coincide"),
        ("factura.pdf", b"%PDF-1.7", "No se encontró Tesseract"),
    ],
)
def test_ocr_rejects_invalid_files_and_reports_missing_engine(name, content, message):
    with patch("contabilidad.services.ocr_service.shutil.which", return_value=None):
        if message == "No se encontró Tesseract":
            with pytest.raises(OCRConfigurationError, match=message):
                OCRService().extract_file(name, content)
        else:
            with pytest.raises(DocumentReadError, match=message):
                OCRService().extract_file(name, content)


def test_ocr_rejects_files_over_limit():
    with pytest.raises(DocumentReadError, match="10 MB"):
        OCRService().extract_file("factura.png", b"\x89PNG\r\n\x1a\n" + b"x" * (10 * 1024 * 1024))
