from __future__ import annotations


class OCRService:
    """Placeholder OCR adapter. The real implementation can be swapped for a local OCR engine later."""

    def extract_text(self, file_name: str, raw_text: str = "") -> str:
        if raw_text and raw_text.strip():
            return raw_text.strip()
        if file_name:
            return f"[OCR placeholder]: {file_name}"
        return ""
