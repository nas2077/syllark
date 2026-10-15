param([switch]$Quiet, [switch]$NoZip, [switch]$SkipSetup)
$ErrorActionPreference = 'Stop'
$DevelopmentRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $DevelopmentRoot
$EnvironmentPython = Join-Path $DevelopmentRoot '.venv\Scripts\python.exe'
if (-not $SkipSetup) {
    & (Join-Path $DevelopmentRoot 'setup.ps1') -Quiet
    if ($LASTEXITCODE -ne 0) { throw 'Environment preparation failed.' }
}
if (-not (Test-Path -LiteralPath $EnvironmentPython)) { throw 'Run dev\setup.ps1 first.' }
& $EnvironmentPython (Join-Path $DevelopmentRoot 'collect_licenses.py')
if ($LASTEXITCODE -ne 0) { throw 'License collection failed.' }
& $EnvironmentPython -m PyInstaller --noconfirm --clean --log-level WARN --distpath (Join-Path $DevelopmentRoot 'build\dist') --workpath (Join-Path $DevelopmentRoot 'build\work') (Join-Path $DevelopmentRoot 'build.spec')
if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
$Distribution = Join-Path $DevelopmentRoot 'build\dist\Syllark'
if (-not (Test-Path -LiteralPath (Join-Path $Distribution 'Syllark.exe'))) { throw 'Executable is missing.' }
if (-not $NoZip) {
    $ReleaseZip = Join-Path $DevelopmentRoot 'dist\Syllark-0.1.0-windows-x64.zip'
    New-Item -ItemType Directory -Force -Path (Split-Path $ReleaseZip) | Out-Null
    & $EnvironmentPython (Join-Path $DevelopmentRoot 'package_release.py') $Distribution $ReleaseZip
    if ($LASTEXITCODE -ne 0) { throw 'Release ZIP verification failed.' }
}
Write-Host "Built Syllark in $Distribution"
