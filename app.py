"""
Admin-only Attendance Management System. Open at /.
"""
import logging
import os

# Structured logging for chat and routes
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Load .env from project root (same folder as app.py) so OPENAI_API_KEY is always found
_project_root = os.path.dirname(os.path.abspath(__file__))
_env_path = os.path.join(_project_root, ".env")
try:
    from dotenv import load_dotenv  # type: ignore[import-untyped]
    load_dotenv(_env_path)
except ImportError:
    pass

from flask import Flask, redirect, url_for

from config import SECRET_KEY, get_openai_api_key
from models import init_db
from routes.main import bp as main_bp

# Confirm API key is loaded (uses same loader as chat)
if get_openai_api_key():
    print("KEY LOADED: True  (OpenAI chat enabled)")
else:
    print("KEY LOADED: False (AI will say 'not configured'). To fix: create .env in project root with: OPENAI_API_KEY=sk-...")
    print("  .env path checked:", _env_path)

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["PERMANENT_SESSION_LIFETIME"] = 86400  # 1 day

app.register_blueprint(main_bp)

# Initialize DB when app is loaded (needed for gunicorn / Render)
init_db()


@app.route("/dashboard")
def dashboard_redirect():
    return redirect(url_for("main.index"))


@app.route("/reload")
def reload_route():
    return redirect(url_for("main.index"))


def create_app():
    return app


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    print(f"Attendance Management System ready. Open http://127.0.0.1:{port}/")
    app.run(host="0.0.0.0", port=port, debug=True)
