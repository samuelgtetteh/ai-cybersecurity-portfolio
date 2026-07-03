# Run this from the ai-cybersecurity-portfolio root directory, in a normal (non-activated) PowerShell.
# Activates the venv and installs any backend dependencies that aren't already installed.
# Packages already present are skipped.

Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& .\venv\Scripts\Activate.ps1

$requirements = Get-Content backend\requirements.txt | Where-Object { $_.Trim() -ne "" }

foreach ($req in $requirements) {
    # Strip version specifiers (==, >=, etc.) to get the bare package name
    $pkgName = ($req -split '[=<>!~\[]')[0].Trim()

    $installed = python -m pip show $pkgName 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[skip] $pkgName already installed"
    } else {
        Write-Host "[install] $req"
        python -m pip install $req
    }
}

# Sanity check
python -c "import fastapi, uvicorn; print('fastapi', fastapi.__version__); print('uvicorn', uvicorn.__version__)"
