# SPDX-License-Identifier: Apache-2.0
param(
    [string]$BindAddress = "127.0.0.1",
    [int]$Port = 8098,
    [string]$TokenFile = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $TokenFile) {
    $TokenFile = Join-Path $repoRoot "data\hermes-memory.token"
}

$python = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent\venv\Scripts\python.exe"
$bridge = Join-Path $PSScriptRoot "hermes_memory_bridge.py"

# Se Hermes Agent non e' installato nativamente, opera in modalita' Shadow Memory autonoma
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    $repoPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $repoPython -PathType Leaf) {
        $python = $repoPython
    } else {
        $python = "python"
    }
    Write-Host "[hermes-bridge] Hermes Agent non rilevato: avvio in modalita' SHADOW MEMORY (interprete: $python)" -ForegroundColor Cyan
    $env:HERMES_HOME = Join-Path $repoRoot "data\hermes_shadow"
} else {
    $env:HERMES_HOME = Join-Path $env:LOCALAPPDATA "hermes"
}

# Generazione automatica del token di memoria se assente
if (-not (Test-Path -LiteralPath $TokenFile -PathType Leaf)) {
    Write-Host "[hermes-bridge] Generazione token di memoria in $TokenFile..." -ForegroundColor Green
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $hexToken = -join ($bytes | ForEach-Object { "{0:x2}" -f $_ })
    $tokenDir = Split-Path -Parent $TokenFile
    if (-not (Test-Path $tokenDir)) { New-Item -ItemType Directory -Path $tokenDir -Force | Out-Null }
    Set-Content -Path $TokenFile -Value $hexToken -NoNewline -Encoding Ascii
}

$env:HERMES_MEMORY_TOKEN_FILE = (Resolve-Path -LiteralPath $TokenFile).Path
& $python $bridge --host $BindAddress --port $Port --token-file $env:HERMES_MEMORY_TOKEN_FILE
