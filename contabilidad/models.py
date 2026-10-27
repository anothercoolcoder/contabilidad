from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class User:
    user_id: str
    name: str
    phone: str
    employee_id: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_active: bool = True


@dataclass
class Document:
    document_id: str
    user_id: str
    source: str = "whatsapp"
    file_name: str = ""
    raw_text: str = ""
    status: str = "received"
    extracted_fields: Dict[str, Any] = field(default_factory=dict)
    validation_notes: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    processed_at: Optional[str] = None


@dataclass
class ProcessingResult:
    document_id: str
    user_id: str
    status: str
    extracted_fields: Dict[str, Any]
    validation_notes: List[str]
    confidence: float
