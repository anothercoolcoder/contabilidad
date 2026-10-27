from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from contabilidad.db import LocalDatabase


class UserService:
    def __init__(self, database: LocalDatabase):
        self.database = database

    def register_user(self, name: str, phone: str, employee_id: str) -> dict:
        clean_name = name.strip()
        clean_phone = phone.strip()
        clean_employee_id = employee_id.strip()

        if not clean_name:
            raise ValueError("El nombre del usuario es obligatorio.")
        if not clean_phone:
            raise ValueError("El teléfono del usuario es obligatorio.")
        if not clean_employee_id:
            raise ValueError("El identificador del empleado es obligatorio.")

        existing_by_phone = self.database.get_user_by_phone(clean_phone)
        if existing_by_phone:
            raise ValueError(f"El teléfono {clean_phone} ya está registrado.")

        existing_row = self.database.connection.execute(
            "SELECT 1 FROM users WHERE employee_id = ?",
            (clean_employee_id,),
        ).fetchone()
        if existing_row:
            raise ValueError(f"El empleado {clean_employee_id} ya está registrado.")

        user_id = str(uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        return self.database.create_user(
            user_id=user_id,
            name=clean_name,
            phone=clean_phone,
            employee_id=clean_employee_id,
            created_at=created_at,
        )
