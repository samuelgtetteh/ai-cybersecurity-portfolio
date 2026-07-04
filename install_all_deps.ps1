# Run this from the ai-cybersecurity-portfolio root directory on a fresh machine.
# Creates the venv if missing, then installs every dependency used across the
# repo's applications (backend/, demo/, notebooks/), skipping anything already
# installed. Safe to re-run.

if (-not (Test-Path .\venv)) {
    Write-Host "[venv] Creating virtual environment..."
    python -m venv venv
} else {
    Write-Host "[venv] Already exists, skipping creation"
}

Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& .\venv\Scripts\Activate.ps1

python -m pip install --upgrade pip

# Requirements files for each application in this repo
$requirementFiles = @(
    "backend\requirements.txt",   # FastAPI RegMap service
    "demo\requirements.txt"       # Streamlit demo app
)

# Not captured in any requirements.txt but needed to run notebooks/*.ipynb
$notebookExtras = @(
    "jupyterlab",
    "ipykernel",
    "tqdm"
)

$allRequirements = New-Object System.Collections.Generic.List[string]

foreach ($file in $requirementFiles) {
    if (Test-Path $file) {
        Get-Content $file | Where-Object { $_.Trim() -ne "" } | ForEach-Object { $allRequirements.Add($_) }
    } else {
        Write-Host "[warn] $file not found, skipping"
    }
}
foreach ($pkg in $notebookExtras) { $allRequirements.Add($pkg) }

# De-dupe by bare package name (case-insensitive), keeping the first spec seen
$seen = @{}
$toInstall = @()
foreach ($req in $allRequirements) {
    $pkgName = ($req -split '[=<>!~\[]')[0].Trim()
    $key = $pkgName.ToLower()
    if (-not $seen.ContainsKey($key)) {
        $seen[$key] = $true
        $toInstall += [PSCustomObject]@{ Name = $pkgName; Spec = $req }
    }
}

foreach ($item in $toInstall) {
    python -m pip show $item.Name 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[skip] $($item.Name) already installed"
    } else {
        Write-Host "[install] $($item.Spec)"
        python -m pip install $item.Spec
    }
}

# Sanity check - one import per application
Write-Host "`n--- Sanity check ---"
python -c "import fastapi, uvicorn; print('backend  OK - fastapi', fastapi.__version__, '/ uvicorn', uvicorn.__version__)"
python -c "import streamlit; print('demo     OK - streamlit', streamlit.__version__)"
python -c "import jupyterlab, tqdm; print('notebooks OK - jupyterlab', jupyterlab.__version__, '/ tqdm', tqdm.__version__)"
