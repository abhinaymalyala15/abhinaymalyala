"""
Professional Admin Attendance System. Sidebar layout, dashboard, sections, students, mark attendance, records.
Includes hybrid AI chat (Attendance Assistant) with intent engine, smart defaults, and AI formatting.
"""
import logging
import re
import smtplib
import time
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import Blueprint, request, jsonify, render_template, session
from models import (
    section_create,
    section_update,
    section_delete,
    sections_list,
    sections_list_with_stats,
    section_by_id,
    section_by_name,
    section_by_name_insensitive,
    student_create,
    student_update,
    student_delete,
    student_by_id,
    student_count_by_section,
    students_list_paginated,
    students_by_section_paginated,
    student_find_by_roll_or_name,
    students_attendance_rates,
    students_absent_more_than_days,
    attendance_get_by_date_section_session,
    attendance_set_absent_for_date_section_session,
    attendance_absent_on_date_section_by_name,
    attendance_present_on_date_section_by_name,
    attendance_absent_today_all_sections,
    attendance_present_on_date_all_sections,
    attendance_view_by_date,
    attendance_records_paginated,
    dashboard_stats,
    report_daily,
    report_student,
    VALID_SESSIONS,
)

logger = logging.getLogger(__name__)


bp = Blueprint("main", __name__, url_prefix="/")


@bp.route("/")
def index():
    return render_template("main.html")


# ---------------------------------------------------------------------------
# Dashboard (cached 60s for performance)
# ---------------------------------------------------------------------------

_dashboard_cache = None
_dashboard_cache_time = 0
DASHBOARD_CACHE_SECONDS = 60


def _invalidate_dashboard_cache():
    global _dashboard_cache
    _dashboard_cache = None


@bp.route("/api/dashboard/stats", methods=["GET"])
def api_dashboard_stats():
    global _dashboard_cache, _dashboard_cache_time
    now = time.time()
    if _dashboard_cache is not None and (now - _dashboard_cache_time) < DASHBOARD_CACHE_SECONDS:
        return jsonify(_dashboard_cache)
    data = dashboard_stats()
    _dashboard_cache = data
    _dashboard_cache_time = now
    return jsonify(data)


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

@bp.route("/api/sections", methods=["GET"])
def api_sections_list():
    stats = request.args.get("stats", "").strip().lower() in ("1", "true", "yes")
    if stats:
        return jsonify(sections_list_with_stats())
    return jsonify(sections_list())


@bp.route("/api/sections", methods=["POST"])
def api_sections_create():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Section name is required"}), 400
    try:
        sid = section_create(name)
        _invalidate_dashboard_cache()
        return jsonify({"id": sid, "ok": True})
    except Exception as e:
        if "UNIQUE" in str(e) or "Duplicate" in str(e):
            return jsonify({"error": "A section with that name already exists"}), 400
        raise


@bp.route("/api/sections/<int:sid>", methods=["PATCH"])
def api_sections_update(sid):
    if section_by_id(sid) is None:
        return jsonify({"error": "Section not found"}), 404
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Section name is required"}), 400
    try:
        section_update(sid, name)
        _invalidate_dashboard_cache()
        return jsonify({"ok": True})
    except Exception as e:
        if "UNIQUE" in str(e) or "Duplicate" in str(e):
            return jsonify({"error": "A section with that name already exists"}), 400
        raise


@bp.route("/api/sections/<int:sid>", methods=["DELETE"])
def api_sections_delete(sid):
    if section_by_id(sid) is None:
        return jsonify({"error": "Section not found"}), 404
    section_delete(sid)
    _invalidate_dashboard_cache()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Students (global list with filters + by-section for dropdown)
# ---------------------------------------------------------------------------

@bp.route("/api/students", methods=["GET"])
def api_students_list():
    """List students with optional section_id, search, pagination, sort."""
    section_id = request.args.get("section_id", type=int)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)
    per_page = min(100, max(1, per_page))
    search = request.args.get("search", "").strip() or None
    sort_by = request.args.get("sort_by", "roll_no", type=str) or "roll_no"
    students, total = students_list_paginated(section_id=section_id, page=page, per_page=per_page, search=search, sort_by=sort_by)
    return jsonify({"students": students, "total": total, "page": page, "per_page": per_page})


@bp.route("/api/students", methods=["POST"])
def api_students_create():
    data = request.get_json() or {}
    roll_no = (data.get("roll_no") or "").strip()
    name = (data.get("name") or "").strip()
    try:
        section_id = int(data.get("section_id", 0))
    except (TypeError, ValueError):
        section_id = 0
    if not roll_no or not name:
        return jsonify({"error": "Roll number and name are required"}), 400
    if not section_id or section_by_id(section_id) is None:
        return jsonify({"error": "Valid section is required"}), 400
    try:
        sid = student_create(roll_no=roll_no, name=name, section_id=section_id)
        _invalidate_dashboard_cache()
        return jsonify({"id": sid, "ok": True})
    except Exception as e:
        if "UNIQUE" in str(e) or "Duplicate" in str(e):
            return jsonify({"error": "A student with that roll number already exists in this section"}), 400
        raise


@bp.route("/api/students/<int:sid>", methods=["GET"])
def api_students_get(sid):
    """Get one student for edit form."""
    st = student_by_id(sid)
    if st is None:
        return jsonify({"error": "Student not found"}), 404
    return jsonify(st)


