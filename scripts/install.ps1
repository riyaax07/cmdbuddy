# CmdBuddy PowerShell Installation Script
# Installs CmdBuddy in editable mode and configures PowerShell access safely.
# Does NOT require administrative privileges or changing machine-wide ExecutionPolicy.

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  Installing CmdBuddy for PowerShell     " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# 1. Verify Python availability
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Error "Python was not found in PATH. Please install Python 3.11+."
    exit 1
}

$pyVersion = python --version
Write-Host "Detected: $pyVersion" -ForegroundColor Green

# 2. Locate project root directory
$projectDir = Split-Path -Parent $PSScriptRoot
Write-Host "Installing package from: $projectDir ..." -ForegroundColor Yellow

# Use pip install -e
python -m pip install -e "$projectDir"

# 3. Locate Python Scripts directory where cmb.exe resides
$scriptDirs = @(
    (python -c "import site; print(site.USER_BASE + '\\Scripts')"),
    (python -c "import sysconfig; print(sysconfig.get_path('scripts'))")
)

$foundDir = $null
foreach ($sDir in $scriptDirs) {
    if (Test-Path (Join-Path $sDir "cmb.exe")) {
        $foundDir = $sDir
        Write-Host "[OK] cmb.exe found at: $sDir\cmb.exe" -ForegroundColor Green
        break
    }
}

if ($foundDir) {
    # Configure current session PATH
    if ($env:PATH -notlike "*$foundDir*") {
        $env:PATH = "$foundDir;" + $env:PATH
        Write-Host "Added $foundDir to current session PATH." -ForegroundColor Cyan
    }

    # Safe persistence check: does NOT alter machine-wide ExecutionPolicy
    Write-Host "`nTo make 'cmb' permanently available across all PowerShell windows:" -ForegroundColor Yellow
    Write-Host "  Option A (Recommended - User PATH):" -ForegroundColor White
    Write-Host "    [Environment]::SetEnvironmentVariable('PATH', [Environment]::GetEnvironmentVariable('PATH', 'User') + ';$foundDir', 'User')" -ForegroundColor Gray
    Write-Host "  Option B (PowerShell Profile function / alias):" -ForegroundColor White
    Write-Host "    Add to your `$PROFILE: function cmb { python -m cmdbuddy.cli @args }" -ForegroundColor Gray
} else {
    Write-Host "! cmb.exe not found in standard directories. You can run via: python -m cmdbuddy.cli" -ForegroundColor Yellow
}

# 4. Verify version
python -m cmdbuddy.cli --version
Write-Host "`nInstallation verified! Try running:" -ForegroundColor Cyan
Write-Host "  cmb --help" -ForegroundColor White
Write-Host "  cmb context" -ForegroundColor White
Write-Host "  cmb history" -ForegroundColor White
