$ErrorActionPreference = "Stop"

$RootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RootDir

function Invoke-SystemPython {
    param([string[]]$Arguments)

    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 @Arguments
        return
    }

    & python @Arguments
}

if (-not (Test-Path ".venv")) {
    Invoke-SystemPython @("-m", "venv", ".venv")
}

$Python = Join-Path $RootDir ".venv\Scripts\python.exe"
$AgentPrimer = Join-Path $RootDir ".venv\Scripts\agent-primer.exe"

& $Python -m pip install -e ".[dev]"
& $AgentPrimer
