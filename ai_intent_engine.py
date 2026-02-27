"""
AI Intent Engine: interpret natural language into structured JSON for the chat backend.
Uses OpenAI gpt-4o-mini. No SQL; returns intent + parameters only.
"""
import re
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

ALLOWED_INTENTS = frozenset({
    "attendance_list",
    "attendance_summary",
    "student_lookup",
    "student_list",
    "count_students",
    "section_lookup",
    "low_attendance",
    "absent_more_than",
    "section_most_absent",
    "attendance_week",
    "general_question",
})

SYSTEM_PROMPT = """You convert user questions about attendance and students into structured JSON. Be strict: only output valid JSON.

IMPORTANT: Prefer attendance/student intents whenever the question mentions: attendance, absent, present, students, section, roll number, who didn't come, who skipped, missing, summary, count, how many, which section, low attendance, days absent, came, attended. Use general_question ONLY when clearly unrelated (e.g. weather, jokes).

Supported intents:
- attendance_list: who is present/absent (e.g. "who is absent today", "who didn't come", "who skipped", "missing students", "list absent", "who attended morning", "show attendance for today")
- attendance_summary: overall counts and rates (e.g. "attendance summary", "overall attendance", "whole school today", "how many students absent today", "attendance rate for ECE A today", "how many came today")
- student_lookup: find student by roll or name (e.g. "find student Rahul", "details of roll number 12", "show student X")
- student_list: list students (e.g. "list of all students", "list students in ECE A", "students in ECE A")
- count_students: how many students (e.g. "how many students in ECE A", "total students in system", "number of students in CSE")
- section_lookup: which section is a student in (e.g. "which section is Saketh in?")
- low_attendance: students below 75% attendance
- absent_more_than: students absent more than X days
- section_most_absent: which section has most absentees today
- attendance_week: total attendance for this week (last 7 days)
- general_question: only if clearly not about attendance/students/school

Return format (JSON only):
{"intent": "intent_name", "date": "YYYY-MM-DD or null", "section": "Section name or ALL or null", "session": "morning or afternoon or ALL or null", "status": "present or absent or null", "roll_no": "value or null", "student_name": "value or null", "days": number or null}

Date rules: Use YYYY-MM-DD. For "today" use actual today. For "yesterday" use yesterday's date. For "23 Feb" use 2026-02-23 (current year). For "01-02-2026" or "1-2-2026" use that date. For "last Monday" use the most recent Monday. Section: extract names like "ECE A", "ECE", "AIML", "CSE" when user says "in ECE A", "for ECE", etc. Session: "morning attendance" -> morning, "afternoon attendance" -> afternoon. Return JSON only, no explanation."""


def parse_date_from_question(question):
    """Parse question for a date; return YYYY-MM-DD or None. Supports today, yesterday, 23 Feb, 20 Feb, 01-02-2026, last Monday."""
    if not question or not isinstance(question, str):
        return None
    q = question.strip().lower()
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")

    if "today" in q:
        return today
    if "yesterday" in q:
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")
    if "this week" in q or "last week" in q:
        return today  # handler will use range

    # DD-MM-YYYY or D-M-YYYY or 01-02-2026
    m = re.search(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})\b", q)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y = y if y >= 100 else 2000 + y
        try:
            return datetime(y, mo, d).strftime("%Y-%m-%d")
        except ValueError:
            pass

    # "23 Feb", "Feb 23", "20 Feb"
    months = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
    for month_name, month_num in months.items():
        if month_name in q:
            day_m = re.search(r"\b(\d{1,2})\s*(?:st|nd|rd|th)?\s*(?:of\s+)?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", q, re.I) or re.search(r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2})\b", q, re.I)
            if day_m:
                try:
                    day = int(day_m.group(1))
                    return datetime(now.year, month_num, day).strftime("%Y-%m-%d")
                except ValueError:
                    pass
            # "23 feb" style
            day_m2 = re.search(r"\b(\d{1,2})\s+" + month_name, q)
            if day_m2:
                try:
                    return datetime(now.year, month_num, int(day_m2.group(1))).strftime("%Y-%m-%d")
                except ValueError:
                    pass

    # last Monday
    if "last monday" in q or "last Monday" in question:
        d = now
        while d.weekday() != 0:  # 0 = Monday
            d -= timedelta(days=1)
        return d.strftime("%Y-%m-%d")

    return None