@bp.route("/api/students/<int:sid>", methods=["PATCH"])
def api_students_update(sid):
    if student_by_id(sid) is None:
        return jsonify({"error": "Student not found"}), 404
    data = request.get_json() or {}
    roll_no = (data.get("roll_no") or "").strip()
    name = (data.get("name") or "").strip()
    try:
        section_id = int(data.get("section_id", 0))
    except (TypeError, ValueError):
        section_id = 0
    if not roll_no or not name:
        return jsonify({"error": "Roll number and name are required"}), 400
    if not section_id or section_by_id(section_id) is None:
        return jsonify({"error": "Valid section is required"}), 400
    try:
        student_update(sid, roll_no=roll_no, name=name, section_id=section_id)
        _invalidate_dashboard_cache()
        return jsonify({"ok": True})
    except Exception as e:
        if "UNIQUE" in str(e) or "Duplicate" in str(e):
            return jsonify({"error": "A student with that roll number already exists in this section"}), 400
        raise


@bp.route("/api/students/<int:sid>", methods=["DELETE"])
def api_students_delete(sid):
    if student_by_id(sid) is None:
        return jsonify({"error": "Student not found"}), 404
    student_delete(sid)
    _invalidate_dashboard_cache()
    return jsonify({"ok": True})


@bp.route("/api/sections/<int:sid>/students", methods=["GET"])
def api_section_students(sid):
    """For Mark Attendance: students in section only (paginated)."""
    if section_by_id(sid) is None:
        return jsonify({"error": "Section not found"}), 404
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    per_page = min(100, max(1, per_page))
    students, total = students_by_section_paginated(sid, page=page, per_page=per_page)
    return jsonify({"students": students, "total": total, "page": page, "per_page": per_page})


# ---------------------------------------------------------------------------
# Mark Attendance
# ---------------------------------------------------------------------------

@bp.route("/api/attendance", methods=["GET"])
def api_attendance_get():
    date_str = (request.args.get("date") or "").strip()
    section_id = request.args.get("section_id", type=int)
    session = (request.args.get("session") or "").strip().lower()
    if not date_str or section_id is None or not session or session not in VALID_SESSIONS:
        return jsonify({"error": "date, section_id, and session (morning|afternoon) are required"}), 400
    if section_by_id(section_id) is None:
        return jsonify({"error": "Section not found"}), 404
    rows = attendance_get_by_date_section_session(date_str, section_id, session)
    return jsonify({"date": date_str, "section_id": section_id, "session": session, "students": rows})


@bp.route("/api/attendance", methods=["POST"])
def api_attendance_mark():
    data = request.get_json() or {}
    date_str = (data.get("date") or "").strip()
    try:
        section_id = int(data.get("section_id", 0))
    except (TypeError, ValueError):
        section_id = 0
    session = (data.get("session") or "").strip().lower()
    absent_ids = data.get("absent_ids") if isinstance(data.get("absent_ids"), list) else []
    if not date_str or not section_id or not session or session not in VALID_SESSIONS:
        return jsonify({"error": "date, section_id, and session (morning|afternoon) are required"}), 400
    if section_by_id(section_id) is None:
        return jsonify({"error": "Section not found"}), 404
    attendance_set_absent_for_date_section_session(date_str, section_id, session, absent_ids)
    _invalidate_dashboard_cache()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Attendance Records (view/filter)
# ---------------------------------------------------------------------------

@bp.route("/api/attendance/records", methods=["GET"])
def api_attendance_records():
    section_id = request.args.get("section_id", type=int)
    date_str = (request.args.get("date") or "").strip()
    session = (request.args.get("session") or "").strip().lower()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)
    per_page = min(100, max(1, per_page))
    search = request.args.get("search", "").strip() or None
    if section_id is None or not date_str or not session or session not in VALID_SESSIONS:
        return jsonify({"error": "section_id, date, and session are required"}), 400
    if section_by_id(section_id) is None:
        return jsonify({"error": "Section not found"}), 404
    records, total = attendance_records_paginated(section_id, date_str, session, page=page, per_page=per_page, search=search)
    return jsonify({"records": records, "total": total, "page": page, "per_page": per_page})


@bp.route("/api/attendance/view", methods=["GET"])
def api_attendance_view():
    date_str = (request.args.get("date") or datetime.now().strftime("%Y-%m-%d")).strip()
    result = attendance_view_by_date(date_str)
    return jsonify({"date": date_str, "by_section_session": result})


# ---------------------------------------------------------------------------
# Analytics: low attendance
# ---------------------------------------------------------------------------

@bp.route("/api/analytics/low-attendance", methods=["GET"])
def api_analytics_low_attendance():
    """Students with attendance percentage below 75%. Uses last 30 days."""
    date_end = datetime.now()
    date_start = date_end - timedelta(days=30)
    date_end_str = date_end.strftime("%Y-%m-%d")
    date_start_str = date_start.strftime("%Y-%m-%d")
    rates = students_attendance_rates(date_start_str, date_end_str)
    low = [r for r in rates if (r.get("rate") or 1) < 0.75]
    data = [
        {"student_name": r.get("name", ""), "roll_no": r.get("roll_no", ""), "percentage": int((r.get("rate") or 0) * 100)}
        for r in low
    ]
    return jsonify({"success": True, "data": data})


# ---------------------------------------------------------------------------
# Reports: daily, weekly, student
# ---------------------------------------------------------------------------

@bp.route("/api/reports/daily", methods=["GET"])
def api_reports_daily():
    """GET /api/reports/daily?date=YYYY-MM-DD"""
    date_str = (request.args.get("date") or datetime.now().strftime("%Y-%m-%d")).strip()[:10]
    result = report_daily(date_str)
    return jsonify(result)


