$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

$pythonLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($pythonLauncher) {
    & $pythonLauncher.Source -3 -m venv .venv
} else {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        throw "Python 3.11 or later is required. Install Python and rerun this script."
    }

    & $pythonCommand.Source -m venv .venv
}

$projectPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $projectPython)) {
    throw "Failed to create the project virtual environment at .venv."
}

& $projectPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Failed to upgrade pip in the project virtual environment."
}

& $projectPython -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install project dependencies."
}

Write-Host "Project environment is ready. Activate it with .\.venv\Scripts\Activate.ps1"
