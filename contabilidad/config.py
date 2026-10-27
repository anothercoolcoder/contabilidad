from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
APP_NAME = "contabilidad-local"
DATA_DIR = BASE_DIR / "data"
DEFAULT_DB_PATH = DATA_DIR / "accounting_local.db"
REVIEW_CONFIDENCE_THRESHOLD = 0.75

# Light-weight defaults for the initial project skeleton.
SUPPORTED_MESSAGE_SOURCES = {"whatsapp"}
VALID_DOCUMENT_TYPES = {"factura", "boleta", "guia", "nc", "nd", "otro"}