@bp.route("/api/reports/weekly", methods=["GET"])
def api_reports_weekly():
    """Last 7 days attendance summary."""
    today = datetime.now()
    total_present = 0
    total_absent = 0
    by_day = []
    for i in range(7):
        d = today - timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        view = attendance_view_by_date(date_str)
        day_present = sum(r.get("present", 0) for r in view)
        day_absent = sum(r.get("absent", 0) for r in view)
        total_present += day_present
        total_absent += day_absent
        by_day.append({"date": date_str, "present": day_present, "absent": day_absent})
    return jsonify({
        "period": "last_7_days",
        "total_present": total_present,
        "total_absent": total_absent,
        "total_students": total_present + total_absent,
        "attendance_percentage": round(total_present / (total_present + total_absent) * 100, 1) if (total_present + total_absent) else 0,
        "by_day": by_day,
    })


@bp.route("/api/reports/student/<int:student_id>", methods=["GET"])
def api_reports_student(student_id):
    """Student attendance report: total_classes, present, absent, percentage."""
    result = report_student(student_id)
    if result is None:
        return jsonify({"error": "Student not found"}), 404
    return jsonify(result)


# ---------------------------------------------------------------------------
# Email report (absentees)
# ---------------------------------------------------------------------------

def _validate_smtp_credentials(c=None):
    """Try SMTP login. Returns (True, None) if OK, (False, error_message) otherwise."""
    if c is None:
        from config import get_mail_config
        c = get_mail_config()
    if not c.get("server") or not c.get("username") or not c.get("password"):
        return False, "Mail server, username, and password are required."
    try:
        with smtplib.SMTP(c["server"], c["port"], timeout=15) as server:
            if c.get("use_tls"):
                server.starttls()
            server.login(c["username"], c["password"])
        return True, None
    except Exception as e:
        err = str(e).strip().lower()
        # Gmail rejects normal password with these messages
        if any(x in err for x in ("535", "534", "application-specific", "app password", "authentication failed", "username and password not accepted", "invalid credentials")):
            return False, (
                "Gmail does not accept your normal password. You must use an App Password. "
                "Steps: 1) Turn on 2-Step Verification in your Google Account. "
                "2) Go to https://myaccount.google.com/apppasswords and create an App Password for 'Mail'. "
                "3) Use that 16-character password here (not your Gmail login password)."
            )
        return False, str(e).strip() or "Connection failed"


def _send_email(to_email, subject, body_text):
    """Send a plain-text email. Returns (True, None) on success, (False, error_message) on failure."""
    from config import is_email_configured, get_mail_config
    if not is_email_configured():
        return False, "Email is not configured. Set mail and password in Settings."
    c = get_mail_config()
    to_email = (to_email or "").strip()
    if not to_email or "@" not in to_email:
        return False, "Invalid recipient email."
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = c["from_addr"] or c["username"]
        msg["To"] = to_email
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        with smtplib.SMTP(c["server"], c["port"]) as server:
            if c["use_tls"]:
                server.starttls()
            server.login(c["username"], c["password"])
            server.sendmail(msg["From"], to_email, msg.as_string())
        return True, None
    except Exception as e:
        logger.exception("send_email failed")
        return False, str(e)


def _build_absentees_report_for_date(date_str, section, session):
    """Get absentees for one date/section/session. section: name or 'ALL'. session: 'morning' or 'afternoon' or 'all'.
    Returns list of dicts with section_name, session, roll_no, name (or roll_no, name for single section)."""
    section = (section or "ALL").strip()
    session = (session or "all").strip().lower()
    if section.upper() == "ALL" and session == "all":
        rows = attendance_absent_today_all_sections(date_str)
        return rows
    if section.upper() == "ALL" and session in ("morning", "afternoon"):
        sections = sections_list()
        out = []
        for sec in sections:
            for a in attendance_absent_on_date_section_by_name(date_str, sec["name"], session):
                out.append({"section_name": sec["name"], "session": session, "roll_no": a["roll_no"], "name": a["name"]})
        return out
    sec = section_by_name_insensitive(section) if section.upper() != "ALL" else None
    if not sec:
        return []
    if session == "all":
        out = []
        for sess in VALID_SESSIONS:
            for a in attendance_absent_on_date_section_by_name(date_str, sec["name"], sess):
                out.append({"section_name": sec["name"], "session": sess, "roll_no": a["roll_no"], "name": a["name"]})
        return out
    rows = attendance_absent_on_date_section_by_name(date_str, sec["name"], session)
    return [{"section_name": sec["name"], "session": session, "roll_no": r["roll_no"], "name": r["name"]} for r in rows]


