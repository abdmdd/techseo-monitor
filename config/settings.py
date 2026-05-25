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

YANDEX_CLIENT_ID = os.getenv(
    "YANDEX_CLIENT_ID",
    ""
)

YANDEX_CLIENT_SECRET = os.getenv(
    "YANDEX_CLIENT_SECRET",
    ""
)

DEFAULT_YANDEX_REDIRECT_URI = "https://techseo-monitor.ru/?oauth_provider=yandex"
YANDEX_REDIRECT_URI = os.getenv("YANDEX_REDIRECT_URI", DEFAULT_YANDEX_REDIRECT_URI)

if YANDEX_REDIRECT_URI.rstrip("/") == "https://techseo-monitor.ru/yandex/oauth/callback":
    YANDEX_REDIRECT_URI = DEFAULT_YANDEX_REDIRECT_URI

YANDEX_GPT_API_KEY = os.getenv(
    "YANDEX_GPT_API_KEY",
    ""
)

YANDEX_GPT_FOLDER_ID = os.getenv(
    "YANDEX_GPT_FOLDER_ID",
    ""
)

YANDEX_GPT_MODEL = os.getenv(
    "YANDEX_GPT_MODEL",
    "yandexgpt-lite"
)

YANDEX_GPT_TIMEOUT = float(os.getenv(
    "YANDEX_GPT_TIMEOUT",
    "20"
))


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
