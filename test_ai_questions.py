"""
Run AI chat questions and verify answers.
Use: from project root, run:  python test_ai_questions.py
Requires: Flask app, DB initialized, sample knowledge seeded.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import init_db, seed_sample_knowledge, user_by_username, login_record

# Test user for chat (created if missing)
TEST_USER = "test_ai_run"
TEST_PASS = "test_ai_run_123"
TEST_EMAIL = "test_ai_run@local.test"


def ensure_test_user(client):
    """Register test user if not exists, then log in. Returns True if session is ready."""
    from werkzeug.security import generate_password_hash
    import models
    user = user_by_username(TEST_USER)
    if not user:
        try:
            models.user_create(TEST_USER, TEST_EMAIL, generate_password_hash(TEST_PASS))
        except Exception:
            pass
    r = client.post("/auth/login", data={"username": TEST_USER, "password": TEST_PASS}, follow_redirects=True)
    if r.status_code != 200:
        return False
    # Ensure one login record for "current login" answers
    user = user_by_username(TEST_USER)
    if user:
        login_record(user["id"], "127.0.0.1")
    return True


def chat(client, question):
    """POST to /ai/chat and return response text."""
    r = client.post(
        "/ai/chat",
        json={"question": question, "language": "en"},
        content_type="application/json",
    )
    if r.status_code != 200:
        return None
    data = r.get_json()
    return (data or {}).get("response", "")


# Questions and how to validate the answer
# Each item: (question, validator)
# validator: "greeting" | "dynamic_login" | "dynamic_count_today" | "dynamic_who" | "dynamic_time_now" | "dynamic_last_q" | "knowledge" | callable(response) -> bool
def _has_substring(*subs):
    def fn(response):
        r = (response or "").lower()
        return any(s.lower() in r for s in subs)
    return fn


TESTS = [
    # Greetings (time-based greeting or friendly reply)
    ("hi", _has_substring("good morning", "good afternoon", "good evening", "good night", "how can i help")),
    ("hello", _has_substring("good morning", "good afternoon", "good evening", "good night", "how can i help")),
    ("hoii", _has_substring("good morning", "good afternoon", "good evening", "good night", "how can i help")),
    ("how are you", _has_substring("good morning", "good afternoon", "good evening", "good night", "how can i help")),
    ("hey", _has_substring("good morning", "good afternoon", "good evening", "good night", "how can i help")),
    # Current time (must give actual time, not AI definition)
    ("what is the time right now?", _has_substring("time", "pm", "am")),
    ("what time is it?", _has_substring("time", "pm", "am")),
    ("current time", _has_substring("time", "pm", "am")),
    # Login time (must say when user logged in, not AI definition)
    ("at what time", _has_substring("logged in", "login")),
    ("when did i login?", _has_substring("logged in", "login")),
    ("at what time did i login?", _has_substring("logged in", "login")),
    # How many users today
    ("how many users logined today", _has_substring("user", "logged in", "today")),
    ("how many logined today", _has_substring("user", "logged in", "today")),
    ("how many users today?", _has_substring("user", "today")),
    # Who logged in
    ("who?", _has_substring("user", "logged in", "today", "no one")),
    ("who", _has_substring("user", "logged in", "today", "no one")),
    ("who logged in?", _has_substring("user", "logged in", "today", "no one")),
    ("who logged in today?", _has_substring("user", "logged in", "today", "no one")),
    # Last question
    ("what was my last question?", lambda r: "last question" in (r or "").lower() or "not asked" in (r or "").lower() or "you have not" in (r or "").lower()),
    # Knowledge base (must not be generic "I don't have an answer")
    ("What is Python?", _has_substring("python", "programming")),
    ("What is the capital of India?", _has_substring("delhi")),
    ("What is Flask?", _has_substring("flask", "web")),
    ("What can you do?", _has_substring("login", "question", "help", "dashboard")),
    ("What is this app?", _has_substring("chat", "dashboard", "login")),
]


def main():
    print("Initializing DB and knowledge...")
    init_db()
    seed_sample_knowledge(force=True)  # ensure expanded KB for consistent answers
    client = app.test_client()
    if not ensure_test_user(client):
        print("Failed to create or log in test user. Ensure app and DB are usable.")
        return 1
    print("Running", len(TESTS), "questions...\n")
    failed = []
    for q, validator in TESTS:
        response = chat(client, q)
        if response is None:
            failed.append((q, "No response (request failed)"))
            print("FAIL:", repr(q)[:50])
            continue
        ok = validator(response) if callable(validator) else (validator in (response or "").lower())
        if ok:
            print("PASS:", repr(q)[:55], "->", repr(response[:60]) + ("..." if len(response) > 60 else ""))
        else:
            failed.append((q, response[:120]))
            print("FAIL:", repr(q)[:55])
            print("     Got:", repr(response[:100]))
    print("\n--- Summary ---")
    print("Passed:", len(TESTS) - len(failed), "/", len(TESTS))
    if failed:
        print("Failed:", len(failed))
        for q, msg in failed:
            print("  -", repr(q), "->", repr(msg)[:80])
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