def _handle_send_absentees_email(params, report_email):
    """Build absentees report and send to report_email. Returns response text for the user."""
    section = (params.get("section") or "").strip() or None
    session_val = (params.get("session") or "").strip().lower() or None
    if session_val in ("", "null"):
        session_val = None
    if section and section.upper() == "ALL":
        section = "ALL"
    last_n_days = params.get("last_n_days")
    if last_n_days is not None:
        try:
            last_n_days = int(last_n_days)
            last_n_days = min(14, max(1, last_n_days))
        except (TypeError, ValueError):
            last_n_days = 1
    else:
        last_n_days = 1

    if not report_email or not (report_email or "").strip():
        return "Please set your **report recipient email** in **Settings** (Report recipient email), then try again."

    report_email = report_email.strip()
    if "@" not in report_email:
        return "Please set a valid email address in Settings."

    if section is None or section == "" or (isinstance(section, str) and section.strip().lower() in ("null", "")):
        return "Which **section** do you want the absentees report for? (e.g. *ECE A*, or *all sections*). Reply with the section name."
    if session_val is None or session_val == "" or session_val not in ("morning", "afternoon", "all"):
        return "Which **session** do you want? (*morning* or *afternoon*). Reply with morning or afternoon."

    today = datetime.now()
    dates_to_use = []
    if last_n_days and last_n_days > 1:
        for i in range(last_n_days):
            d = today - timedelta(days=i)
            dates_to_use.append(d.strftime("%Y-%m-%d"))
    else:
        dates_to_use = [today.strftime("%Y-%m-%d")]

    from config import is_email_configured
    if not is_email_configured():
        return "Email sending is not configured. Set mail server, username, and password in **Settings** → **Email (SMTP)** (or in .env)."

    lines = ["Absentees Report – AI Attendance", "=" * 40, ""]
    for date_str in dates_to_use:
        rows = _build_absentees_report_for_date(date_str, section, session_val)
        lines.append(f"Date: {date_str}  |  Section: {section}  |  Session: {session_val}")
        lines.append("-" * 40)
        if not rows:
            lines.append("(No absentees recorded)")
        else:
            for r in rows:
                sn = r.get("section_name", "")
                sess = r.get("session", "")
                lines.append(f"  {r.get('roll_no', '')}  {r.get('name', '')}  {sn}  {sess}")
        lines.append("")

    body = "\n".join(lines)
    subject = f"Absentees report – {section} – {dates_to_use[0]}" + (f" (last {len(dates_to_use)} days)" if len(dates_to_use) > 1 else "")
    ok, err = _send_email(report_email, subject, body)
    if ok:
        return f"Report sent to **{report_email}** for {section}, {session_val}" + (f" (last {len(dates_to_use)} days)." if len(dates_to_use) > 1 else ".")
    return f"Could not send email: {err}"


@bp.route("/api/settings/mail", methods=["GET"])
def api_get_mail_settings():
    """Return mail email and whether password is set (simple form: mail + password only)."""
    from config import get_mail_config
    c = get_mail_config()
    return jsonify({
        "mail_username": c["username"],
        "password_set": bool(c["password"]),
    })


@bp.route("/api/settings/mail", methods=["POST"])
def api_save_mail_settings():
    """Save mail (email) + password. Uses Gmail SMTP. Validates credentials and sends one demo email on success."""
    from models import set_mail_settings_from_db
    data = request.get_json() or {}
    username = (data.get("mail_username") or data.get("mail") or "").strip()
    password = (data.get("mail_password") or data.get("password") or "").strip() or None
    if not username or "@" not in username:
        return jsonify({"ok": False, "error": "Enter a valid email address."}), 400
    if not password:
        return jsonify({"ok": False, "error": "Enter your mail password (for Gmail use an App Password)."}), 400
    # Fixed Gmail SMTP
    set_mail_settings_from_db(
        server="smtp.gmail.com",
        port=587,
        use_tls=True,
        username=username,
        password=password,
        from_addr=username,
    )
    from config import get_mail_config
    c = get_mail_config()
    credentials_ok, err_msg = _validate_smtp_credentials(c)
    if not credentials_ok:
        return jsonify({
            "ok": False,
            "error": "Credentials incorrect. " + (err_msg or "Check email and password."),
            "credentials_ok": False,
        }), 400
    # Send one demo email to the same address
    demo_sent = False
    body = "This is a demo email from AI Attendance.\n\nYour email and password are correct. You can now send reports and get AI answers by email.\n\n— Attendance Management System"
    ok_send, _ = _send_email(username, "AI Attendance – Demo Email", body)
    if ok_send:
        demo_sent = True
    return jsonify({
        "ok": True,
        "message": "Credentials correct. " + ("Demo email sent to your inbox." if demo_sent else "Demo email could not be sent."),
        "credentials_ok": True,
        "demo_sent": demo_sent,
    })


@bp.route("/api/chat/email-reply", methods=["POST"])
def api_email_reply():
    """Send the AI reply text to the user's email (e.g. 'Email me this reply')."""
    from config import is_email_configured
    data = request.get_json() or {}
    to_email = (data.get("to_email") or data.get("email") or "").strip()
    reply_text = (data.get("reply_text") or "").strip()
    subject = (data.get("subject") or "AI Attendance – Reply").strip()
    if not to_email or "@" not in to_email:
        return jsonify({"ok": False, "error": "Provide a valid email address."}), 400
    if not reply_text:
        return jsonify({"ok": False, "error": "No reply text to send."}), 400
    if not is_email_configured():
        return jsonify({"ok": False, "error": "Email not configured. Set mail and password in Settings."}), 503
    ok, err = _send_email(to_email, subject, reply_text)
    if ok:
        return jsonify({"ok": True, "message": "Reply sent to " + to_email})
    return jsonify({"ok": False, "error": err}), 500


@bp.route("/api/reports/send-demo-email", methods=["POST"])
def api_send_demo_email():
    """Send a single demo/test email to the given address. Use to verify MAIL_* config."""
    from config import is_email_configured
    data = request.get_json() or {}
    to_email = (data.get("email") or "").strip()
    if not to_email or "@" not in to_email:
        return jsonify({"ok": False, "error": "Provide a valid 'email' in the request body."}), 400
    from config import email_config_error_message
    if not is_email_configured():
        err_msg = email_config_error_message() or "Email not configured."
        return jsonify({"ok": False, "error": "Email not configured. " + err_msg}), 503
    body = "This is a demo email from AI Attendance.\n\nIf you received this, email sending is working.\n\n— Attendance Management System"
    subject = "AI Attendance – Demo Email"
    ok, err = _send_email(to_email, subject, body)
    if ok:
        return jsonify({"ok": True, "message": "Demo email sent to " + to_email})
    return jsonify({"ok": False, "error": err}), 500