def interpret_question(question):
    """
    Call OpenAI to get structured intent JSON. Safe parsing; returns dict with intent and params.
    On failure or non-attendance, returns {"intent": "general_question"}.
    """
    from config import get_openai_api_key, OPENAI_MODEL
    if not question or not isinstance(question, str):
        return {"intent": "general_question"}
    q = (question or "").strip()[:2000]
    if not q:
        return {"intent": "general_question"}

    api_key = get_openai_api_key()
    if not api_key:
        logger.info("chat: no OPENAI_API_KEY, using rule-based fallback for intent")
        return _rule_based_intent(q)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": q},
            ],
            temperature=0.1,
            max_tokens=300,
        )
        text = (response.choices[0].message.content or "").strip()
        parsed = _parse_intent_json(text)
        if parsed and parsed.get("intent") in ALLOWED_INTENTS:
            logger.info("chat: intent=%s params=%s", parsed.get("intent"), parsed)
            return parsed
    except Exception as e:
        logger.warning("chat: interpret_question OpenAI failed: %s", e)
    return _rule_based_intent(q)


def _parse_intent_json(text):
    """Extract JSON from model output; validate intent. Returns dict or None."""
    if not text:
        return None
    # Strip markdown code blocks if present
    text = text.strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
        if not isinstance(data, dict):
            return None
        intent = data.get("intent")
        if intent not in ALLOWED_INTENTS:
            return None
        # Normalize types
        if "days" in data and data["days"] is not None:
            try:
                data["days"] = int(data["days"])
            except (TypeError, ValueError):
                data["days"] = None
        for key in ("date", "section", "session", "status", "roll_no", "student_name"):
            if key in data and data[key] is not None and not isinstance(data[key], str):
                data[key] = str(data[key]) if data[key] else None
        return data
    except json.JSONDecodeError:
        return None


def _extract_section_from_question(question):
    """Extract section name from phrases like 'in ECE A', 'for ECE', 'in AIML yesterday'. Returns section name or None."""
    if not question:
        return None
    q = question.strip()
    # "in ECE A today", "in ECE A", "for ECE morning", "in AIML yesterday"
    m = re.search(r"\b(?:in|for)\s+([A-Za-z0-9]+(?:\s+[A-Za-z0-9]+)?)\s*(?:today|yesterday|morning|afternoon|class|attendance|$|\?)", q, re.I)
    if m:
        return m.group(1).strip()
    # "ECE A today", "ECE A morning" at start
    m2 = re.search(r"^([A-Za-z0-9]+(?:\s+[A-Za-z0-9]+)?)\s+(?:today|yesterday|morning|afternoon)", q, re.I)
    if m2:
        return m2.group(1).strip()
    return None


