# Review: Table Management Features

This file explains **what “table management features” means** in this project and **where they are implemented**. Use it when you are asked to “review the table management features file.”

---

## What “table management” means here

In this **Attendance Management System**, “table” is used in two ways:

1. **Database tables** — stored data: `sections`, `students`, `attendance`.
2. **UI tables** — on-screen tables: student list, mark-attendance grid, attendance records, and chat reply tables.

“Table management features” = everything that creates, reads, updates, or displays these (DB + UI).

---

## 1. Database tables (schema and access)

**File: `models.py`**

- **Schema:** Defines and creates three tables:
  - **sections** — id, name, created_at
  - **students** — id, roll_no, name, section_id, created_at (UNIQUE section_id + roll_no)
  - **attendance** — id, student_id, date, session, status, marked_at (UNIQUE student_id + date + session)
- **Management:** All CRUD and queries: create/update/delete sections and students, mark attendance, list absentees, student lookup, section lookup (including case-insensitive by name), etc.
- **Review focus:** `init_db()`, and functions like `section_by_name_insensitive`, `student_find_by_roll_or_name`, `attendance_absent_today_all_sections`, `students_attendance_rates`.

---

## 2. UI tables (admin pages)

**Files: `static/js/main.js`, `static/css/main.css`, `templates/main.html`**

- **Students page:** One table listing all students (Roll No, Name, Section) with sort and delete. Built in JS and styled with `.data-table`, `.students-table-wrap`.
- **Mark Attendance page:** Table of students (Roll No, Name, Status) for the chosen section/date/session; status can be toggled (Present/Absent). Uses `.data-table`, `#markTbody`.
- **Attendance Records page:** Table of records (Roll No, Name, Status) for the selected filters. Uses `.data-table`, `#recordsTbody`.
- **Review focus:** In `main.js` — building table HTML, filling `#studentsTbody`, `#markTbody`, `#recordsTbody`; in `main.css` — `.data-table`, `.data-table-wrap`, `.table-card`, `.tables-section`.

---

## 3. Chat reply tables (AI answers as tables)

**Files: `ai_service.py`, `static/js/main.js`, `static/css/main.css`**

- **Backend:** `ai_service.py` formats attendance/student lists as markdown tables (e.g. `| Roll No | Name | Section | Status |`) and uses `_structured_result_to_text()` so replies stay structured.
- **Frontend:** `main.js` detects markdown tables in chat messages and converts them to HTML `<table class="chat-table">`.
- **Styles:** `.chat-table`, `.chat-table-wrap` in `main.css` for chat message tables.
- **Review focus:** In `ai_service.py` — “(table):” labels and table formatting; in `main.js` — the block that parses `| ... |` lines and builds `chat-table` HTML.

---

## Quick reference: which file does what

| Feature                    | Primary file(s)        | What to review                          |
|---------------------------|------------------------|----------------------------------------|
| DB schema & table creation| `models.py`            | `init_db()`, table and index definitions |
| Section/student/attendance CRUD | `models.py`     | All `create_*`, `update_*`, `get_*`, `*_by_name*` |
| Students list (UI table)  | `static/js/main.js`    | Students table HTML and tbody fill      |
| Mark attendance (UI table)| `static/js/main.js`    | Mark-attendance table and status toggles|
| Attendance records (UI)   | `static/js/main.js`    | Records table and filters               |
| Chat reply as table       | `ai_service.py` + `main.js` | Table formatting + markdown→HTML   |
| Table styling             | `static/css/main.css`  | `.data-table`, `.chat-table`, etc.     |

---

## If you see an “error” about “table management features file”

- **“File not found” / “don’t understand which file”:**  
  This document (**TABLE_MANAGEMENT_FEATURES.md**) is the **table management features file**. Review this file and the files it points to above.

- **Bug in a table (wrong data, missing rows, wrong layout):**  
  Use the table above to pick the right file (e.g. DB → `models.py`, UI → `main.js`, chat tables → `ai_service.py` + `main.js`), then fix in that file.

- **Assignment says “review table management features”:**  
  Review this file first, then open the listed files and check the indicated sections.
