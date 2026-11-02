# SPDX-License-Identifier: Apache-2.0
# Modulo extra Qwenputer (divagr18/qwenputer, MIT) per Windows: clona a un commit fissato, crea il
# suo ambiente con uv e verifica la CPU RISC-V sulla macchina di riferimento.
#
#   powershell -ExecutionPolicy Bypass -File scripts\install-qwenputer.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\install-qwenputer.ps1 -InWeight
#
# -InWeight scarica il modello (~9 GB) e lo carica intero in RAM (14,65 GB in bf16) per una chat
# vera in CPU: la GPU da 8 GB non basta e il circuito non sopporta la quantizzazione.
param(
    [switch]$InWeight,
    [string]$Dest = "",
    [string]$Commit = "bec1a0c9654ac8151b6f36ed0154a19c53141384"
)
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
if (-not $Dest) {
    if ($env:QWENPUTER_DIR) { $Dest = $env:QWENPUTER_DIR } else { $Dest = Join-Path $Root "modules\qwenputer" }
}
$Repo = "https://github.com/divagr18/qwenputer.git"
$ModelId = "divagr1925/Qwen3.5-4B-Qwenputer"

function Invoke-Native {
    param([string]$Exe, [string[]]$ArgList)
    & $Exe @ArgList
    if ($LASTEXITCODE -ne 0) { throw "$Exe $($ArgList -join ' ') -> exit $LASTEXITCODE" }
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "git non trovato" }
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv non trovato: installalo con 'python -m pip install --user uv' o da https://docs.astral.sh/uv/"
}

if (-not (Test-Path (Join-Path $Dest ".git"))) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Dest) | Out-Null
    Invoke-Native git @("clone", $Repo, $Dest)
}
Invoke-Native git @("-C", $Dest, "fetch", "--quiet", "origin")
Invoke-Native git @("-C", $Dest, "checkout", "--quiet", "--detach", $Commit)
Write-Host "[qwenputer] $Dest @ $(git -C $Dest rev-parse --short HEAD)"

Push-Location (Join-Path $Dest "experimental\riscv")
try {
    Invoke-Native uv @("sync", "--extra", "hf")
    Invoke-Native uv @("run", "pytest", "-q", "tests/test_rv_ref.py", "tests/test_rv_core.py", "tests/test_rv_bridge.py")

    if ($InWeight) {
        $ramGb = [math]::Floor((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
        if ($ramGb -lt 24) { throw "RAM $ramGb GB < 24 GB: il modello in-weight non entra su questa macchina" }
        $ModelDir = if ($env:QWENPUTER_MODEL_DIR) { $env:QWENPUTER_MODEL_DIR } else { Join-Path $Dest "qwenputer-rv" }
        Invoke-Native uv @("run", "hf", "download", $ModelId, "--local-dir", $ModelDir)
        Invoke-Native uv @("run", "python", "-m", "chipformer.rv.chat", $ModelDir,
            "--firmware", "tests/data/rv/calc-bridge.elf",
            "--ask", "Use calc: what is 123456789 * 987654321?", "--check")
    }
}
finally {
    Pop-Location
}
Write-Host "[qwenputer] OK"
