"""
AI service layer for Attendance Management System.
Hybrid: rule-based classification + extraction; OpenAI only for formatting and general Q&A.
Billing-safe: max_tokens=400, temperature=0.2. No full DB sent to AI.
"""
import re
import json
from datetime import datetime


# ---------------------------------------------------------------------------
# Classification (rule-based, no API call)
# ---------------------------------------------------------------------------

def classify_question(question):
    """
    Classify user question. Returns one of:
    - "attendance_query"
    - "student_query"
    - "general_question"
    """
    if not question or not isinstance(question, str):
        return "general_question"
    q = question.strip().lower()
    if not q:
        return "general_question"
    # Normalize typos so "abscent" / "absentees" etc. are understood
    q = re.sub(r"\babscent\b", "absent", q)
    q = re.sub(r"\babsente?\b", "absent", q)
    q = re.sub(r"\babsentees?\b", "absent", q)

    attendance_keywords = (
        "absent", "present", "attendance", "who is", "how many", "marked",
        "today", "yesterday", "morning", "afternoon", "session", "section",
        "roll", "attended", "missing", "list", "show"
    )
    student_keywords = ("student", "students", "roll no", "roll number", "section", "count")

    has_attendance = any(k in q for k in ("absent", "present", "attendance", "marked", "who is", "how many"))
    has_date_or_session = any(k in q for k in ("today", "yesterday", "morning", "afternoon", "february", "january", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december")) or re.search(r"\d{4}-\d{2}-\d{2}", q) or re.search(r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", q, re.I)
    if has_attendance or (has_date_or_session and ("section" in q or "who" in q or "list" in q)):
        return "attendance_query"

    if "how many students" in q or ("student" in q and ("section" in q or "total" in q)):
        return "student_query"

    return "general_question"


# ---------------------------------------------------------------------------
# Parameter extraction (rule-based, no API call). Safe: no SQL from AI.
# ---------------------------------------------------------------------------

_MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}


def _parse_date_from_question(question):
    """Extract date as YYYY-MM-DD from question. Uses today if 'today' or no date found."""
    q = question.lower().strip()
    today = datetime.now().strftime("%Y-%m-%d")
    if "today" in q:
        return today
    match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", q)
    if match:
        return match.group(0)
    year = datetime.now().year
    for name, month in sorted(_MONTHS.items(), key=lambda x: -len(x[0])):
        if name in q:
            day_m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\b", q)
            if day_m:
                try:
                    d = datetime(year, month, int(day_m.group(1)))
                    return d.strftime("%Y-%m-%d")
                except ValueError:
                    pass
    return today if "today" in q else None


def _normalize_question_for_parsing(question):
    """Normalize typos and phrases so natural language is understood (e.g. abscent -> absent, both sessions)."""
    if not question or not isinstance(question, str):
        return ""
    q = question.strip().lower()
    # Common typos (abscent, absentee, absentees -> absent)
    q = re.sub(r"\babscent\b", "absent", q)
    q = re.sub(r"\babsente?\b", "absent", q)
    q = re.sub(r"\babsentees?\b", "absent", q)
    q = re.sub(r"\bpresente?\b", "present", q)
    q = re.sub(r"\batendance\b", "attendance", q)
    return q


def extract_parameters(question, section_names):
    """
    Extract structured parameters from question. section_names = list of section names from DB.
    Returns dict: section (str|null), date (str|null), session ("morning"|"afternoon"|null),
    status ("present"|"absent"|null), student_name (str|null).
    Validated and sanitized; no user input passed to SQL directly (section matched to list).
    """
    q = _normalize_question_for_parsing(question)
    section_names = [s for s in (section_names or []) if s and isinstance(s, str)]
    out = {
        "section": None,
        "date": None,
        "session": None,
        "status": None,
        "student_name": None,
    }

    # "Both sessions" / "all sessions" = we want all data, leave session None so backend uses all-sessions query
    if re.search(r"\b(both|all)\s*sessions?\b", q) or "morning and afternoon" in q or "morning & afternoon" in q:
        out["session"] = None
    # Single session
    elif "afternoon" in q:
        out["session"] = "afternoon"
    elif "morning" in q:
        out["session"] = "morning"

    # Status (after typo normalization, so "abscent" -> "absent")
    if "absent" in q:
        out["status"] = "absent"
    elif "present" in q:
        out["status"] = "present"

    # Date
    out["date"] = _parse_date_from_question(question or "")

    # Section: only from allowed list (no raw user input to DB)
    for name in section_names:
        if name.lower() in q or name.replace(" ", "").lower() in q.replace(" ", ""):
            out["section"] = name
            break

    return out


