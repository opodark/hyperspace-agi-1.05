# SPDX-License-Identifier: Apache-2.0
# Modulo extra Resin 1.06 (ekzhang/resin, Apache-2.0) per Windows: clona a un commit fissato,
# verifica i crate Rust (resin-core, resin-recipe, resin-http) e compila il binding Python (_resin.pyd).
#
#   powershell -ExecutionPolicy Bypass -File scripts\install-resin.ps1
param(
    [string]$Dest = "",
    [string]$Commit = "3f68b0a5024859e0f7cef8b7a348adb8c3293c5d"
)
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
if (-not $Dest) {
    if ($env:RESIN_DIR) { $Dest = $env:RESIN_DIR } else { $Dest = Join-Path $Root "modules\resin" }
}
$Repo = "https://github.com/ekzhang/resin.git"

function Invoke-Native {
    param([string]$Exe, [string[]]$ArgList)
    & $Exe @ArgList
    if ($LASTEXITCODE -ne 0) { throw "$Exe $($ArgList -join ' ') -> exit $LASTEXITCODE" }
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "git non trovato" }
if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    throw "cargo (Rust) non trovato: installalo da https://rustup.rs/"
}

if (-not (Test-Path (Join-Path $Dest ".git"))) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Dest) | Out-Null
    # Disabilita autocrlf per evitare che git converta LF in CRLF nei template/fixtures dei test
    Invoke-Native git @("-c", "core.autocrlf=false", "clone", $Repo, $Dest)
}
Invoke-Native git @("-C", $Dest, "fetch", "--quiet", "origin")
Invoke-Native git @("-C", $Dest, "checkout", "--quiet", "--detach", $Commit)
# Assicura checkout con terminatori LF nativi per la suite di test
Invoke-Native git @("-C", $Dest, "config", "core.autocrlf", "false")
Invoke-Native git @("-C", $Dest, "checkout", "--quiet", "--", "crates/resin-recipe/src/deepseek/tools.txt")
Write-Host "[resin] $Dest @ $(git -C $Dest rev-parse --short HEAD)"

Push-Location $Dest
try {
    # Normalizza eventuali terminatori CRLF clonati in precedenza nei template inclusi con include_str!
    $toolsFile = Join-Path $Dest "crates\resin-recipe\src\deepseek\tools.txt"
    if (Test-Path $toolsFile) {
        $content = [System.IO.File]::ReadAllText($toolsFile)
        if ($content.Contains("`r`n")) {
            [System.IO.File]::WriteAllText($toolsFile, $content.Replace("`r`n", "`n"))
        }
    }
    Invoke-Native cargo @("test", "--quiet", "-p", "resin-core", "-p", "resin-recipe", "-p", "resin-http")
    Invoke-Native cargo @("build", "--release", "-p", "resin-py")
    $dllPath = Join-Path $Dest "target\release\_resin.dll"
    if (-not (Test-Path $dllPath)) {
        # Cargo su Windows può generare lib_resin.dll o _resin.dll
        $altDll = Join-Path $Dest "target\release\lib_resin.dll"
        if (Test-Path $altDll) { $dllPath = $altDll }
    }
    if (Test-Path $dllPath) {
        Copy-Item -Force $dllPath (Join-Path $Dest "resin\_resin.pyd")
    }
}
finally {
    Pop-Location
}
Write-Host "[resin] OK"
