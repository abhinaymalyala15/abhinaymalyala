# Deploy & Daily Data Backup

## 1. Save data daily & push to GitHub

### Option A: Run the script daily (recommended)

From the **project root** (or run the script from anywhere; it finds the project):

```powershell
.\scripts\backup_and_push.ps1
```

What it does:

1. Runs the Python backup → creates `backups/ai_system_YYYYMMDD_HHMMSS.db`
2. Copies the latest backup to `data/ai_system_latest.db`
3. Commits and pushes `data/ai_system_latest.db` to GitHub (branch `main`)

**Schedule it (Windows Task Scheduler):**

1. Open Task Scheduler → Create Basic Task
2. Trigger: Daily, at a time you choose (e.g. 11:00 PM)
3. Action: Start a program  
   - Program: `powershell.exe`  
   - Arguments: `-ExecutionPolicy Bypass -File "C:\Users\USER\Desktop\ai attendence management system\scripts\backup_and_push.ps1"`
4. Start in: `C:\Users\USER\Desktop\ai attendence management system`

### Option B: Backup only (no push)

- Backup runs **automatically** when you start the app: if the last backup was more than 24 hours ago, it creates a new file in `backups/`.
- To run a backup manually without pushing:  
  `python -c "from utils.backup_db import run_backup; run_backup()"`

---

## 2. Run on Render

### Deploy from GitHub

1. Go to [Render](https://render.com) → Dashboard → New → Web Service
2. Connect your GitHub repo (`abhinaymalyala15/abhinaymalyala` or the one that contains this project)
3. Use the repo that has the attendance app; if it’s in a subfolder, set **Root Directory** to that folder
4. Render will use `render.yaml` if present, or set:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `gunicorn app:app`

### Environment variables (Render dashboard)

Add in the service → Environment:

| Key              | Value / note                                      |
|------------------|---------------------------------------------------|
| `OPENAI_API_KEY`| Your OpenAI API key                               |
| `SECRET_KEY`     | Long random string for Flask sessions             |
| `USE_SQLITE`     | `1` (default) or `0` if you use MySQL/PostgreSQL  |

Optional: `PORT` is set by Render; for email: `MAIL_SERVER`, `MAIL_USERNAME`, `MAIL_PASSWORD`, etc.

### Data persistence on Render

- Render’s filesystem is **ephemeral**: restarts/redeploys wipe the disk, so SQLite data is lost.
- Options:
  1. **Render Persistent Disk** (paid): mount a disk and set `SQLITE_PATH` to a path on that disk (e.g. `/data/ai_system.db`).
  2. **PostgreSQL on Render** (free tier): create a PostgreSQL service, then set `USE_SQLITE=0` and the MySQL-style env vars (or add a small adapter so the app uses the same `config` and `DATABASE_URL`). The app already supports MySQL; PostgreSQL would need a driver and possibly small config changes.

After you push to GitHub, Render will redeploy automatically if auto-deploy is on.

---

## 3. Quick reference

| Goal                    | Action |
|-------------------------|--------|
| Save data daily         | Run `.\scripts\backup_and_push.ps1` (or schedule it) |
| Push data to GitHub     | Same script: it commits and pushes `data/ai_system_latest.db` |
| Deploy / run on Render  | Connect repo to Render, set env vars, deploy; use persistent disk or PostgreSQL for production data |
