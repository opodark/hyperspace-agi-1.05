# SPDX-License-Identifier: Apache-2.0
# HyperSpace AGI 1.04 - avvio delle SUPERFICI ESTERNE (Windows/PowerShell)
#
# Perché esiste: il driver Telegram, il ponte di ComfyUI e il gateway immagini di
# Open WebUI sono tre processi che vivono sulla macchina e non dentro lo stack: se
# non li avvii, il canale tace, le immagini restano in coda e la WebUI non trova
# nessuno che disegni. Tre comandi diversi da ricordare sono tre comandi che si
# dimenticano — qui diventano uno, con un verdetto.
#
#   .\scripts\start-surfaces.ps1            # avvia tutti e tre (nascosti, con log)
#   .\scripts\start-surfaces.ps1 -Check     # non avvia: dice cosa gira e cosa manca
#   .\scripts\start-surfaces.ps1 -Telegram  # solo il driver Telegram
#   .\scripts\start-surfaces.ps1 -Comfy     # solo il ponte di ComfyUI
#   .\scripts\start-surfaces.ps1 -Gateway   # solo il gateway immagini (WebUI)
#   .\scripts\start-surfaces.ps1 -Stop      # ferma quelli avviati da qui
#
# I log finiscono in data\ (ignorata da git): telegram-driver.log,
# comfy-bridge.log, webui-gateway.log. I processi si riconoscono dalla riga di
# comando, quindi -Stop non tocca nient'altro che gira sulla macchina.

