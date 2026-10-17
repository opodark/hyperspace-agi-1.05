# SPDX-License-Identifier: Apache-2.0
# HyperSpace AGI 1.05 - avvio completo con un comando (Windows/PowerShell)
#
# Perché esiste: su macOS lo stack si avvia in un colpo con
# scripts/start-all-macos.sh (doppio clic: scripts/desktop/start-tutto.command).
# Su Windows i pezzi sono sparsi in più script: lo stack Docker (start.ps1), le
# superfici host (start-surfaces.ps1), il bridge memoria Hermes e la superficie
# REA. Qui diventano un comando solo, con un verdetto finale.
#
# Uso:
#   .\scripts\start-tutto.ps1            # avvia tutto (core + superfici + opzionali)
#   .\scripts\start-tutto.ps1 -Build     # come sopra, ricostruendo le immagini
#   .\scripts\start-tutto.ps1 -Check     # non avvia nulla: dice solo cosa gira
#   .\scripts\start-tutto.ps1 -Stop      # ferma tutto
#   .\scripts\start-tutto.ps1 -Quiet     # meno output
#
# Note:
#   - lo stack Docker è quello di docker-compose.windows.yml (delega a start.ps1);
#   - le superfici host (Telegram, ponte ComfyUI, gateway immagini, Laya,
#     Graphify, monitor energetico) sono quelle di start-surfaces.ps1;
#   - Hermes Memory Bridge (porta 8098) e la superficie REA (porta 7872) sono
#     opzionali e partono solo se installati, come sul Mac;
#   - TikTok editor e scheduler Reel giornaliero sono SOLO macOS (girano sul
#     loopback del Mac, 127.0.0.1:7860, non su Windows).

param(
    [switch]$Check,
    [switch]$Stop,
    [switch]$Build,
    [switch]$Quiet
)

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Log($m)  { if (-not $Quiet) { Write-Host "[start-tutto] $m" -ForegroundColor Green } }
function Warn($m) { Write-Host "[start-tutto] AVVISO: $m" -ForegroundColor Yellow }
function Fail($m) { Write-Host "[start-tutto] ERRORE: $m" -ForegroundColor Red }
function Head($m) { Write-Host ""; Write-Host "== $m ==" -ForegroundColor Cyan }

function Test-Porta([int]$Porta) {
    return [bool](Get-NetTCPConnection -LocalPort $Porta -State Listen -ErrorAction SilentlyContinue)
}

$core      = Join-Path $Root 'scripts\start.ps1'
$superfici = Join-Path $Root 'scripts\start-surfaces.ps1'
$hermes    = Join-Path $Root 'scripts\start_hermes_memory_bridge.ps1'
$rea       = Join-Path $Root 'scripts\rea_surface.py'
$python    = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { $python = 'python' }

if (-not (Test-Path '.env')) {
    if (Test-Path '.env.windows') {
        Warn ".env mancante: Copy-Item .env.windows .env (poi rileggi i valori: i segreti sono tuoi)"
    } else {
        Warn ".env mancante: copia .env.example in .env"
    }
}

# --- STOP ---------------------------------------------------------------------
if ($Stop) {
    Head "Stop-tutto"
    Log "fermo le superfici host (Telegram, ponte ComfyUI, gateway, Laya, Graphify, energia)"
    & powershell -NoProfile -ExecutionPolicy Bypass -File $superfici -Stop

    $hermesProc = Get-CimInstance Win32_Process -Filter "Name like '%python%'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -match 'hermes_memory_bridge\.py' }
    foreach ($p in $hermesProc) {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        Log "fermato Hermes Memory Bridge (PID $($p.ProcessId))"
    }

    $reaProc = Get-CimInstance Win32_Process -Filter "Name like '%python%'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -match 'rea_surface\.py' }
    foreach ($p in $reaProc) {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        Log "fermata superficie REA (PID $($p.ProcessId))"
    }

    Log "fermo lo stack Docker (i volumi restano: Identita' e memoria sopravvivono)"
    & powershell -NoProfile -ExecutionPolicy Bypass -File $core -Stop
    Log "fatto. Per ripartire: .\scripts\start-tutto.ps1"
    exit 0
}

