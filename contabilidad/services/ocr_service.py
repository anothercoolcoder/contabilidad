from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_PDF_PAGES = 10
SUPPORTED_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".pdf", ".tif", ".tiff", ".webp"}
OCR_TIMEOUT_SECONDS = 60


class OCRConfigurationError(RuntimeError):
    """Raised when local OCR or PDF tools are not installed or configured."""


class DocumentReadError(ValueError):
    """Raised when an uploaded document cannot be read safely."""


class OCRService:
    """Extract text from local image and PDF files using Tesseract and Poppler."""

    def extract_text(self, file_name: str, raw_text: str = "") -> str:
        return raw_text.strip()

    def extract_file(self, file_name: str, content: bytes) -> str:
        suffix = Path(file_name).suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            raise DocumentReadError("Formato no compatible. Sube PDF, PNG, JPG, TIFF, BMP o WEBP.")
        if not content:
            raise DocumentReadError("El archivo está vacío.")
        if len(content) > MAX_FILE_SIZE:
            raise DocumentReadError("El archivo supera el límite de 10 MB.")
        self._validate_signature(suffix, content)

        with tempfile.TemporaryDirectory(prefix="contabilidad-ocr-") as directory:
            workdir = Path(directory)
            input_path = workdir / f"document{suffix}"
            input_path.write_bytes(content)
            if suffix == ".pdf":
                return self._extract_pdf(input_path, workdir)

            tesseract = self._require_tesseract()
            language = self._tesseract_language(tesseract)
            return self._run_tesseract(tesseract, input_path, language, file_name)

    def _require_tesseract(self) -> str:
        tesseract = shutil.which("tesseract")
        if not tesseract:
            raise OCRConfigurationError(
                "No se encontró Tesseract. Instala Tesseract OCR y el paquete de idioma español."
            )
        return tesseract

    def _tesseract_language(self, tesseract: str) -> str:
        try:
            result = subprocess.run(
                [tesseract, "--list-langs"],
                check=True,
                capture_output=True,
                text=True,
                timeout=OCR_TIMEOUT_SECONDS,
            )
        except FileNotFoundError as error:
            raise OCRConfigurationError("No se pudo ejecutar Tesseract.") from error
        except subprocess.CalledProcessError as error:
            details = error.stderr.strip() or "sin detalle"
            raise OCRConfigurationError(f"Tesseract no pudo listar sus idiomas: {details}") from error
        except subprocess.TimeoutExpired as error:
            raise OCRConfigurationError("Tesseract tardó demasiado al consultar los idiomas.") from error

        languages = set(result.stdout.splitlines())
        if "spa" not in languages:
            raise OCRConfigurationError(
                "Tesseract está instalado, pero falta el idioma español (spa). Instala tesseract-langpack-spa."
            )
        return "spa+eng" if "eng" in languages else "spa"

    def _extract_pdf(self, input_path: Path, workdir: Path) -> str:
        pdftotext = shutil.which("pdftotext")
        if pdftotext:
            try:
                result = subprocess.run(
                    [pdftotext, "-f", "1", "-l", str(MAX_PDF_PAGES), "-layout", str(input_path), "-"],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=OCR_TIMEOUT_SECONDS,
                )
            except FileNotFoundError as error:
                raise OCRConfigurationError("No se pudo ejecutar pdftotext.") from error
            except subprocess.CalledProcessError as error:
                details = error.stderr.decode("utf-8", errors="replace").strip() if isinstance(error.stderr, bytes) else (error.stderr or "").strip()
                raise DocumentReadError(f"No se pudo leer el PDF: {details or 'archivo dañado o inválido.'}") from error
            except subprocess.TimeoutExpired as error:
                raise DocumentReadError("La lectura del PDF superó el tiempo máximo permitido.") from error
            if result.stdout.strip():
                return result.stdout.strip()

        tesseract = self._require_tesseract()
        language = self._tesseract_language(tesseract)
        pdftoppm = shutil.which("pdftoppm")
        if not pdftoppm:
            raise OCRConfigurationError(
                "Para leer PDF instala Poppler (pdftotext y pdftoppm) además de Tesseract."
            )

        prefix = workdir / "page"
        try:
            subprocess.run(
                [
                    pdftoppm, "-f", "1", "-l", str(MAX_PDF_PAGES),
                    "-r", "180", "-png", str(input_path), str(prefix),
                ],
                check=True,
                capture_output=True,
                timeout=OCR_TIMEOUT_SECONDS,
            )
        except FileNotFoundError as error:
            raise OCRConfigurationError("No se pudo ejecutar pdftoppm.") from error
        except subprocess.CalledProcessError as error:
            details = error.stderr.decode("utf-8", errors="replace").strip() if isinstance(error.stderr, bytes) else (error.stderr or "").strip()
            raise DocumentReadError(f"No se pudo convertir el PDF: {details or 'archivo dañado o inválido.'}") from error
        except subprocess.TimeoutExpired as error:
            raise DocumentReadError("La conversión del PDF superó el tiempo máximo permitido.") from error

        pages = sorted(workdir.glob("page-*.png"))
        if not pages:
            raise DocumentReadError("El PDF no contiene páginas legibles.")
        text = [
            self._run_tesseract(tesseract, page, language, page.name)
            for page in pages[:MAX_PDF_PAGES]
        ]
        return "\n\n".join(page_text for page_text in text if page_text).strip()

    def _run_tesseract(self, tesseract: str, input_path: Path, language: str, file_name: str) -> str:
        try:
            result = subprocess.run(
                [tesseract, str(input_path), "stdout", "-l", language, "--psm", "6"],
                check=True,
                capture_output=True,
                text=True,
                timeout=OCR_TIMEOUT_SECONDS,
            )
        except FileNotFoundError as error:
            raise OCRConfigurationError("No se pudo ejecutar Tesseract.") from error
        except subprocess.CalledProcessError as error:
            details = error.stderr.strip() or "sin detalle"
            raise DocumentReadError(f"Tesseract no pudo leer {file_name}: {details}") from error
        except subprocess.TimeoutExpired as error:
            raise DocumentReadError(f"La lectura de {file_name} superó el tiempo máximo permitido.") from error
        return result.stdout.strip()

    def _validate_signature(self, suffix: str, content: bytes) -> None:
        valid = {
            ".pdf": b"%PDF-" in content[:1024],
            ".png": content.startswith(b"\x89PNG\r\n\x1a\n"),
            ".jpg": content.startswith(b"\xff\xd8\xff"),
            ".jpeg": content.startswith(b"\xff\xd8\xff"),
            ".bmp": content.startswith(b"BM"),
            ".tif": content.startswith((b"II*\x00", b"MM\x00*")),
            ".tiff": content.startswith((b"II*\x00", b"MM\x00*")),
            ".webp": len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP",
        }[suffix]
        if not valid:
            raise DocumentReadError("El contenido no coincide con el formato indicado o el archivo está dañado.")
