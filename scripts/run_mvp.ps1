param([int]$Port = 8000, [switch]$Install)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create virtual environment.' }
    $Install = $true
}
if ($Install) {
    & $pythonPath -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
Write-Host "Applicant: http://127.0.0.1:$Port/"
Write-Host "Staff:     http://127.0.0.1:$Port/staff"
Write-Host 'Press Ctrl+C to stop. Source ingestion runs at startup.'
& $pythonPath -m uvicorn src.main:app --host 127.0.0.1 --port $Port