# ---------------------------------------------------------------------------
# Format attendance response (OpenAI, single call, billing-safe)
# ---------------------------------------------------------------------------

def format_attendance_response(summary):
    """
    Use OpenAI to turn a short summary into a professional, readable response.
    summary: plain text (e.g. "Section ECE A, 2026-02-22, afternoon. Absent: 3 - Alice, Bob, Charlie.").
    Returns formatted string. Raises on API error.
    """
    from config import get_openai_api_key, OPENAI_MODEL, OPENAI_MAX_TOKENS, OPENAI_TEMPERATURE
    api_key = get_openai_api_key()
    if not api_key:
        return summary or "No data."

    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are an attendance assistant. Rewrite the given attendance summary into a clear, professional, concise reply. Do not add information not in the summary. Use short paragraphs or bullet points if helpful. No SQL, no code."
            },
            {"role": "user", "content": (summary or "No attendance data.")[:3000]}
        ],
        max_tokens=OPENAI_MAX_TOKENS,
        temperature=OPENAI_TEMPERATURE,
    )
    reply = (response.choices[0].message.content or "").strip()
    return reply if reply else summary


def general_openai_response(question):
    """General question: single OpenAI call. Billing-safe."""
    from config import get_openai_api_key, OPENAI_MODEL, OPENAI_MAX_TOKENS, OPENAI_TEMPERATURE
    api_key = get_openai_api_key()
    if not api_key:
        return (
            "**AI assistant is currently offline.**\n\n"
            "To enable AI responses:\n"
            "1. Open the `.env` file in your project root.\n"
            "2. Set: `OPENAI_API_KEY=your_key`\n"
            "3. Save the file and restart the Flask server.\n\n"
            "You can still ask attendance-related questions; I’ll answer from the database."
        )

    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant. Answer the user's question in a brief, friendly way. For general questions (e.g. 'what is AI?', 'how are you?') answer normally. For attendance, students, or sections you can mention you help with that too. Be concise. No SQL or code."
            },
            {"role": "user", "content": (question or "")[:2000]}
        ],
        max_tokens=OPENAI_MAX_TOKENS,
        temperature=0.2,
    )
    return (response.choices[0].message.content or "").strip()