# --- CHECK --------------------------------------------------------------------
if ($Check) {
    Head "Check-tutto"
    & powershell -NoProfile -ExecutionPolicy Bypass -File $core -Check
    & powershell -NoProfile -ExecutionPolicy Bypass -File $superfici -Check
    if (Test-Porta 8098) { Log "Hermes Memory Bridge: attivo (porta 8098)" }
    else { Warn "Hermes Memory Bridge: porta 8098 non in ascolto (opzionale)" }
    if (Test-Porta 7872) { Log "superficie REA: attiva (porta 7872)" }
    else { Log "superficie REA: spenta (opzionale: rea-agents non installato)" }
    Log "TikTok editor e scheduler Reel: solo macOS (non gestiti su Windows)"
    exit 0
}

# --- AVVIO --------------------------------------------------------------------
Head "Start-tutto (HyperSpace su Windows)"
Log "repo: $Root"

# 1. Stack Docker: control-plane, registry, gateway, web-node, ...
$coreArgs = @()
if (-not $Build) { $coreArgs += '-NoBuild' }
Log "avvio stack Docker ($(if ($Build) { 'con --build' } else { 'senza rebuild' }))"
& powershell -NoProfile -ExecutionPolicy Bypass -File $core @coreArgs
Log "stack Docker avviato (verifica: .\scripts\start.ps1 -Check)"

# 2. Superfici host
Log "avvio superfici host"
& powershell -NoProfile -ExecutionPolicy Bypass -File $superfici

# 3. Hermes Memory Bridge (opzionale, memoria sovrana)
$data         = Join-Path $Root 'data'
if (-not (Test-Path $data)) { New-Item -ItemType Directory -Path $data -Force | Out-Null }
$hermesPython = Join-Path $env:LOCALAPPDATA 'hermes\hermes-agent\venv\Scripts\python.exe'
$hermesToken  = Join-Path $data 'hermes-memory.token'
if (Test-Porta 8098) {
    Log "Hermes Memory Bridge gia' attivo (porta 8098)"
} elseif (Test-Path $hermesPython -and Test-Path $hermesToken) {
    $logHermes = Join-Path $data 'hermes-memory-bridge.log'
    $cmdHermes = "& '$hermes' *> '$logHermes'"
    Start-Process -FilePath 'powershell.exe' `
        -ArgumentList "-NoProfile -ExecutionPolicy Bypass -Command `"$cmdHermes`"" `
        -WorkingDirectory $Root -WindowStyle Hidden | Out-Null
    Log "Hermes Memory Bridge avviato (porta 8098, log: data\hermes-memory-bridge.log)"
} else {
    Log "Hermes Memory Bridge non avviato: Hermes Agent non installato o token assente (opzionale)"
}

# 4. Superficie REA (opzionale, serve rea-agents nel PATH)
if (Test-Porta 7872) {
    Log "superficie REA gia' attiva (porta 7872)"
} else {
    & $python $rea --check *> $null
    if ($LASTEXITCODE -eq 0) {
        $reaLog = Join-Path $data 'rea-surface.log'
        $reaErr = Join-Path $data 'rea-surface.err.log'
        Start-Process -FilePath $python -ArgumentList @($rea) `
            -WorkingDirectory $Root -WindowStyle Hidden `
            -RedirectStandardOutput $reaLog -RedirectStandardError $reaErr | Out-Null
        Log "superficie REA in avvio (porta 7872, log: data\rea-surface.log)"
    } else {
        Log "superficie REA non avviata: rea-agents non installato (npm install --global rea-agents)"
    }
}

# 5. TikTok editor + scheduler Reel: solo macOS
Log "TikTok editor e scheduler Reel: solo macOS (loopback 127.0.0.1:7860 sul Mac)"

Head "Riepilogo"
Log "dashboard:  http://127.0.0.1:8085/dashboard"
Log "web-node:   http://127.0.0.1:8790"
Log "grafo repo: http://127.0.0.1:7871 (se il grafo e' stato generato)"
Log "REA:        http://127.0.0.1:7872 (se rea-agents installato)"
Log "Laya:       porta 8097"
Log "ComfyUI:    porta 8188 (Desktop) + ponte in esecuzione"
Log "verifica stato: .\scripts\start-tutto.ps1 -Check"
Log "ferma tutto:    .\scripts\start-tutto.ps1 -Stop"
