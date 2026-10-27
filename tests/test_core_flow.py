import pytest

from contabilidad.db import LocalDatabase
from contabilidad.services.processor import ProcessingPipeline
from contabilidad.services.user_service import UserService


def test_user_registration_and_document_processing():
    db = LocalDatabase(":memory:")
    user_service = UserService(db)

    user = user_service.register_user("Ana", "+56912345678", "EMP-001")
    assert user["phone"] == "+56912345678"

    pipeline = ProcessingPipeline(db)
    result = pipeline.process_document(
        user_phone="+56912345678",
        file_name="factura_acme.pdf",
        raw_text="Factura - Proveedor ACME\nTotal: 125000\nRUT: 76.123.456-0",
    )

    assert result["status"] == "processed"
    assert result["extracted_fields"]["vendor"] == "Proveedor ACME"
    assert result["extracted_fields"]["total"] == 125000.0

    saved = db.get_document(result["document_id"])
    assert saved["status"] == "processed"
    db.close()


def test_unregistered_user_is_rejected():
    db = LocalDatabase(":memory:")
    pipeline = ProcessingPipeline(db)

    with pytest.raises(ValueError, match="debe estar registrado"):
        pipeline.process_document(
            user_phone="+56999999999",
            file_name="boleta.txt",
            raw_text="Boleta\nTotal: 50000",
        )

    db.close()