def _rule_based_intent(q_raw):
    """Fallback when OpenAI is not available: basic intent from keywords."""
    q = q_raw.lower()
    # Normalize typos and conversational phrases
    q = re.sub(r"\babscent\b", "absent", q)
    q = re.sub(r"\babsente?\b", "absent", q)
    q = re.sub(r"\babsentees?\b", "absent", q)
    q = re.sub(r"\bskipped\b", "absent", q)
    q = re.sub(r"\bmissing\b", "absent", q)
    q = re.sub(r"\bcame\b", "present", q)
    q = re.sub(r"\battended\b", "present", q)
    today = datetime.now().strftime("%Y-%m-%d")
    parsed_date = parse_date_from_question(q_raw) or today
    section = _extract_section_from_question(q_raw)
    out = {"intent": "general_question", "date": parsed_date, "section": section or "ALL", "session": "ALL", "status": None, "roll_no": None, "student_name": None, "days": None}

    # section_most_absent: which section has most absentees
    if "which section" in q and "most absent" in q:
        out["intent"] = "section_most_absent"
        out["date"] = today
        return out

    # attendance_week: this week, last week
    if "this week" in q or "last week" in q or ("attendance" in q and "week" in q):
        out["intent"] = "attendance_week"
        return out

    if "which section" in q and (" in" in q or " is " in q):
        out["intent"] = "section_lookup"
        for w in q.replace("?", "").split():
            if w not in ("which", "section", "is", "in", "the", "a", "an") and len(w) > 1:
                out["student_name"] = w
                break
        return out

    # find student X, show student X, details of roll number 12
    if "find student" in q or "show student" in q or ("details" in q and "roll" in q):
        out["intent"] = "student_lookup"
        if "roll" in q and ("number" in q or "no" in q):
            roll_m = re.search(r"\b(\d+|[a-z0-9]{2,10})\b", q_raw, re.I)
            if roll_m:
                out["roll_no"] = roll_m.group(1)
        else:
            # "find student Rahul" -> take word after "student"
            m = re.search(r"(?:find|show)\s+student\s+(\w+)", q_raw, re.I)
            if m:
                out["student_name"] = m.group(1).strip()
        out["date"] = today
        return out

    if "roll" in q and ("number" in q or "no" in q or "details" in q):
        out["intent"] = "student_lookup"
        roll_m = re.search(r"\b(\d+|[a-z0-9]{2,10})\b", q_raw, re.I)
        if roll_m:
            out["roll_no"] = roll_m.group(1)
        out["date"] = today
        return out

    if "how many students" in q:
        out["intent"] = "count_students"
        out["section"] = section or "ALL"
        out["date"] = today
        return out

    if "total students" in q or "number of students" in q:
        out["intent"] = "count_students"
        out["section"] = section or "ALL"
        return out

    if "absent" in q and ("day" in q or "days" in q or "more than" in q):
        out["intent"] = "absent_more_than"
        out["date"] = today
        dm = re.search(r"more than\s*(\d+)", q)
        out["days"] = int(dm.group(1)) if dm else 3
        return out

    if "low attendance" in q or "below 75" in q:
        out["intent"] = "low_attendance"
        out["date"] = today
        return out

    # attendance summary: summary, overall, whole school, how many absent today, how many came, attendance rate
    if "summary" in q or "overall" in q or "whole school" in q or ("how many" in q and ("absent" in q or "came" in q or "present" in q)) or "attendance rate" in q:
        out["intent"] = "attendance_summary"
        out["date"] = parsed_date
        out["section"] = section or "ALL"
        out["session"] = "morning" if "morning" in q and "afternoon" not in q else "afternoon" if "afternoon" in q else "ALL"
        return out

    # list students in ECE A / list of all students
    if "list" in q and "student" in q:
        out["intent"] = "student_list"
        out["section"] = section or "ALL"
        out["date"] = today
        return out
    if "students" in q and "in " in q and section:  # "students in ECE A"
        out["intent"] = "student_list"
        out["section"] = section
        out["date"] = today
        return out

    # attendance list: who absent/present, who didn't come, who skipped, missing students, morning/afternoon attendance
    if "absent" in q or "present" in q or "who" in q and ("didn't" in q or "did not" in q or "come" in q or "skip" in q) or "missing" in q or "attendance" in q and ("today" in q or "yesterday" in q or re.search(r"\d{1,2}\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", q, re.I)):
        out["intent"] = "attendance_list"
        out["date"] = parsed_date
        out["section"] = section or "ALL"
        out["session"] = "morning" if "morning" in q and "afternoon" not in q else "afternoon" if "afternoon" in q else "ALL"
        out["status"] = "absent" if "absent" in q or "didn't" in q or "did not" in q or "skip" in q or "missing" in q else "present"
        return out

    return out
