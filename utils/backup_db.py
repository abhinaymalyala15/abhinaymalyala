"""
Automatic database backup for AI Attendance (SQLite only).
Copies ai_system.db to backups/ai_system_YYYYMMDD_HHMMSS.db.
Keeps last 30 backups. Run on app start if last backup is older than 24 hours.
"""
import os
import shutil
import glob
from datetime import datetime

# Project root (parent of utils)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUPS_DIR = os.path.join(PROJECT_ROOT, "backups")
MAX_BACKUPS = 30
BACKUP_INTERVAL_HOURS = 24
LAST_BACKUP_FILE = os.path.join(BACKUPS_DIR, ".last_backup_time")


def get_db_path():
    """SQLite path from config (avoid importing app to prevent circular deps)."""
    try:
        from config import USE_SQLITE, SQLITE_PATH
        if USE_SQLITE and SQLITE_PATH:
            return SQLITE_PATH if os.path.isabs(SQLITE_PATH) else os.path.join(PROJECT_ROOT, SQLITE_PATH)
    except Exception:
        pass
    return os.path.join(PROJECT_ROOT, "ai_system.db")


def _last_backup_time():
    """Return last backup timestamp (float) or 0 if never."""
    if not os.path.isfile(LAST_BACKUP_FILE):
        return 0
    try:
        with open(LAST_BACKUP_FILE, "r") as f:
            return float(f.read().strip())
    except Exception:
        return 0


def _write_last_backup_time():
    with open(LAST_BACKUP_FILE, "w") as f:
        f.write(str(datetime.now().timestamp()))


def _list_backup_files():
    """List backup files (full path) sorted by mtime descending."""
    pattern = os.path.join(BACKUPS_DIR, "ai_system_*.db")
    files = glob.glob(pattern)
    return sorted(files, key=os.path.getmtime, reverse=True)


def run_backup():
    """
    Copy SQLite DB to backups/ai_system_YYYYMMDD_HHMMSS.db.
    Keep only last MAX_BACKUPS. Does not interrupt DB access (copy is quick).
    Returns (True, path) on success, (False, error_message) on failure.
    """
    db_path = get_db_path()
    if not os.path.isfile(db_path):
        return False, "Database file not found: " + db_path
    try:
        from config import USE_SQLITE
        if not USE_SQLITE:
            return False, "Backup only runs for SQLite (USE_SQLITE=1)"
    except Exception:
        pass
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(BACKUPS_DIR, f"ai_system_{stamp}.db")
    try:
        shutil.copy2(db_path, dest)
    except Exception as e:
        return False, str(e)
    _write_last_backup_time()
    # Prune old backups
    backups = _list_backup_files()
    for f in backups[MAX_BACKUPS:]:
        try:
            os.remove(f)
        except Exception:
            pass
    return True, dest


def should_run_backup():
    """True if last backup was more than BACKUP_INTERVAL_HOURS ago (or never)."""
    last = _last_backup_time()
    if last == 0:
        return True
    elapsed_hours = (datetime.now().timestamp() - last) / 3600
    return elapsed_hours >= BACKUP_INTERVAL_HOURS


def run_backup_if_due():
    """Run backup only if 24+ hours since last (or first run). Returns (ran, result)."""
    if not should_run_backup():
        return False, None
    ok, path_or_err = run_backup()
    return True, (path_or_err if ok else path_or_err)