param(
    [switch]$Telegram,
    [switch]$Comfy,
    [switch]$Gateway,
    [switch]$Laya,
    [switch]$Graphify,
    [switch]$Power,
    [switch]$Bonsai,
    [switch]$Check,
    [switch]$Stop
)

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Log($m)  { Write-Host "[surfaces] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "[warn]     $m" -ForegroundColor Yellow }
function Fail($m) { Write-Host "[error]    $m" -ForegroundColor Red }
function Head($m) { Write-Host ""; Write-Host "== $m ==" -ForegroundColor Cyan }

if (-not $Telegram -and -not $Comfy -and -not $Gateway -and -not $Laya -and -not $Graphify -and -not $Power -and -not $Bonsai -and -not $Stop) {
    # Nessuna scelta = tutte le superfici essenziali abilitate per default
    $Telegram = $true
    $Comfy = $true
    $Gateway = $true
    $Laya = $true
    $Graphify = $true
    $Power = $true
    # Bonsai 2 dismesso/disarmato a favore del runtime LFM 2.5 / Ollama nativo
    $Bonsai = $false
}

function Get-Processi([string]$Frammento) {
    return @(Get-CimInstance Win32_Process -Filter "Name like '%python%'" -ErrorAction SilentlyContinue |
             Where-Object { $_.CommandLine -and $_.CommandLine -match [regex]::Escape($Frammento) })
}

function Avvia([string]$Etichetta, [string]$ScriptPath, [string]$LogNome, [string]$ParametriExtra = "") {
    $dirData = Join-Path $Root "data"
    if (-not (Test-Path $dirData)) { New-Item -ItemType Directory -Path $dirData -Force | Out-Null }
    $percorso = Join-Path $dirData $LogNome
    $cmd = "& '$ScriptPath' $ParametriExtra *> '$percorso'"
    Start-Process -FilePath 'powershell.exe' `
        -ArgumentList "-NoProfile -ExecutionPolicy Bypass -Command `"$cmd`"" `
        -WorkingDirectory $Root `
        -WindowStyle Hidden | Out-Null
    Log "$Etichetta avviato (log: data\$LogNome)"
}

$driverTelegram = Join-Path $Root 'scripts\start-telegram.ps1'
$ponteComfy = Join-Path $Root 'integrations\comfyui\comfy_bridge.py'
$gatewayImmagini = Join-Path $Root 'integrations\comfyui\start-gateway.ps1'
$scriptGraphify = Join-Path $Root 'scripts\graphify_surface.py'
$scriptPower = Join-Path $Root 'scripts\power_monitor.py'
$python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { $python = 'python' }

$telegramAttivi = Get-Processi 'telegram_bot.py'
$comfyAttivi = Get-Processi 'comfy_bridge.py'
$gatewayAttivi = Get-Processi 'webui_gateway.py'
$layaAttivi = Get-Processi 'laya_service.py'
$graphifyAttivi = Get-Processi 'graphify_surface.py'
$powerAttivi = Get-Processi 'power_monitor.py'
$bonsaiAttivi = @(Get-Process -Name 'llama-server' -ErrorAction SilentlyContinue)

if ($Stop) {
    Head "Stop Superfici Esterne"
    $tutti = @($telegramAttivi; $comfyAttivi; $gatewayAttivi; $layaAttivi; $graphifyAttivi; $powerAttivi) |
             Where-Object { $_ -and $_.ProcessId }
    foreach ($processo in $tutti) {
        Stop-Process -Id $processo.ProcessId -Force -ErrorAction SilentlyContinue
        Log "fermato PID $($processo.ProcessId)"
    }
    foreach ($b in $bonsaiAttivi) {
        Stop-Process -Id $b.Id -Force -ErrorAction SilentlyContinue
        Log "fermato PID $($b.Id) (Bonsai 2)"
    }
    if (-not $tutti.Count -and -not $bonsaiAttivi.Count) { Log "nessuna superficie attiva da fermare" }
    exit 0
}

Head "Stato Superfici Host HyperSpace"
if ($powerAttivi.Count) {
    Log "monitor energetico host: attivo (PID $($powerAttivi.ProcessId -join ', '))"
} else {
    Warn "monitor energetico host: spento"
}

# Rilevamento istantaneo alimentazione host
try {
    $hostPowerFile = Join-Path $Root 'data\host_power.json'
    if (Test-Path $hostPowerFile) {
        $pwr = Get-Content $hostPowerFile -Raw | ConvertFrom-Json
        $pwrDesc = if ($pwr.ac_line) { "Presa AC fissa (100%)" } else { "Batteria ($($pwr.battery_pct)%, $(if ($pwr.charging){'in carica'}else{'in scarica'}))" }
        Log "stato alimentazione host: $pwrDesc"
    }
} catch {}

if ($layaAttivi.Count) { Log "decision engine Laya: attivo (PID $($layaAttivi.ProcessId -join ', '), porta 8097)" }
else { Warn "decision engine Laya: spento (porta 8097 non attiva)" }

if ($comfyAttivi.Count) { Log "ponte ComfyUI: attivo (PID $($comfyAttivi.ProcessId -join ', '))" }
else { Warn "ponte ComfyUI: spento (le immagini restano in coda)" }

if ($gatewayAttivi.Count) { Log "gateway immagini WebUI: attivo (PID $($gatewayAttivi.ProcessId -join ', '), porta 8189)" }
else { Warn "gateway immagini WebUI: spento (dalla WebUI l'immagine non si genera)" }

if ($graphifyAttivi.Count) { Log "superficie Graphify: attiva (PID $($graphifyAttivi.ProcessId -join ', '), http://127.0.0.1:7871)" }
else { Warn "superficie Graphify: spenta (porta 7871 non attiva)" }

if ($telegramAttivi.Count) { Log "driver Telegram: attivo (PID $($telegramAttivi.ProcessId -join ', '))" }
else {
    if (Test-Path (Join-Path $Root 'data\telegram-bot.env')) {
        Warn "driver Telegram: spento (configurato ma non attivo)"
    } else {
        Log "driver Telegram: non configurato (data\telegram-bot.env assente, opzionale)"
    }
}

# Controllo servizi infrastrutturali host
$ollamaProc = Get-Process 'ollama' -ErrorAction SilentlyContinue
if ($ollamaProc) { Log "Ollama host runtime: attivo (PID $($ollamaProc.Id -join ', '), porta 11434)" }
else { Warn "Ollama host runtime: non rilevato" }

$comfyUiProc = Get-Process -Name 'Comfy Desktop', 'python' -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -and $_.Path -match 'Comfy' }
if ($comfyUiProc) { Log "ComfyUI Desktop host: attivo (PID $($comfyUiProc.Id -join ', '), porta 8188)" }
else { Warn "ComfyUI Desktop host: spento su porta 8188" }

$hermesConn = Get-NetTCPConnection -LocalPort 8098 -State Listen -ErrorAction SilentlyContinue
if ($hermesConn) { Log "Hermes Memory Bridge: attivo (PID $($hermesConn.OwningProcess -join ', '), porta 8098)" }
else { Warn "Hermes Memory Bridge: porta 8098 non in ascolto" }

if ($bonsaiAttivi.Count) { Log "Bonsai 2 server (llama-server): attivo (PID $($bonsaiAttivi.Id -join ', '), porta 8082)" }
else { Warn "Bonsai 2 server (llama-server): spento su porta 8082" }

if ($Check) {
    $statoCp = 0
    try {
        $statoCp = [int](Invoke-WebRequest -Uri 'http://127.0.0.1:8085/health' -UseBasicParsing -TimeoutSec 5).StatusCode
    } catch {
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode) { $statoCp = [int]$_.Exception.Response.StatusCode }
    }
    if ($statoCp -eq 200) { Log "control-plane: ok (HTTP 200)" } else { Warn "control-plane: HTTP $statoCp (avvialo con .\scripts\start.ps1)" }
    # Aggiorna istantaneamente lo stato energetico
    try { & $python $scriptPower --once | Out-Null } catch {}
    Head "Dettagli Check Superfici"
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root 'scripts\start-laya.ps1') -Check
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root 'integrations\comfyui\start-bridge.ps1') -Check
    & powershell -NoProfile -ExecutionPolicy Bypass -File $gatewayImmagini -Check
    if (Test-Path (Join-Path $Root 'data\telegram-bot.env')) {
        & powershell -NoProfile -ExecutionPolicy Bypass -File $driverTelegram -Check -Mention
    }
    if (Test-Path $scriptGraphify) {
        & $python $scriptGraphify --check
    }
    exit 0
}

# Avvio ordinato
if ($Laya -and -not $layaAttivi.Count) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root 'scripts\start-laya.ps1') -Port 8097
}
if ($Comfy -and -not $comfyAttivi.Count) {
    Avvia 'ponte ComfyUI' (Join-Path $Root 'integrations\comfyui\start-bridge.ps1') 'comfy-bridge.log'
}
if ($Gateway -and -not $gatewayAttivi.Count) {
    Avvia 'gateway immagini WebUI' $gatewayImmagini 'webui-gateway.log'
}
if ($Graphify -and -not $graphifyAttivi.Count) {
    $dirData = Join-Path $Root "data"
    if (-not (Test-Path $dirData)) { New-Item -ItemType Directory -Path $dirData -Force | Out-Null }
    $logGraphify = Join-Path $dirData 'graphify.log'
    $logGraphifyErr = Join-Path $dirData 'graphify.err.log'
    Start-Process -FilePath $python `
        -ArgumentList @($scriptGraphify) `
        -WorkingDirectory $Root `
        -WindowStyle Hidden `
        -RedirectStandardOutput $logGraphify `
        -RedirectStandardError $logGraphifyErr | Out-Null
    Log "superficie Graphify avviata (log: data\graphify.log, http://127.0.0.1:7871)"
}
if ($Telegram -and -not $telegramAttivi.Count) {
    if (Test-Path (Join-Path $Root 'data\telegram-bot.env')) {
        Avvia 'driver Telegram' $driverTelegram 'telegram-driver.log' '-Mention'
    } else {
        Log "driver Telegram: saltato (data\telegram-bot.env assente)"
    }
}
if ($Power -and -not $powerAttivi.Count) {
    $dirData = Join-Path $Root "data"
    if (-not (Test-Path $dirData)) { New-Item -ItemType Directory -Path $dirData -Force | Out-Null }
    $logPower = Join-Path $dirData 'power-monitor.log'
    $logPowerErr = Join-Path $dirData 'power-monitor.err.log'
    Start-Process -FilePath $python `
        -ArgumentList @($scriptPower) `
        -WorkingDirectory $Root `
        -WindowStyle Hidden `
        -RedirectStandardOutput $logPower `
        -RedirectStandardError $logPowerErr | Out-Null
    Log "monitor energetico avviato (log: data\power-monitor.log)"
}
if ($Bonsai -and -not $bonsaiAttivi.Count) {
    $scriptBonsai = Join-Path $Root 'scripts\start_bonsai_daemon.ps1'
    if (Test-Path $scriptBonsai) {
        Avvia 'Bonsai 2 server' $scriptBonsai 'bonsai-surface.log'
    }
}

Head "Completato"
Log "verifica stato con: .\scripts\start-surfaces.ps1 -Check"
