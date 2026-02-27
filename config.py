"""
Production config for Flask + MySQL/SQLite AI system.
Set environment variables or override in production.
USE_SQLITE=1 to run without MySQL (default for local run).
"""
import os

# Load .env from project root
_CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
_ENV_FILE = os.path.join(_CONFIG_DIR, ".env")
try:
    from dotenv import load_dotenv  # type: ignore[import-untyped]
    load_dotenv(_ENV_FILE)
    load_dotenv()
except ImportError:
    pass


def _read_openai_key_from_file():
    """Read OPENAI_API_KEY directly from .env file (reliable when env var not set)."""
    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if key and key.startswith("sk-"):
        return key
    if not os.path.isfile(_ENV_FILE):
        return ""
    try:
        with open(_ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("OPENAI_API_KEY=") and not line.startswith("OPENAI_API_KEY=#"):
                    val = line.split("=", 1)[1].strip().strip("\"'")
                    if val and val.startswith("sk-"):
                        return val
    except Exception:
        pass
    return ""


# Flask
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production-use-long-random-string")

# Database: set USE_SQLITE=0 to use MySQL; default 1 so app runs without MySQL
USE_SQLITE = os.environ.get("USE_SQLITE", "1").strip().lower() in ("1", "true", "yes")
SQLITE_PATH = os.environ.get("SQLITE_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_system.db"))

# OpenAI (billing-safe defaults); read from .env file if env var not set
OPENAI_API_KEY = _read_openai_key_from_file()


def get_openai_api_key():
    """Return API key; reload .env then read from env or .env file."""
    try:
        from dotenv import load_dotenv  # type: ignore[import-untyped]
        load_dotenv(_ENV_FILE)
        load_dotenv()
    except ImportError:
        pass
    return _read_openai_key_from_file()


OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_MAX_TOKENS = int(os.environ.get("OPENAI_MAX_TOKENS", "400"))
OPENAI_TEMPERATURE = float(os.environ.get("OPENAI_TEMPERATURE", "0.2"))

# Chat rate limits (per IP)
CHAT_RATE_LIMIT_PER_MINUTE = int(os.environ.get("CHAT_RATE_LIMIT_PER_MINUTE", "10"))
CHAT_DAILY_CAP = int(os.environ.get("CHAT_DAILY_CAP", "200"))

# MySQL (when USE_SQLITE is False)
MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "ai_system")

def get_mysql_config():
    return {
        "host": MYSQL_HOST,
        "port": MYSQL_PORT,
        "user": MYSQL_USER,
        "password": MYSQL_PASSWORD,
        "database": MYSQL_DATABASE,
        "charset": "utf8mb4",
        "cursorclass": None,
    }