def _structured_result_to_text(structured_result):
    """Convert API result dict to clear, structured plain text (no AI). Keeps answers relevant and on-topic."""
    import json
    if isinstance(structured_result, str):
        return structured_result
    if isinstance(structured_result, dict):
        if structured_result.get("error"):
            return "**Error:** " + str(structured_result["error"])
        lines = []
        from datetime import datetime as _dt
        today_str = _dt.now().strftime("%Y-%m-%d")
        # Summary-style keys first; show actual today for date when value is "today" or already today
        for key in ("date", "scope", "period", "section", "total_students", "present", "absent", "count", "threshold_percent", "min_absent_days", "attendance_rate_percent", "section_most_absent", "absent_count", "total_present", "total_absent"):
            if key in structured_result and structured_result[key] is not None:
                label = key.replace("_", " ").title()
                val = structured_result[key]
                if key == "date" and isinstance(val, str) and (val.strip().lower() == "today" or val.strip() == today_str):
                    val = today_str
                if key == "attendance_rate_percent":
                    label = "Attendance rate (%)"
                lines.append("**%s:** %s" % (label, val))
        if "query" in structured_result and "found" in structured_result:
            q = structured_result["query"]
            if isinstance(q, dict):
                q = " | ".join("%s=%s" % (k, v) for k, v in q.items() if v)
            lines.append("**Query:** %s | **Found:** %s" % (q, "Yes" if structured_result["found"] else "No"))
        if structured_result.get("message"):
            lines.append(structured_result["message"])
        # by_section table (section_most_absent)
        if structured_result.get("by_section") and isinstance(structured_result["by_section"], list):
            lines.append("\n**By section (absent count):**")
            lines.append("| Section | Absent |")
            lines.append("| --- | --- |")
            for row in structured_result["by_section"][:15]:
                lines.append("| %s | %s |" % (row.get("section", ""), row.get("absent", 0)))
        # by_day table (attendance_week)
        if structured_result.get("by_day") and isinstance(structured_result["by_day"], list):
            lines.append("\n**By day:**")
            lines.append("| Date | Present | Absent |")
            lines.append("| --- | --- | --- |")
            for row in structured_result["by_day"][:10]:
                lines.append("| %s | %s | %s |" % (row.get("date", ""), row.get("present", 0), row.get("absent", 0)))
        # List: students / list
        for list_key in ("students", "list", "by_section_session"):
            if list_key not in structured_result or not structured_result[list_key]:
                continue
            items = structured_result[list_key]
            label = list_key.replace("_", " ").title()
            if list_key == "by_section_session":
                lines.append("\n**By section / session:**")
                for row in items[:15]:
                    lines.append("  • %s — %s: Present %s, Absent %s" % (row.get("section", ""), row.get("session", ""), row.get("present", 0), row.get("absent", 0)))
            elif isinstance(items, list) and items and isinstance(items[0], dict):
                # Format as table when we have roll_no, name, and optionally section/session or status_today
                show_as_table = "roll_no" in items[0] and "name" in items[0]
                has_status_today = any("status_today" in s for s in items[:3])
                if show_as_table and has_status_today:
                    lines.append("\n**%s (table):**" % label)
                    lines.append("| Roll No | Name | Section | Status (today) |")
                    lines.append("| --- | --- | --- | --- |")
                    for s in items[:50]:
                        lines.append("| %s | %s | %s | %s |" % (s.get("roll_no", ""), s.get("name", ""), s.get("section_name", ""), s.get("status_today", "")))
                elif show_as_table and any("section_name" in s or "session" in s for s in items[:3]):
                    # Absent list table: Name | Roll No | Session absent (morning/afternoon)
                    lines.append("\n**%s**" % label)
                    lines.append("| Name | Roll No | Session absent (morning/afternoon) |")
                    lines.append("| --- | --- | --- |")
                    for s in items[:50]:
                        nm = s.get("name", "")
                        rn = s.get("roll_no", "")
                        sess = s.get("session", "") or "—"
                        lines.append("| %s | %s | %s |" % (nm, rn, sess))
                else:
                    lines.append("\n**%s:**" % label)
                    for i, s in enumerate(items[:25], 1):
                        if "name" in s and "roll_no" in s:
                            line = "  %d. %s (%s)" % (i, s.get("name", ""), s.get("roll_no", ""))
                            if s.get("section_name"):
                                line += " — %s" % s["section_name"]
                            if s.get("session"):
                                line += " — %s" % s["session"]
                            if "rate" in s and s["rate"] is not None:
                                line += " — %.0f%% attendance" % (s["rate"] * 100)
                            if "absent_days" in s:
                                line += " — %s days absent" % s["absent_days"]
                            lines.append(line)
                        elif "name" in s and "section" in s:
                            line = "  %d. %s (%s) — %s" % (i, s.get("name", ""), s.get("roll_no", ""), s.get("section", ""))
                            lines.append(line)
                        else:
                            lines.append("  %d. %s" % (i, json.dumps(s)[:80]))
            else:
                lines.append("\n**%s:** %s" % (label, items))
        if structured_result.get("truncated"):
            lines.append("\n(Showing first entries only.)")
        return "\n".join(lines) if lines else json.dumps(structured_result, indent=2)[:1500]
    return json.dumps(structured_result, indent=2)[:2000]


def format_result_with_ai(structured_result):
    """
    Format structured result: first build clear text, then optionally polish with OpenAI.
    Strict rule: AI must not add or change facts; only structure (bullets, spacing). If AI fails or adds fluff, use text only.
    """
    from config import get_openai_api_key, OPENAI_MODEL
    api_key = get_openai_api_key()
    text = _structured_result_to_text(structured_result)
    if not api_key:
        return text

    import json
    if not isinstance(structured_result, str):
        data_str = json.dumps(structured_result, indent=2)[:2500]
    else:
        data_str = (structured_result or "")[:2500]

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You ONLY reformat the given attendance/student data into a clear, structured reply. RULES: (1) Use exactly the information provided — do not add, remove, or change any fact. (2) Use bold labels (**Label:**), bullet points (-), and tables where appropriate. (3) No greetings, no 'Here is...', no extra commentary. (4) Keep dates as YYYY-MM-DD; do not replace with the word 'today'. (5) Keep the same facts and numbers. Output the structured text only."
                },
                {"role": "user", "content": "Format this data strictly (same facts, structured only):\n\n" + data_str}
            ],
            max_tokens=400,
            temperature=0.1,
        )
        reply = (response.choices[0].message.content or "").strip()
        if reply and len(reply) > 10:
            return reply
    except Exception:
        pass
    return text
