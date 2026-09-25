$root = Split-Path -Parent $MyInvocation.MyCommand.Path

$nodeDir = "C:\Program Files\nodejs"
$env:Path = "$nodeDir;$env:Path"

$npm = Join-Path $nodeDir "npm.cmd"
$frontend = Join-Path $root "frontend"

# Create frontend environment file if missing
if (-not (Test-Path "$frontend\.env")) {
    if (Test-Path "$frontend\.env.example") {
        Write-Host "Creating frontend .env from .env.example..."
        Copy-Item "$frontend\.env.example" "$frontend\.env"
    }
    else {
        Write-Host "Creating frontend .env..."
        Set-Content "$frontend\.env" "VITE_API_BASE=http://localhost:8000/api"
    }
}

# Install frontend dependencies only when needed
if (-not (Test-Path "$frontend\node_modules")) {
    Write-Host "Frontend dependencies not found. Running npm ci..."
    Push-Location $frontend
    & $npm ci

    if ($LASTEXITCODE -ne 0) {
        Pop-Location
        throw "npm ci failed."
    }

    Pop-Location
}

# Start Django
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$root'; .\.venv\Scripts\Activate.ps1; python manage.py runserver"
)

# Start React/Vite
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$frontend'; npm.cmd run dev -- --port 5173 --strictPort"
)

# Give Django/Vite time to start
Start-Sleep -Seconds 6

Start-Process "http://localhost:5173/dashboard"