# ---------------------------------------------------------------------------
# Chat (hybrid AI: intent engine → smart defaults → safe DB → AI formatting)
# ---------------------------------------------------------------------------

from config import CHAT_RATE_LIMIT_PER_MINUTE, CHAT_DAILY_CAP

_chat_request_times = {}  # ip -> list of timestamps


def _chat_rate_limit_exceeded(ip):
    """Return True if this IP would exceed per-minute or daily cap."""
    now = time.time()
    one_min_ago = now - 60
    one_day_ago = now - 86400
    if ip not in _chat_request_times:
        _chat_request_times[ip] = []
    times = _chat_request_times[ip]
    times[:] = [t for t in times if t > one_day_ago]
    per_min = sum(1 for t in times if t > one_min_ago)
    daily = len(times)
    if per_min >= CHAT_RATE_LIMIT_PER_MINUTE or (CHAT_DAILY_CAP and daily >= CHAT_DAILY_CAP):
        return True
    times.append(now)
    return False


def _sanitize_question(q):
    """Sanitize user input: strip, length limit, no control chars."""
    if not q or not isinstance(q, str):
        return ""
    q = "".join(c for c in q.strip() if c.isprintable() or c in "\n\r\t")[:1000]
    return q.strip()


def _apply_smart_defaults(params):
    """Apply smart defaults: null date -> today (YYYY-MM-DD), null section/session -> ALL."""
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    out = dict(params)
    date_val = out.get("date")
    if not date_val or (isinstance(date_val, str) and date_val.strip().lower() in ("", "null", "today")):
        out["date"] = today
    elif isinstance(date_val, str) and date_val.strip().lower() == "yesterday":
        out["date"] = yesterday
    if out.get("section") is None or (isinstance(out.get("section"), str) and out["section"].strip().lower() in ("", "null")):
        out["section"] = "ALL"
    if out.get("session") is None or (isinstance(out.get("session"), str) and out["session"].strip().lower() in ("", "null")):
        out["session"] = "ALL"
    return out


def _handle_attendance_list(params):
    """Return list of present/absent for date, section, session (ALL supported)."""
    date_val = params.get("date")
    if not date_val or (isinstance(date_val, str) and date_val.strip().lower() in ("", "null", "today")):
        date_val = datetime.now().strftime("%Y-%m-%d")
    date_str = (date_val if isinstance(date_val, str) else datetime.now().strftime("%Y-%m-%d"))[:10]
    if date_str.lower() == "today":
        date_str = datetime.now().strftime("%Y-%m-%d")
    section = (params.get("section") or "ALL").strip()
    session = (params.get("session") or "ALL").strip().lower()
    status = (params.get("status") or "absent").strip().lower()

    if section.upper() == "ALL" and session == "all":
        if status == "absent":
            rows = attendance_absent_today_all_sections(date_str)
            # Deduplicate: same student can be absent in both morning and afternoon; show once with sessions
            by_student = {}
            for r in rows:
                key = (r.get("section_name"), r.get("roll_no"), r.get("name"))
                if key not in by_student:
                    by_student[key] = {"section_name": r.get("section_name"), "roll_no": r.get("roll_no"), "name": r.get("name"), "sessions": []}
                by_student[key]["sessions"].append(r.get("session", ""))
            list_out = []
            for v in by_student.values():
                v["session"] = ", ".join(sorted(s for s in v["sessions"] if s))
                del v["sessions"]
                list_out.append(v)
            list_out = list_out[:50]
            return {"date": date_str, "scope": "all sections, both sessions", "status": status, "count": len(list_out), "list": list_out, "truncated": len(by_student) > 50}
        else:
            rows = attendance_present_on_date_all_sections(date_str)
        list_out = rows[:50]
        return {"date": date_str, "scope": "all sections, both sessions", "status": status, "count": len(list_out), "list": list_out, "truncated": len(rows) > 50}

    if section.upper() == "ALL" and session in ("morning", "afternoon"):
        sections = sections_list()
        rows = []
        for sec in sections:
            if status == "absent":
                for a in attendance_absent_on_date_section_by_name(date_str, sec["name"], session):
                    rows.append({"section_name": sec["name"], "session": session, "roll_no": a["roll_no"], "name": a["name"]})
            else:
                for p in attendance_present_on_date_section_by_name(date_str, sec["name"], session):
                    rows.append({"section_name": sec["name"], "session": session, "roll_no": p["roll_no"], "name": p["name"]})
        list_out = rows[:50]
        return {"date": date_str, "scope": "all sections, " + session, "status": status, "count": len(list_out), "list": list_out, "truncated": len(rows) > 50}

    sec = section_by_name_insensitive(section) if section.upper() != "ALL" else None
    if not sec and section.upper() != "ALL":
        return {"error": "Section not found: " + section}
    if sec and session == "all":
        out = []
        for sess in VALID_SESSIONS:
            if status == "absent":
                for a in attendance_absent_on_date_section_by_name(date_str, sec["name"], sess):
                    out.append({"section_name": sec["name"], "session": sess, "roll_no": a["roll_no"], "name": a["name"]})
            else:
                for p in attendance_present_on_date_section_by_name(date_str, sec["name"], sess):
                    out.append({"section_name": sec["name"], "session": sess, "roll_no": p["roll_no"], "name": p["name"]})
        if status == "absent":
            by_student = {}
            for r in out:
                key = (r.get("roll_no"), r.get("name"))
                if key not in by_student:
                    by_student[key] = {"section_name": sec["name"], "roll_no": r["roll_no"], "name": r["name"], "sessions": []}
                by_student[key]["sessions"].append(r.get("session", ""))
            list_out = []
            for v in by_student.values():
                v["session"] = ", ".join(sorted(s for s in v["sessions"] if s))
                del v["sessions"]
                list_out.append(v)
            list_out = list_out[:50]
            return {"date": date_str, "scope": sec["name"] + ", both sessions", "status": status, "count": len(list_out), "list": list_out, "truncated": len(by_student) > 50}
        list_out = out[:50]
        return {"date": date_str, "scope": sec["name"] + ", both sessions", "status": status, "count": len(list_out), "list": list_out, "truncated": len(out) > 50}
    if sec and session in ("morning", "afternoon"):
        if status == "absent":
            rows = attendance_absent_on_date_section_by_name(date_str, sec["name"], session)
        else:
            rows = attendance_present_on_date_section_by_name(date_str, sec["name"], session)
        return {"date": date_str, "scope": sec["name"] + ", " + session, "status": status, "count": len(rows), "list": [{"roll_no": r["roll_no"], "name": r["name"]} for r in rows]}
    return {"date": date_str, "status": status, "count": 0, "list": []}


