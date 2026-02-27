# Push all changes to GitHub
# Run this after you make changes: .\push.ps1 "your commit message"

param(
    [Parameter(Mandatory=$false)]
    [string]$Message = "Update project"
)

Set-Location $PSScriptRoot

git add .
$status = git status --short
if (-not $status) {
    Write-Host "Nothing to commit. Working tree clean."
    exit 0
}
git commit -m $Message
git push origin main
Write-Host "Done. Pushed to https://github.com/abhinaymalyala15/abhinaymalyala"