import os

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv():
        return False


# ==================================================
# LOAD ENV
# ==================================================

load_dotenv()


# ==================================================
# APP
# ==================================================

APP_NAME = "TechSEO Monitor"

APP_VERSION = "1.0"


# ==================================================
# DATABASE
# ==================================================

SQLITE_DB_PATH = os.getenv(
    "SQLITE_DB_PATH",
    "data/techseo.db"
)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{SQLITE_DB_PATH}"
)


# ==================================================
# YANDEX
# ==================================================

YANDEX_WEBMASTER_TOKEN = os.getenv(
    "YANDEX_WEBMASTER_TOKEN",
    ""
)


# ==================================================
# GOOGLE
# ==================================================

GOOGLE_API_KEY = os.getenv(
    "GOOGLE_API_KEY",
    ""
)


# ==================================================
# AI
# ==================================================

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY",
    ""
)


# ==================================================
# REPORTS
# ==================================================

REPORTS_DIR = "reports"


# ==================================================
# AUDITS
# ==================================================

DEFAULT_TIMEOUT = 15

MAX_PAGES_TO_CRAWL = 50
