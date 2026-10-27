from __future__ import annotations

import argparse
from datetime import datetime, timezone
from uuid import uuid4

from contabilidad.config import DEFAULT_DB_PATH
from contabilidad.db import LocalDatabase
from contabilidad.services.processor import ProcessingPipeline
from contabilidad.services.user_service import UserService


def register_user_command(args):
    db = LocalDatabase(args.db)
    service = UserService(db)
    user = service.register_user(args.name, args.phone, args.employee_id)
    print(f"Usuario registrado: {user['user_id']} | {user['name']} | {user['phone']}")
    db.close()


def submit_document_command(args):
    db = LocalDatabase(args.db)
    pipeline = ProcessingPipeline(db)
    result = pipeline.process_document(
        user_phone=args.phone,
        file_name=args.file_name,
        raw_text=args.raw_text,
    )
    print(result)
    db.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local accounting workflow prototype")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    register_parser = subparsers.add_parser("register-user", help="Register a field user")
    register_parser.add_argument("--name", required=True)
    register_parser.add_argument("--phone", required=True)
    register_parser.add_argument("--employee-id", required=True)
    register_parser.set_defaults(func=register_user_command)

    submit_parser = subparsers.add_parser("submit-document", help="Submit a document for OCR + RAG processing")
    submit_parser.add_argument("--phone", required=True, help="Registered user's phone number")
    submit_parser.add_argument("--file-name", required=True)
    submit_parser.add_argument("--raw-text", required=True)
    submit_parser.set_defaults(func=submit_document_command)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
