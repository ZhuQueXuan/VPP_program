param([string]$InputFile = '', [string]$ModelFile = '', [double]$Target = 120)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot 'work\ride_b1_v02_reproduction_20261029\.venv\Scripts\python.exe'
$cliPath = Join-Path $PSScriptRoot 'research_cli.py'
$env:PYTHONIOENCODING = 'utf-8'
if ($InputFile) { & $pythonPath -B $cliPath --input $InputFile --target $Target }
elseif ($ModelFile) { & $pythonPath -B $cliPath --model $ModelFile --target $Target }
else { & $pythonPath -B $cliPath --target $Target }
if ($LASTEXITCODE -ne 0) { throw 'Research point one execution failed; see the output above.' }