def _handle_attendance_summary(params):
    """Return total students, present count, absent count for date (and optional section/session)."""
    date_str = params.get("date") or datetime.now().strftime("%Y-%m-%d")
    section = (params.get("section") or "ALL").strip()
    session = (params.get("session") or "ALL").strip().lower()

    view = attendance_view_by_date(date_str)
    total_present = 0
    total_absent = 0
    by_section = []
    sec_lookup = section_by_name_insensitive(section) if section.upper() != "ALL" else None
    section_match = (sec_lookup["name"] if sec_lookup else None) if section.upper() != "ALL" else None
    for row in view:
        sec_name = row.get("section_name", "")
        sess = row.get("session", "")
        if section.upper() != "ALL":
            if section_match:
                if sec_name != section_match:
                    continue
            elif not (sec_name.upper().startswith(section.upper().strip())):
                continue
        if session != "all" and sess != session:
            continue
        total_present += row.get("present", 0)
        total_absent += row.get("absent", 0)
        by_section.append({"section": sec_name, "session": sess, "present": row.get("present", 0), "absent": row.get("absent", 0)})
    total_students = total_present + total_absent
    rate = (total_present / total_students * 100) if total_students else 0
    return {"date": date_str, "total_students": total_students, "present": total_present, "absent": total_absent, "attendance_rate_percent": round(rate, 1), "by_section_session": by_section[:20]}


def _handle_student_lookup(params):
    """Search by roll_no or student_name across all sections."""
    roll_no = params.get("roll_no")
    name = params.get("student_name")
    if not roll_no and not name:
        return {"error": "Please provide a roll number or student name."}
    students = student_find_by_roll_or_name(roll_no=(roll_no or "").strip() or None, name=(name or "").strip() or None)
    return {"query": {"roll_no": roll_no, "student_name": name}, "count": len(students), "students": students}


def _handle_student_list(params):
    """List students (roll_no, name, section_name). Optionally filter by section; include today's attendance status."""
    section = (params.get("section") or "ALL").strip()
    if section.upper() != "ALL" and section:
        sec = section_by_name_insensitive(section)
        if not sec:
            return {"error": "Section not found: " + section, "students": [], "count": 0}
        students, total = students_by_section_paginated(sec["id"], page=1, per_page=200)
        scope = sec["name"]
    else:
        students, total = students_list_paginated(section_id=None, page=1, per_page=200)
        scope = "all sections"
    out = []
    for s in students:
        sec_obj = section_by_id(s.get("section_id"))
        out.append({
            "roll_no": s.get("roll_no", ""),
            "name": s.get("name", ""),
            "section_name": sec_obj.get("name", "") if sec_obj else scope if section.upper() == "ALL" else scope,
        })
    today_str = datetime.now().strftime("%Y-%m-%d")
    absent_today = attendance_absent_today_all_sections(today_str)
    absent_set = set((a.get("roll_no"), a.get("section_name")) for a in absent_today)
    for s in out:
        s["status_today"] = "absent" if (s["roll_no"], s["section_name"]) in absent_set else "present"
    return {"date": today_str, "scope": scope, "count": len(out), "students": out, "truncated": total > 200}


def _handle_count_students(params):
    """Total or per-section student count."""
    section = (params.get("section") or "ALL").strip()
    if section.upper() == "ALL" or not section:
        n = student_count_by_section(None)
        return {"scope": "all sections", "count": n}
    sec = section_by_name_insensitive(section)
    if not sec:
        return {"error": "Section not found: " + section, "count": 0}
    n = student_count_by_section(sec["id"])
    return {"section": section, "count": n}


def _handle_section_lookup(params):
    """Which section is this student in? Search by name."""
    name = (params.get("student_name") or "").strip()
    if not name:
        return {"error": "Please provide a student name."}
    students = student_find_by_roll_or_name(name=name)
    if not students:
        return {"query": name, "found": False, "message": "No student found with that name."}
    return {"query": name, "found": True, "students": [{"name": s["name"], "roll_no": s["roll_no"], "section": s.get("section_name", "")} for s in students]}


