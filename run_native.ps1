<#
Run the RegMap backend NATIVELY on Windows (not in Docker).

Why: Docker Desktop containers run in a NAT'd WSL2 VM, so they can't get an IP on your physical
Wi-Fi/LAN and can't do proper host discovery. Running natively binds the app to this Windows host
(which IS on your LAN, e.g. 10.0.0.71), so SecureScan / Compliance Advisor scan your physical
network directly, "Discover environment" sees your real interfaces, and the app is reachable on
the LAN at http://<your-lan-ip>:<port>.

Usage (from the repo root):
    .\run_native.ps1                 # http://localhost:2500 , private/LAN scanning
    .\run_native.ps1 -AllowAny       # also allow scanning any target you enter (authorized use only)
    .\run_native.ps1 -Port 2600      # use a different port

Note: if the Docker container "RedMap" is bound to the same port, stop it first:
    docker stop RedMap
Native and container are two ways to run the SAME app; use native when you need physical scanning.
#>
param(
    [int]$Port = 2500,
    [string]$BindHost = "0.0.0.0",
    [switch]$AllowAny
)

$ErrorActionPreference = "Stop"
$repo = $PSScriptRoot
$venvPy = Join-Path $repo "venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) { throw "venv python not found at $venvPy" }

# Persist the verdict trail on the host (separate from the container's Docker volume).
$env:VERDICT_DB = Join-Path $repo "data\verdicts_native.db"
if ($AllowAny) { $env:SCAN_ALLOW_ANY = "1" } else { $env:SCAN_ALLOW_ANY = "0" }
# Keep AI triage LLM off by default (fast, no heavy model load) unless the user opts in elsewhere.
if (-not $env:AI_TRIAGE_LLM) { $env:AI_TRIAGE_LLM = "0" }

# Show the LAN IP(s) the app will be reachable on / scan from.
$ips = Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' -and $_.IPAddress -notlike '172.*' } |
    Select-Object -ExpandProperty IPAddress
Write-Host "== RegMap native ==" -ForegroundColor Cyan
Write-Host ("Physical LAN IP(s): {0}" -f ($ips -join ", "))
Write-Host ("Open:  http://localhost:{0}/   (and http://<lan-ip>:{0}/ on your network)" -f $Port)
Write-Host ("Scan authorization: SCAN_ALLOW_ANY={0}" -f $env:SCAN_ALLOW_ANY)
Write-Host "Ctrl+C to stop." -ForegroundColor DarkGray

# Run uvicorn from backend/ so the app's ../models, ../data relative paths resolve as in the image.
Push-Location (Join-Path $repo "backend")
try {
    & $venvPy -m uvicorn app:app --host $BindHost --port $Port
} finally {
    Pop-Location
}
