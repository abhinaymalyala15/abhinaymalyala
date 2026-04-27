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

### Why your data disappears on deploy/refresh

On **Render**, the app runs on a **temporary disk**. Every time you:
- **Redeploy** (push to GitHub, or click Deploy),
- **Restart** the service,

the disk is wiped and a new one is created. So `ai_system.db` is lost and your data is reset.

**Fix: use a Persistent Disk** so the database file is stored on a disk that survives restarts and redeploys.

### Steps: Add a Persistent Disk on Render (data saved across deploys)

1. In **Render Dashboard**, open your **Web Service** (ai-attendance-management).
2. Go to **Disks** in the left sidebar (or the **Disks** tab).
3. Click **Add Disk**.
4. Set:
   - **Name:** e.g. `attendance-data`
   - **Mount Path:** `/data`
   - **Size:** 1 GB is enough.
5. Save. Render will redeploy the service with the disk attached.
6. In **Environment** (same service), add:
   - **Key:** `SQLITE_PATH`
   - **Value:** `/data/ai_system.db`
7. Save. Render will redeploy again.

After this, the app will create and use `ai_system.db` on the persistent disk. Your sections, students, and attendance **will persist** across deploys and restarts.

**Check:** After deploy, in the service **Logs** you should see a line like: `Database: /data/ai_system.db`.

### If you don’t use a Persistent Disk

- Data will keep disappearing on every deploy or restart.
- For a free option without Persistent Disk, you’d need to use an external database (e.g. Render PostgreSQL or a free MySQL host) and set `USE_SQLITE=0` plus the DB env vars (the app supports MySQL).

After you push to GitHub, Render will redeploy automatically if auto-deploy is on.

---

## 3. Quick reference

| Goal                    | Action |
|-------------------------|--------|
| Save data daily         | Run `.\scripts\backup_and_push.ps1` (or schedule it) |
| Push data to GitHub     | Same script: it commits and pushes `data/ai_system_latest.db` |
| Deploy / run on Render  | Connect repo to Render, set env vars, **add Persistent Disk** and set `SQLITE_PATH=/data/ai_system.db` so data is not cleared on deploy |