def _handle_low_attendance(params):
    """Students below 75% attendance in a date range (default last 30 days)."""
    date_end = datetime.now()
    date_start = date_end - timedelta(days=30)
    date_end_str = date_end.strftime("%Y-%m-%d")
    date_start_str = date_start.strftime("%Y-%m-%d")
    rates = students_attendance_rates(date_start_str, date_end_str)
    low = [r for r in rates if r.get("rate", 1) < 0.75]
    return {"period": date_start_str + " to " + date_end_str, "threshold_percent": 75, "count": len(low), "students": low[:30], "truncated": len(low) > 30}


def _handle_section_most_absent(params):
    """Which section has the most absentees today? Returns section name and count."""
    date_str = params.get("date") or datetime.now().strftime("%Y-%m-%d")
    view = attendance_view_by_date(date_str)
    by_section = {}
    for row in view:
        sn = row.get("section_name", "")
        by_section[sn] = by_section.get(sn, 0) + (row.get("absent", 0) or 0)
    if not by_section:
        return {"date": date_str, "section_most_absent": None, "absent_count": 0, "by_section": []}
    best = max(by_section.items(), key=lambda x: x[1])
    by_section_list = [{"section": s, "absent": c} for s, c in sorted(by_section.items(), key=lambda x: -x[1])[:10]]
    return {"date": date_str, "section_most_absent": best[0], "absent_count": best[1], "by_section": by_section_list}


def _handle_attendance_week(params):
    """Total attendance for the last 7 days (this week)."""
    today = datetime.now()
    total_present = 0
    total_absent = 0
    by_day = []
    for i in range(7):
        d = today - timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        view = attendance_view_by_date(date_str)
        day_present = sum(r.get("present", 0) for r in view)
        day_absent = sum(r.get("absent", 0) for r in view)
        total_present += day_present
        total_absent += day_absent
        by_day.append({"date": date_str, "present": day_present, "absent": day_absent})
    return {"period": "last 7 days", "total_present": total_present, "total_absent": total_absent, "total_students": total_present + total_absent, "by_day": by_day}


def _handle_absent_more_than(params):
    """Students absent more than X days in a period (default this month)."""
    days = params.get("days")
    if days is None or (isinstance(days, (int, float)) and int(days) < 1):
        days = 3
    days = int(days)
    now = datetime.now()
    date_end_str = now.strftime("%Y-%m-%d")
    date_start = now.replace(day=1)
    date_start_str = date_start.strftime("%Y-%m-%d")
    students = students_absent_more_than_days(days, date_start_str, date_end_str)
    return {"period": date_start_str + " to " + date_end_str, "min_absent_days": days, "count": len(students), "students": students[:30], "truncated": len(students) > 30}


def _handle_attendance_insights(params):
    """Last 7 days: sections with highest absence, students absent more than 3 times. Summary for AI to format."""
    today = datetime.now()
    date_end_str = today.strftime("%Y-%m-%d")
    date_start = today - timedelta(days=6)
    date_start_str = date_start.strftime("%Y-%m-%d")
    view_by_section = {}
    for i in range(7):
        d = today - timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        view = attendance_view_by_date(date_str)
        for row in view:
            sn = row.get("section_name", "")
            view_by_section[sn] = view_by_section.get(sn, 0) + (row.get("absent", 0) or 0)
    sections_most_absent = sorted(view_by_section.items(), key=lambda x: -x[1])[:5]
    students_absent_3_plus = students_absent_more_than_days(3, date_start_str, date_end_str)
    return {
        "period": "last_7_days",
        "sections_highest_absence": [{"section": s, "absent_count": c} for s, c in sections_most_absent],
        "students_absent_more_than_3_times": [{"name": s.get("name"), "roll_no": s.get("roll_no"), "section_name": s.get("section_name"), "absent_days": s.get("absent_days")} for s in students_absent_3_plus[:20]],
        "summary": f"Last 7 days: {len(sections_most_absent)} sections with absences; {len(students_absent_3_plus)} students absent 3+ times.",
    }


