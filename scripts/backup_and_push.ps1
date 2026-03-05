# Daily backup and push to GitHub
# Run this script once per day (e.g. via Task Scheduler) to save DB and push to GitHub.
# Requires: Git configured, remote "origin" set, and push access.

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $ProjectRoot) { $ProjectRoot = (Get-Location).Path }

Set-Location $ProjectRoot

# 1. Run Python backup (creates backups/ai_system_YYYYMMDD_HHMMSS.db)
Write-Host "Running database backup..."
python -c "
from utils.backup_db import run_backup
ok, path = run_backup()
if not ok:
    print('Backup failed:', path)
    exit(1)
print('Backup saved:', path)
"

if ($LASTEXITCODE -ne 0) {
    Write-Host "Backup failed. Aborting." -ForegroundColor Red
    exit 1
}

# 2. Copy latest backup to data/ for Git (so we push one file)
$BackupsDir = Join-Path $ProjectRoot "backups"
$DataDir = Join-Path $ProjectRoot "data"
$LatestDest = Join-Path $DataDir "ai_system_latest.db"

if (-not (Test-Path $BackupsDir)) {
    Write-Host "No backups folder. Skipping copy." -ForegroundColor Yellow
    exit 0
}

$latest = Get-ChildItem -Path $BackupsDir -Filter "ai_system_*.db" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $latest) {
    Write-Host "No backup file found. Skipping push." -ForegroundColor Yellow
    exit 0
}

New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
Copy-Item -Path $latest.FullName -Destination $LatestDest -Force
Write-Host "Copied latest backup to data/ai_system_latest.db"

# 3. Git add, commit, push
$dateStr = Get-Date -Format "yyyy-MM-dd"
$commitMsg = "Daily backup $dateStr"

git add data/ai_system_latest.db
$status = git status --short data/
if (-not $status) {
    Write-Host "No changes to data file. Nothing to commit."
    exit 0
}
git commit -m $commitMsg
git push origin main
Write-Host "Pushed to GitHub (main)." -ForegroundColor Green
