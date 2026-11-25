<#
.SYNOPSIS
    Start-Billo.ps1 - GPU Workstation Launch Script (Windows 11)
    Hardware: i7-12700K | RTX 3080 Ti | 32GB DDR5
.DESCRIPTION
    IMPORTANT GOTCHA RESOLUTION:
    $PID is a PowerShell reserved variable representing the current shell process ID.
    Never run "Kill -Id $PID" or assign to $PID.
    Use "Stop-Process -Name python -Force" instead.
#>

Write-Host "===========================================================" -ForegroundColor Cyan
$vpsHost = $env:BILLO_VPS_HOST
Write-Host " Launching Billo Orchestrator & LOCI Memory System" -ForegroundColor Cyan
Write-Host " Environment: Windows 11 GPU Workstation (RTX 3080 Ti)" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan

# 1. Cleanly stop any existing Python processes without touching $PID
Write-Host "[1/4] Terminating stale Python processes safely..." -ForegroundColor Yellow
Stop-Process -Name python -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

# 2. Check local GPU Ollama (14b)
Write-Host "[2/4] Verifying local GPU Ollama on port 11434..." -ForegroundColor Yellow
try {
    $ollamaCheck = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method Get -TimeoutSec 3 -ErrorAction Stop
    Write-Host "  -> Ollama GPU is running. Available models: $($ollamaCheck.models.name -join ', ')" -ForegroundColor Green
} catch {
    Write-Host "  -> WARNING: Local Ollama on port 11434 not responding. Please launch 'ollama serve'." -ForegroundColor Red
}

# 3. Establish / Check SSH Tunnel to VPS
Write-Host "[3/4] Checking SSH tunnel to configured VPS (127.0.0.1:11435 -> VPS:11434)..." -ForegroundColor Yellow
$tunnelActive = $false
try {
    $tunnelCheck = Invoke-RestMethod -Uri "http://localhost:11435/api/tags" -Method Get -TimeoutSec 3 -ErrorAction Stop
    $tunnelActive = $true
    Write-Host "  -> VPS Tunnel verified on port 11435." -ForegroundColor Green
} catch {
    if ([string]::IsNullOrWhiteSpace($vpsHost)) {
        Write-Host "  -> VPS Tunnel inactive; set BILLO_VPS_HOST to launch it." -ForegroundColor DarkYellow
    } else {
        Write-Host "  -> VPS Tunnel inactive. Launching in background..." -ForegroundColor DarkYellow
        Start-Process -FilePath "ssh" -ArgumentList "-N -L 127.0.0.1:11435:127.0.0.1:11434 root@$vpsHost" -WindowStyle Hidden
    }
}

# 4. Start Billo API & Background Worker
Write-Host "[4/4] Starting Billo API server and background learning loop..." -ForegroundColor Yellow
Set-Location -Path $PSScriptRoot\..\..

# Launch Worker in separate window
Start-Process -FilePath "python" -ArgumentList "Workers\learning_loop.py" -WindowStyle Normal

# Launch FastAPI Server
Write-Host "Starting Uvicorn API on http://127.0.0.1:8000..." -ForegroundColor Green
python -m uvicorn billo.app:app --host 127.0.0.1 --port 8000 --reload