@bp.route("/api/chat", methods=["POST"])
def api_chat():
    from ai_intent_engine import interpret_question
    from ai_service import format_result_with_ai, general_openai_response

    ip = request.remote_addr or "0.0.0.0"
    if _chat_rate_limit_exceeded(ip):
        logger.warning("chat: rate limit exceeded for IP %s", ip)
        return jsonify({"response": "AI usage limit reached. Please try later.", "error": "AI usage limit reached. Please try later."}), 429

    data = request.get_json() or {}
    question = _sanitize_question(data.get("question") or "")
    if not question:
        return jsonify({"response": "Please enter a question.", "error": "empty"}), 400

    try:
        intent_data = interpret_question(question)
    except Exception as e:
        logger.exception("chat: interpret_question failed")
        intent_data = {"intent": "general_question"}

    intent = (intent_data.get("intent") or "general_question").strip().lower()
    q_lower = (question or "").lower()
    q_stripped = (question or "").strip()
    words = q_lower.split()
    # Don't treat greetings or casual chat as section/session follow-ups (they were wrongly triggering "Which session?")
    _greetings = frozenset(("hi", "hello", "hey", "hlo", "hloo", "hlw", "hii", "helloo", "hellooo", "yo", "sup", "gm", "gn", "good morning", "good afternoon", "good evening", "thanks", "thank you", "ok", "okay", "bye"))
    is_greeting = q_stripped.lower() in _greetings or (len(words) == 1 and words[0] in _greetings)
    # If OpenAI returned general_question but the message looks like a section/session follow-up (e.g. "ECE A", "ece a morning"), treat as send_absentees_email so we don't call the API again
    question_like = any(w in q_lower for w in ("who", "how", "what", "which", "when", "today", "yesterday", "many", "summary", "list", "give", "show", "was", "were"))
    if intent == "general_question" and not is_greeting and len(q_stripped) <= 45 and "?" not in q_stripped and not question_like:
        if words == ["morning"] or words == ["afternoon"]:
            intent = "send_absentees_email"
            intent_data = {"intent": "send_absentees_email", "section": None, "session": "morning" if words == ["morning"] else "afternoon"}
        elif re.match(r"^all\s*sections?\s*(morning|afternoon)?\s*$", q_lower) or words == ["all"]:
            intent = "send_absentees_email"
            intent_data = {"intent": "send_absentees_email", "section": "ALL", "session": "morning" if "morning" in q_lower else "afternoon" if "afternoon" in q_lower else None}
        elif len(words) <= 5 and all(c.isalnum() or c.isspace() for c in q_lower):
            part = re.sub(r"\s*morning\s*|\s*afternoon\s*", " ", q_lower).strip()
            # Only treat as section if it looks like a section name (e.g. ECE A, CSE), not a single greeting-like word
            if part and part not in ("morning", "afternoon") and len(part) >= 2 and part not in _greetings:
                intent = "send_absentees_email"
                intent_data = {"intent": "send_absentees_email", "section": part.title(), "session": "morning" if "morning" in q_lower else "afternoon" if "afternoon" in q_lower else None}
    # Force date for attendance queries: if user didn't mention a date, use today (avoid wrong dates like 2023-10-04)
    date_mentioned = (
        "today" in q_lower or "yesterday" in q_lower or "last monday" in q_lower
        or any(m in q_lower for m in ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"))
        or re.search(r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4}", q_lower)  # e.g. 01-02-2026
    )
    if intent in ("attendance_list", "attendance_summary") and not date_mentioned:
        intent_data["date"] = None
    elif "today" in q_lower:
        intent_data["date"] = None
    elif "yesterday" in q_lower:
        intent_data["date"] = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    # If model returned an old date (e.g. 2023) and user didn't ask for a past date, use today
    if intent in ("attendance_list", "attendance_summary"):
        d = intent_data.get("date")
        if isinstance(d, str) and len(d) >= 4 and d[:4] < "2024" and not date_mentioned:
            intent_data["date"] = None
    params = _apply_smart_defaults(intent_data)
    report_email = (data.get("report_email") or "").strip() or None

    # Follow-up memory: use last context for "send them to my email"
    if intent == "send_absentees_email":
        sect = (intent_data.get("section") or "").strip() or None
        sess_val = (intent_data.get("session") or "").strip().lower() or None
        if (not sect or sect.lower() in ("null", "all")) and (not sess_val or sess_val == "all"):
            last_section = session.get("last_section")
            last_date = session.get("last_date")
            if last_section:
                intent_data["section"] = last_section
            if last_date:
                intent_data["date"] = last_date
            if not sess_val and last_section:
                intent_data["session"] = session.get("last_session") or "morning"

    try:
        if intent == "send_absentees_email":
            text = _handle_send_absentees_email(intent_data, report_email)
            return jsonify({"response": text})

        if intent == "attendance_list":
            result = _handle_attendance_list(params)
            # Store context for follow-up "send them to my email"
            if isinstance(result, dict) and result.get("status") == "absent" and result.get("list"):
                session["last_absentees"] = [{"name": r.get("name"), "roll_no": r.get("roll_no")} for r in result.get("list", [])[:50]]
                session["last_section"] = params.get("section") or "ALL"
                session["last_date"] = params.get("date") or datetime.now().strftime("%Y-%m-%d")
                session["last_session"] = params.get("session") or "ALL"
            text = format_result_with_ai(result)
            return jsonify({"response": text})

        if intent == "attendance_summary":
            result = _handle_attendance_summary(params)
            text = format_result_with_ai(result)
            return jsonify({"response": text})

        if intent == "student_lookup":
            result = _handle_student_lookup(params)
            text = format_result_with_ai(result)
            return jsonify({"response": text})

        if intent == "count_students":
            result = _handle_count_students(params)
            text = format_result_with_ai(result)
            return jsonify({"response": text})

        if intent == "student_list":
            result = _handle_student_list(params)
            text = format_result_with_ai(result)
            return jsonify({"response": text})

        if intent == "section_lookup":
            result = _handle_section_lookup(params)
            text = format_result_with_ai(result)
            return jsonify({"response": text})

        if intent == "low_attendance":
            result = _handle_low_attendance(params)
            text = format_result_with_ai(result)
            return jsonify({"response": text})

        if intent == "absent_more_than":
            result = _handle_absent_more_than(params)
            text = format_result_with_ai(result)
            return jsonify({"response": text})

        if intent == "section_most_absent":
            result = _handle_section_most_absent(params)
            text = format_result_with_ai(result)
            return jsonify({"response": text})

        if intent == "attendance_week":
            result = _handle_attendance_week(params)
            text = format_result_with_ai(result)
            return jsonify({"response": text})

        if intent == "attendance_insights":
            result = _handle_attendance_insights(params)
            text = format_result_with_ai(result)
            return jsonify({"response": text})

        # general_question or unknown
        text = general_openai_response(question)
        return jsonify({"response": text})

    except Exception as e:
        logger.exception("chat: handler failed for intent=%s", intent)
        return jsonify({"response": "Sorry, I couldn't process that. Please try again.", "error": str(e)}), 500
