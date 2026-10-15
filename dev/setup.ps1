param([switch]$Quiet)
$ErrorActionPreference = 'Stop'
$DevelopmentRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $DevelopmentRoot
$EnvironmentPath = Join-Path $DevelopmentRoot '.venv'
$EnvironmentPython = Join-Path $EnvironmentPath 'Scripts\python.exe'

if (-not (Test-Path -LiteralPath $EnvironmentPython)) {
    $Launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($Launcher) {
        & $Launcher.Source -3.12 -m venv $EnvironmentPath
    } else {
        $Launcher = Get-Command python -ErrorAction Stop
        & $Launcher.Source -m venv $EnvironmentPath
    }
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 is recommended. Could not create dev/.venv.' }
}
& $EnvironmentPython -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11 or newer is required"'
if ($LASTEXITCODE -ne 0) { throw 'Unsupported Python version.' }
& $EnvironmentPython -m pip install --disable-pip-version-check -r (Join-Path $DevelopmentRoot 'requirements.txt') -c (Join-Path $DevelopmentRoot 'constraints.txt') -r (Join-Path $DevelopmentRoot 'requirements-dev.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $EnvironmentPython (Join-Path $DevelopmentRoot 'prepare_media.py')
if ($LASTEXITCODE -ne 0) { throw 'Verified media preparation failed.' }
$MediaWheel = Join-Path $DevelopmentRoot 'media\av-18.1.0+lgpl.1-cp311-abi3-win_amd64.whl'
& $EnvironmentPython -m pip install --disable-pip-version-check --no-deps $MediaWheel
if ($LASTEXITCODE -ne 0) { throw 'LGPL media installation failed.' }
Write-Host 'Development environment ready. Run dev\run.bat or dev\build.ps1.'
