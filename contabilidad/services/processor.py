from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from contabilidad.config import REVIEW_CONFIDENCE_THRESHOLD
from contabilidad.db import LocalDatabase
from contabilidad.services.ocr_service import OCRService
from contabilidad.services.rag_service import RAGService


class ProcessingPipeline:
    def __init__(self, database: LocalDatabase):
        self.database = database
        self.ocr = OCRService()
        self.rag = RAGService()

    def process_document(
        self,
        user_phone: str,
        file_name: str,
        raw_text: str,
        source: str = "whatsapp",
    ) -> dict:
        user = self.database.get_user_by_phone(user_phone)
        if user is None:
            raise ValueError("El usuario debe estar registrado antes de enviar comprobantes.")

        extracted_text = self.ocr.extract_text(file_name=file_name, raw_text=raw_text)
        structured = self.rag.structure(extracted_text)
        decision, notes = self.validate(structured)

        document_id = str(uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        processed_at = datetime.now(timezone.utc).isoformat() if decision == "processed" else None

        payload = self.database.create_document(
            document_id=document_id,
            user_id=user["user_id"],
            source=source,
            file_name=file_name,
            raw_text=extracted_text,
            status=decision,
            extracted_fields=structured,
            validation_notes=notes,
            created_at=created_at,
            processed_at=processed_at,
        )

        return {
            "document_id": payload["document_id"],
            "user_id": payload["user_id"],
            "status": payload["status"],
            "extracted_fields": payload["extracted_fields"],
            "validation_notes": payload["validation_notes"],
            "confidence": payload["extracted_fields"].get("confidence", 0.0),
        }

    def validate(self, structured: dict) -> tuple[str, list[str]]:
        notes: list[str] = []
        if structured.get("vendor") in {None, "desconocido"}:
            notes.append("Proveedor no identificado con suficiente confianza.")
        if structured.get("total") is None:
            notes.append("Monto total ausente o no reconocido.")
        if structured.get("confidence", 0.0) < REVIEW_CONFIDENCE_THRESHOLD:
            notes.append("Confianza por debajo del umbral de aceptación.")

        if notes:
            return "needs_review", notes
        return "processed", ["Validación automática exitosa."]
