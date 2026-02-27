"""
Attendance Management System — Database layer.
SQLite or MySQL (config.USE_SQLITE). Parameterized queries only.
Normalized schema: sections, students, attendance.
"""
import sqlite3
from datetime import datetime
from contextlib import contextmanager
from config import USE_SQLITE, get_mysql_config, SQLITE_PATH

if not USE_SQLITE:
    import pymysql  # type: ignore[import-untyped]


def _placeholder(sql):
    """Use ? for SQLite, %s for MySQL."""
    return sql.replace("%s", "?") if USE_SQLITE else sql


@contextmanager
def get_connection():
    if USE_SQLITE:
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        cfg = get_mysql_config()
        conn = pymysql.connect(
            host=cfg["host"],
            port=cfg["port"],
            user=cfg["user"],
            password=cfg["password"],
            database=cfg["database"],
            charset=cfg["charset"],
            cursorclass=pymysql.cursors.DictCursor,
        )
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _row_to_dict(row):
    if row is None:
        return None
    if USE_SQLITE and hasattr(row, "keys"):
        return dict(row)
    return row


def _cursor(conn):
    return conn.cursor()


def _execute(cur, sql, params=None):
    if params is None:
        params = ()
    cur.execute(_placeholder(sql), params)


# ---------------------------------------------------------------------------
# Schema: sections, students, attendance
# ---------------------------------------------------------------------------

