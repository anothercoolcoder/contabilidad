from __future__ import annotations

import re
from typing import Any, Dict


class RAGService:
    """Minimal semantic structuring layer for the initial project prototype."""

    def structure(self, raw_text: str) -> Dict[str, Any]:
        text = raw_text or ""
        normalized = text.strip()

        document_type = self._detect_document_type(normalized)
        vendor = self._extract_vendor(normalized)
        total = self._extract_total(normalized)
        currency = self._detect_currency(normalized)
        confidence = self._estimate_confidence(document_type, vendor, total)

        return {
            "document_type": document_type,
            "vendor": vendor,
            "total": total,
            "currency": currency,
            "confidence": confidence,
        }

    def _detect_document_type(self, text: str) -> str:
        lowered = text.lower()
        mapping = {
            "factura": ["factura", "invoice"],
            "boleta": ["boleta", "ticket"],
            "guia": ["guia de despacho", "guia", "dispatch"],
            "nc": ["nota de credito", "nota crédito", "nc"],
            "nd": ["nota de debito", "nota débito", "nd"],
        }
        for key, values in mapping.items():
            if any(value in lowered for value in values):
                return key
        return "otro"

    def _extract_vendor(self, text: str) -> str:
        patterns = [
            r"(?:proveedor|razon social|emitido por|empresa)\s*[:\-]?\s*([^\n]+)",
            r"(?:vendor|supplier)\s*[:\-]?\s*([^\n]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                cleaned = match.group(1).strip()
                if cleaned and cleaned.lower() not in {"-", ":"}:
                    normalized = cleaned
                    label = match.group(0).strip().split()[0].lower()
                    if label in {"proveedor"}:
                        return f"Proveedor {normalized}"
                    if label in {"razon", "razón"}:
                        return f"Razón social {normalized}"
                    return normalized
        return "desconocido"

    def _extract_total(self, text: str) -> float | None:
        patterns = [
            r"(?:total|monto total|valor total)\s*[:\-]?\s*\$?\s*([0-9][0-9.,]*)",
            r"(?:total|monto total|valor total)\s*[:\-]?\s*([0-9]{1,3}(?:[.,][0-9]{3})*(?:[.,][0-9]{2})?)",
            r"(?:total|monto total|valor total)\s*[:\-]?\s*([0-9]+(?:[.,][0-9]{2})?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                candidate = match.group(1).strip().rstrip(".")
                if not candidate:
                    continue
                cleaned = candidate.replace(".", "").replace(",", ".")
                try:
                    return float(cleaned)
                except ValueError:
                    continue
        return None

    def _detect_currency(self, text: str) -> str:
        lowered = text.lower()
        if "usd" in lowered or "$" in lowered:
            return "USD"
        if "clp" in lowered or "pesos" in lowered:
            return "CLP"
        return "CLP"

    def _estimate_confidence(self, document_type: str, vendor: str, total: float | None) -> float:
        score = 0.35
        if document_type != "otro":
            score += 0.25
        if vendor and vendor != "desconocido":
            score += 0.20
        if total is not None:
            score += 0.20
        return round(min(score, 1.0), 2)
