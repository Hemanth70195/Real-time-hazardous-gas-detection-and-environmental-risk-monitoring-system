# SafeEdge HazardGuard Launch Script
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (Test-Path $venvPython) {
    Write-Host "Starting SafeEdge HazardGuard via .venv..." -ForegroundColor Green
    & $venvPython -m streamlit run app.py
} else {
    Write-Host "Starting SafeEdge HazardGuard via system streamlit..." -ForegroundColor Cyan
    streamlit run app.py
}