def init_db():
    """Create tables: sections, students, attendance. Indexes and UNIQUE on (student_id, date, session)."""
    if USE_SQLITE:
        with get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    roll_no TEXT NOT NULL,
                    name TEXT NOT NULL,
                    section_id INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (section_id) REFERENCES sections(id) ON DELETE CASCADE,
                    UNIQUE(section_id, roll_no)
                );
                CREATE TABLE IF NOT EXISTS attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    session TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'present',
                    marked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                    UNIQUE(student_id, date, session)
                );
                CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date);
                CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance(student_id);
                CREATE INDEX IF NOT EXISTS idx_students_section ON students(section_id);
            """)
        return

    with get_connection() as conn:
        cur = _cursor(conn)
        for sql in [
            """CREATE TABLE IF NOT EXISTS sections (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS students (
                id INT AUTO_INCREMENT PRIMARY KEY,
                roll_no VARCHAR(50) NOT NULL,
                name VARCHAR(200) NOT NULL,
                section_id INT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (section_id) REFERENCES sections(id) ON DELETE CASCADE,
                UNIQUE KEY uq_section_roll (section_id, roll_no)
            )""",
            """CREATE TABLE IF NOT EXISTS attendance (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                date VARCHAR(10) NOT NULL,
                session VARCHAR(20) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'present',
                marked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                UNIQUE KEY uq_student_date_session (student_id, date, session)
            )""",
        ]:
            cur.execute(sql)
        for sql in [
            "CREATE INDEX idx_attendance_date ON attendance(date)",
            "CREATE INDEX idx_attendance_student ON attendance(student_id)",
            "CREATE INDEX idx_students_section ON students(section_id)",
        ]:
            try:
                cur.execute(sql)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def section_create(name):
    """Create section. Returns id. Raises on duplicate name."""
    with get_connection() as conn:
        cur = _cursor(conn)
        _execute(cur, "INSERT INTO sections (name) VALUES (%s)", (name.strip(),))
        return cur.lastrowid


def sections_list():
    """All sections ordered by name."""
    with get_connection() as conn:
        cur = _cursor(conn)
        _execute(cur, "SELECT id, name, created_at FROM sections ORDER BY name")
        rows = cur.fetchall()
    if USE_SQLITE and rows:
        rows = [_row_to_dict(r) for r in rows]
    return [dict(r) if isinstance(r, dict) else {"id": r[0], "name": r[1], "created_at": r[2]} for r in (rows or [])]


def sections_list_with_stats():
    """All sections with student_count and attendance_marked_today (bool) for current date."""
    today = datetime.now().strftime("%Y-%m-%d")
    sections = sections_list()
    out = []
    with get_connection() as conn:
        cur = _cursor(conn)
        for sec in sections:
            _execute(cur, "SELECT COUNT(*) AS n FROM students WHERE section_id = %s", (sec["id"],))
            row = cur.fetchone()
            student_count = (row.get("n") if isinstance(row, dict) else (row[0] if row else 0)) or 0
            _execute(cur,
                     "SELECT 1 FROM attendance a INNER JOIN students s ON a.student_id = s.id WHERE s.section_id = %s AND a.date = %s LIMIT 1",
                     (sec["id"], today))
            row2 = cur.fetchone()
            attendance_marked_today = row2 is not None
            out.append({
                "id": sec["id"],
                "name": sec["name"],
                "created_at": sec["created_at"],
                "student_count": student_count,
                "attendance_marked_today": attendance_marked_today,
            })
    return out


def dashboard_stats():
    """Return total_sections, total_students, attendance_marked_today (count of section-session slots marked today), absent_today."""
    today = datetime.now().strftime("%Y-%m-%d")
    with get_connection() as conn:
        cur = _cursor(conn)
        _execute(cur, "SELECT COUNT(*) AS n FROM sections")
        row = cur.fetchone()
        total_sections = (row.get("n") if isinstance(row, dict) else (row[0] if row else 0)) or 0
        _execute(cur, "SELECT COUNT(*) AS n FROM students")
        row = cur.fetchone()
        total_students = (row.get("n") if isinstance(row, dict) else (row[0] if row else 0)) or 0
        if USE_SQLITE:
            cur.execute("SELECT COUNT(DISTINCT s.section_id || '-' || a.session) AS n FROM attendance a INNER JOIN students s ON a.student_id = s.id WHERE a.date = ?", (today,))
        else:
            _execute(cur,
                     "SELECT COUNT(DISTINCT CONCAT(s.section_id, '-', a.session)) AS n FROM attendance a INNER JOIN students s ON a.student_id = s.id WHERE a.date = %s",
                     (today,))
        row = cur.fetchone()
        attendance_marked_today = (row.get("n") if isinstance(row, dict) else (row[0] if row else 0)) or 0
        _execute(cur, "SELECT COUNT(*) AS n FROM attendance WHERE date = %s AND status = %s", (today, "absent"))
        row = cur.fetchone()
        absent_today = (row.get("n") if isinstance(row, dict) else (row[0] if row else 0)) or 0
    return {
        "total_sections": total_sections,
        "total_students": total_students,
        "attendance_marked_today": attendance_marked_today,
        "absent_today": absent_today,
    }


def section_by_id(sid):
    """Section by id or None."""
    with get_connection() as conn:
        cur = _cursor(conn)
        _execute(cur, "SELECT id, name, created_at FROM sections WHERE id = %s LIMIT 1", (int(sid),))
        row = cur.fetchone()
    if not row:
        return None
    r = _row_to_dict(row) if USE_SQLITE and row else row
    return dict(r) if isinstance(r, dict) else {"id": r[0], "name": r[1], "created_at": r[2]}


def section_by_name(name):
    """Section by name or None (exact match)."""
    with get_connection() as conn:
        cur = _cursor(conn)
        _execute(cur, "SELECT id, name, created_at FROM sections WHERE name = %s LIMIT 1", (name.strip(),))
        row = cur.fetchone()
    if not row:
        return None
    r = _row_to_dict(row) if USE_SQLITE and row else row
    return dict(r) if isinstance(r, dict) else {"id": r[0], "name": r[1], "created_at": r[2]}


def section_by_name_insensitive(name):
    """Section by name (case-insensitive) or None. Use for chat/user input."""
    if not name or not isinstance(name, str):
        return None
    n = name.strip()
    if not n:
        return None
    with get_connection() as conn:
        cur = _cursor(conn)
        _execute(cur, "SELECT id, name, created_at FROM sections WHERE LOWER(TRIM(name)) = LOWER(%s) LIMIT 1", (n,))
        row = cur.fetchone()
    if not row:
        return None
    r = _row_to_dict(row) if USE_SQLITE and row else row
    return dict(r) if isinstance(r, dict) else {"id": r[0], "name": r[1], "created_at": r[2]}


def section_update(sid, name):
    """Update section name. Returns True if updated."""
    with get_connection() as conn:
        cur = _cursor(conn)
        _execute(cur, "UPDATE sections SET name = %s WHERE id = %s", (name.strip(), int(sid)))
        return cur.rowcount > 0 if hasattr(cur, "rowcount") else True


def section_delete(sid):
    """Delete section (cascades to students and attendance). Returns True if deleted."""
    with get_connection() as conn:
        cur = _cursor(conn)
        _execute(cur, "DELETE FROM sections WHERE id = %s", (int(sid),))
        return cur.rowcount > 0 if hasattr(cur, "rowcount") else True


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------

def student_create(roll_no, name, section_id):
    """Add student. Returns id. Raises on duplicate (section_id, roll_no)."""
    with get_connection() as conn:
        cur = _cursor(conn)
        _execute(cur, "INSERT INTO students (roll_no, name, section_id) VALUES (%s, %s, %s)",
                 (roll_no.strip(), name.strip(), int(section_id)))
        return cur.lastrowid


def student_count_by_section(section_id=None):
    """Count students. If section_id given, count in that section; else total."""
    with get_connection() as conn:
        cur = _cursor(conn)
        if section_id is not None:
            _execute(cur, "SELECT COUNT(*) AS n FROM students WHERE section_id = %s", (int(section_id),))
        else:
            _execute(cur, "SELECT COUNT(*) AS n FROM students")
        row = cur.fetchone()
    r = _row_to_dict(row) if USE_SQLITE and row else row
    return (r.get("n") if isinstance(r, dict) else r[0]) or 0


def students_by_section_paginated(section_id, page=1, per_page=50):
    """Students in section, ordered by roll_no. Returns (list, total_count)."""
    page = max(1, int(page))
    per_page = min(100, max(1, int(per_page)))
    offset = (page - 1) * per_page
    with get_connection() as conn:
        cur = _cursor(conn)
        _execute(cur, "SELECT COUNT(*) AS n FROM students WHERE section_id = %s", (int(section_id),))
        row = cur.fetchone()
        total = (row.get("n") if isinstance(row, dict) else (row[0] if row else 0)) or 0
        _execute(cur,
                 "SELECT id, roll_no, name, section_id, created_at FROM students WHERE section_id = %s ORDER BY roll_no LIMIT %s OFFSET %s",
                 (int(section_id), per_page, offset))
        rows = cur.fetchall()
    if USE_SQLITE and rows:
        rows = [_row_to_dict(r) for r in rows]
    list_ = [dict(r) if isinstance(r, dict) else {"id": r[0], "roll_no": r[1], "name": r[2], "section_id": r[3], "created_at": r[4]} for r in (rows or [])]
    return list_, total


def student_by_id(sid):
    """Student by id or None."""
    with get_connection() as conn:
        cur = _cursor(conn)
        _execute(cur, "SELECT id, roll_no, name, section_id, created_at FROM students WHERE id = %s LIMIT 1", (int(sid),))
        row = cur.fetchone()
    if not row:
        return None
    r = _row_to_dict(row) if USE_SQLITE and row else row
    return dict(r) if isinstance(r, dict) else {"id": r[0], "roll_no": r[1], "name": r[2], "section_id": r[3], "created_at": r[4]}


def student_update(sid, roll_no, name, section_id):
    """Update student. Returns True if updated."""
    with get_connection() as conn:
        cur = _cursor(conn)
        _execute(cur, "UPDATE students SET roll_no = %s, name = %s, section_id = %s WHERE id = %s",
                 (roll_no.strip(), name.strip(), int(section_id), int(sid)))
        return cur.rowcount > 0 if hasattr(cur, "rowcount") else True


def student_delete(sid):
    """Delete student (cascades attendance). Returns True if deleted."""
    with get_connection() as conn:
        cur = _cursor(conn)
        _execute(cur, "DELETE FROM students WHERE id = %s", (int(sid),))
        return cur.rowcount > 0 if hasattr(cur, "rowcount") else True


def students_list_paginated(section_id=None, page=1, per_page=25, search=None, sort_by="roll_no"):
    """List students, optionally by section. search filters roll_no and name. sort_by roll_no or name. Returns (list, total)."""
    page = max(1, int(page))
    per_page = min(100, max(1, int(per_page)))
    offset = (page - 1) * per_page
    sort_col = "name" if (sort_by or "").strip().lower() == "name" else "roll_no"
    with get_connection() as conn:
        cur = _cursor(conn)
        if section_id is not None:
            if search:
                q = "%" + (search.strip() or "") + "%"
                _execute(cur, "SELECT COUNT(*) AS n FROM students WHERE section_id = %s AND (roll_no LIKE %s OR name LIKE %s)", (int(section_id), q, q))
            else:
                _execute(cur, "SELECT COUNT(*) AS n FROM students WHERE section_id = %s", (int(section_id),))
        else:
            if search:
                q = "%" + (search.strip() or "") + "%"
                _execute(cur, "SELECT COUNT(*) AS n FROM students WHERE roll_no LIKE %s OR name LIKE %s", (q, q))
            else:
                _execute(cur, "SELECT COUNT(*) AS n FROM students")
        row = cur.fetchone()
        total = (row.get("n") if isinstance(row, dict) else (row[0] if row else 0)) or 0
        if section_id is not None:
            if search:
                q = "%" + (search.strip() or "") + "%"
                _execute(cur, "SELECT id, roll_no, name, section_id, created_at FROM students WHERE section_id = %s AND (roll_no LIKE %s OR name LIKE %s) ORDER BY " + sort_col + " LIMIT %s OFFSET %s", (int(section_id), q, q, per_page, offset))
            else:
                _execute(cur, "SELECT id, roll_no, name, section_id, created_at FROM students WHERE section_id = %s ORDER BY " + sort_col + " LIMIT %s OFFSET %s", (int(section_id), per_page, offset))
        else:
            if search:
                q = "%" + (search.strip() or "") + "%"
                _execute(cur, "SELECT id, roll_no, name, section_id, created_at FROM students WHERE roll_no LIKE %s OR name LIKE %s ORDER BY " + sort_col + " LIMIT %s OFFSET %s", (q, q, per_page, offset))
            else:
                _execute(cur, "SELECT id, roll_no, name, section_id, created_at FROM students ORDER BY " + sort_col + " LIMIT %s OFFSET %s", (per_page, offset))
        rows = cur.fetchall()
    if USE_SQLITE and rows:
        rows = [_row_to_dict(r) for r in rows]
    list_ = [dict(r) if isinstance(r, dict) else {"id": r[0], "roll_no": r[1], "name": r[2], "section_id": r[3], "created_at": r[4]} for r in (rows or [])]
    return list_, total


def student_find_by_roll_or_name(roll_no=None, name=None):
    """Search student across all sections by roll_no and/or name. Returns list of { id, roll_no, name, section_id, section_name }."""
    with get_connection() as conn:
        cur = _cursor(conn)
        if roll_no and roll_no.strip():
            rq = (roll_no.strip().lower() + "%").replace("%%", "%")
            _execute(cur,
                     "SELECT s.id, s.roll_no, s.name, s.section_id FROM students s WHERE LOWER(s.roll_no) LIKE %s OR s.roll_no = %s ORDER BY s.roll_no LIMIT 20",
                     (rq, roll_no.strip()))
        elif name and name.strip():
            nq = "%" + (name.strip() + "%").replace("%%", "%")
            _execute(cur,
                     "SELECT s.id, s.roll_no, s.name, s.section_id FROM students s WHERE s.name LIKE %s ORDER BY s.name LIMIT 20",
                     (nq,))
        else:
            return []
        rows = cur.fetchall()
    if USE_SQLITE and rows:
        rows = [_row_to_dict(r) for r in rows]
    out = []
    for r in (rows or []):
        row = dict(r) if isinstance(r, dict) else {"id": r[0], "roll_no": r[1], "name": r[2], "section_id": r[3]}
        sec = section_by_id(row["section_id"])
        row["section_name"] = sec["name"] if sec else ""
        out.append(row)
    return out


def students_attendance_rates(date_start, date_end):
    """For each student, compute present count and rate in [date_start, date_end]. total = days * 2 (morning+afternoon). Returns list of { student_id, roll_no, name, section_name, present, total, rate }."""
    from datetime import datetime as dt
    try:
        start = dt.strptime(str(date_start)[:10], "%Y-%m-%d")
        end = dt.strptime(str(date_end)[:10], "%Y-%m-%d")
    except ValueError:
        return []
    days = max(0, (end - start).days + 1)
    total_sessions = days * 2
    if total_sessions == 0:
        return []
    with get_connection() as conn:
        cur = _cursor(conn)
        _execute(cur,
                 "SELECT s.id, s.roll_no, s.name, s.section_id FROM students s ORDER BY s.section_id, s.roll_no",
                 ())
        students = cur.fetchall()
    if USE_SQLITE and students:
        students = [_row_to_dict(r) for r in students]
    students = [dict(r) if isinstance(r, dict) else {"id": r[0], "roll_no": r[1], "name": r[2], "section_id": r[3]} for r in (students or [])]
    out = []
    for s in students:
        sid = s["id"]
        with get_connection() as conn:
            cur = _cursor(conn)
            _execute(cur,
                     "SELECT COUNT(*) AS n FROM attendance WHERE student_id = %s AND date >= %s AND date <= %s AND status = %s",
                     (sid, str(date_start)[:10], str(date_end)[:10], "present"))
            row = cur.fetchone()
        r = _row_to_dict(row) if USE_SQLITE and row else row
        present = (r.get("n") if isinstance(r, dict) else (row[0] if row else 0)) or 0
        rate = (present / total_sessions) if total_sessions else 0
        sec = section_by_id(s["section_id"])
        out.append({
            "student_id": sid,
            "roll_no": s["roll_no"],
            "name": s["name"],
            "section_name": sec["name"] if sec else "",
            "present": present,
            "total": total_sessions,
            "rate": round(rate, 2),
        })
    return out


def students_absent_more_than_days(min_days, date_start, date_end):
    """Students with distinct absent days >= min_days in [date_start, date_end]. Returns list of { student_id, roll_no, name, section_name, absent_days }."""
    with get_connection() as conn:
        cur = _cursor(conn)
        _execute(cur,
                 "SELECT student_id, COUNT(DISTINCT date) AS absent_days FROM attendance WHERE status = %s AND date >= %s AND date <= %s GROUP BY student_id HAVING absent_days >= %s",
                 ("absent", str(date_start)[:10], str(date_end)[:10], int(min_days)))
        rows = cur.fetchall()
    if USE_SQLITE and rows:
        rows = [_row_to_dict(r) for r in rows]
    out = []
    for r in (rows or []):
        row = dict(r) if isinstance(r, dict) else {"student_id": r[0], "absent_days": r[1]}
        sid = row["student_id"]
        student = student_by_id(sid)
        if not student:
            continue
        sec = section_by_id(student["section_id"])
        out.append({
            "student_id": sid,
            "roll_no": student["roll_no"],
            "name": student["name"],
            "section_name": sec["name"] if sec else "",
            "absent_days": row["absent_days"],
        })
    return out


# ---------------------------------------------------------------------------
# Attendance (parameterized, no hardcoded logic)
# ---------------------------------------------------------------------------

VALID_SESSIONS = ("morning", "afternoon")
VALID_STATUSES = ("present", "absent")


def attendance_upsert(student_id, date_str, session, status):
    """Insert or replace attendance for (student_id, date, session). status in ('present','absent')."""
    if session not in VALID_SESSIONS or status not in VALID_STATUSES:
        raise ValueError("Invalid session or status")
    with get_connection() as conn:
        cur = _cursor(conn)
        if USE_SQLITE:
            cur.execute(
                "INSERT INTO attendance (student_id, date, session, status, marked_at) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(student_id, date, session) DO UPDATE SET status = excluded.status, marked_at = excluded.marked_at",
                (int(student_id), date_str.strip(), session, status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
        else:
            _execute(cur,
                     "INSERT INTO attendance (student_id, date, session, status, marked_at) VALUES (%s, %s, %s, %s, NOW()) "
                     "ON DUPLICATE KEY UPDATE status = VALUES(status), marked_at = NOW()",
                     (int(student_id), date_str.strip(), session, status))
        return cur.lastrowid if hasattr(cur, 'lastrowid') else None


def attendance_get_by_date_section_session(date_str, section_id, session):
    """For given date, section, session: list of { student_id, roll_no, name, status }.
    Students without a row default to status 'present'.
    """
    with get_connection() as conn:
        cur = _cursor(conn)
        _execute(cur,
                 "SELECT s.id AS student_id, s.roll_no, s.name FROM students s WHERE s.section_id = %s ORDER BY s.roll_no",
                 (int(section_id),))
        students = cur.fetchall()
    if USE_SQLITE and students:
        students = [_row_to_dict(r) for r in students]
    students = [dict(r) if isinstance(r, dict) else {"student_id": r[0], "roll_no": r[1], "name": r[2]} for r in (students or [])]
    if not students:
        return []
    ids = [s["student_id"] for s in students]
    placeholders = ",".join(["%s"] * len(ids))
    with get_connection() as conn:
        cur = _cursor(conn)
        _execute(cur,
                 f"SELECT student_id, status FROM attendance WHERE date = %s AND session = %s AND student_id IN ({placeholders})",
                 [date_str.strip(), session] + ids)
        rows = cur.fetchall()
    if USE_SQLITE and rows:
        rows = [_row_to_dict(r) for r in rows]
    status_map = {r.get("student_id") if isinstance(r, dict) else r[0]: (r.get("status") if isinstance(r, dict) else r[1]) for r in (rows or [])}
    for s in students:
        s["status"] = status_map.get(s["student_id"], "present")
    return students


def attendance_set_absent_for_date_section_session(date_str, section_id, session, absent_student_ids):
    """Ensure every student in section has a row for (date, session). Set given student_ids to absent, rest present."""
    list_with_status = attendance_get_by_date_section_session(date_str, section_id, session)
    absent_set = set(int(x) for x in absent_student_ids)
    for s in list_with_status:
        sid = s["student_id"]
        new_status = "absent" if sid in absent_set else "present"
        attendance_upsert(sid, date_str, session, new_status)


def attendance_absent_on_date_section_session(date_str, section_id, session):
    """List of { roll_no, name } who are absent."""
    rows = attendance_get_by_date_section_session(date_str, section_id, session)
    return [{"roll_no": r["roll_no"], "name": r["name"]} for r in rows if r.get("status") == "absent"]


def attendance_absent_on_date_section_by_name(date_str, section_name, session):
    """Same but section by name."""
    sec = section_by_name(section_name)
    if not sec:
        return []
    return attendance_absent_on_date_section_session(date_str, sec["id"], session)


def attendance_absent_today_all_sections(date_str=None):
    """Absentees across all sections for given date. Returns list of { section_name, session, roll_no, name }."""
    date_str = date_str or datetime.now().strftime("%Y-%m-%d")
    sections = sections_list()
    out = []
    for sec in sections:
        for session in VALID_SESSIONS:
            for a in attendance_absent_on_date_section_session(date_str, sec["id"], session):
                out.append({"section_name": sec["name"], "session": session, "roll_no": a["roll_no"], "name": a["name"]})
    return out


def attendance_present_on_date_section_session(date_str, section_id, session):
    """List of { roll_no, name } who are present."""
    rows = attendance_get_by_date_section_session(date_str, section_id, session)
    return [{"roll_no": r["roll_no"], "name": r["name"]} for r in rows if r.get("status") == "present"]


def attendance_present_on_date_section_by_name(date_str, section_name, session):
    """Same but section by name."""
    sec = section_by_name(section_name)
    if not sec:
        return []
    return attendance_present_on_date_section_session(date_str, sec["id"], session)


def attendance_present_on_date_all_sections(date_str):
    """Present on date across all sections/sessions. Returns list of { section_name, session, roll_no, name }."""
    date_str = date_str or datetime.now().strftime("%Y-%m-%d")
    sections = sections_list()
    out = []
    for sec in sections:
        for session in VALID_SESSIONS:
            for p in attendance_present_on_date_section_session(date_str, sec["id"], session):
                out.append({"section_name": sec["name"], "session": session, "roll_no": p["roll_no"], "name": p["name"]})
    return out


def attendance_view_by_date(date_str):
    """Summary for a date: per section, per session, present/absent counts."""
    sections = sections_list()
    out = []
    for sec in sections:
        for session in VALID_SESSIONS:
            rows = attendance_get_by_date_section_session(date_str, sec["id"], session)
            present = sum(1 for r in rows if r.get("status") == "present")
            absent = sum(1 for r in rows if r.get("status") == "absent")
            out.append({"section_id": sec["id"], "section_name": sec["name"], "session": session, "present": present, "absent": absent, "students": rows})
    return out


def attendance_records_paginated(section_id, date_str, session, page=1, per_page=25, search=None):
    """Records for section/date/session with pagination and search. Returns (list of { roll_no, name, status }, total)."""
    if section_id is None or not date_str or not session or session not in VALID_SESSIONS:
        return [], 0
    page = max(1, int(page))
    per_page = min(100, max(1, int(per_page)))
    offset = (page - 1) * per_page
    with get_connection() as conn:
        cur = _cursor(conn)
        if search and search.strip():
            q = "%" + search.strip() + "%"
            _execute(cur,
                     "SELECT COUNT(*) AS n FROM students s WHERE s.section_id = %s AND (s.roll_no LIKE %s OR s.name LIKE %s)",
                     (int(section_id), q, q))
        else:
            _execute(cur, "SELECT COUNT(*) AS n FROM students WHERE section_id = %s", (int(section_id),))
        row = cur.fetchone()
        total = (row.get("n") if isinstance(row, dict) else (row[0] if row else 0)) or 0
        if USE_SQLITE:
            sql = (
                "SELECT s.roll_no, s.name, COALESCE(a.status, 'present') AS status FROM students s "
                "LEFT JOIN attendance a ON a.student_id = s.id AND a.date = ? AND a.session = ? "
                "WHERE s.section_id = ?"
            )
            params = [date_str.strip(), session, int(section_id)]
            if search and search.strip():
                sql += " AND (s.roll_no LIKE ? OR s.name LIKE ?)"
                params.extend(["%" + search.strip() + "%", "%" + search.strip() + "%"])
            sql += " ORDER BY s.roll_no LIMIT ? OFFSET ?"
            params.extend([per_page, offset])
            cur.execute(sql, params)
        else:
            sql = (
                "SELECT s.roll_no, s.name, COALESCE(a.status, 'present') AS status FROM students s "
                "LEFT JOIN attendance a ON a.student_id = s.id AND a.date = %s AND a.session = %s "
                "WHERE s.section_id = %s"
            )
            params = [date_str.strip(), session, int(section_id)]
            if search and search.strip():
                sql += " AND (s.roll_no LIKE %s OR s.name LIKE %s)"
                params.extend(["%" + search.strip() + "%", "%" + search.strip() + "%"])
            sql += " ORDER BY s.roll_no LIMIT %s OFFSET %s"
            params.extend([per_page, offset])
            _execute(cur, sql, params)
        rows = cur.fetchall()
    if USE_SQLITE and rows:
        rows = [_row_to_dict(r) for r in rows]
    list_ = [dict(r) if isinstance(r, dict) else {"roll_no": r[0], "name": r[1], "status": r[2]} for r in (rows or [])]
    return list_, total
