# SPDX-License-Identifier: Apache-2.0
# HyperSpace AGI - Gestione Daemon Laya Decision Engine (Windows/PowerShell)
#
# Uso:
#   .\scripts\start-laya.ps1          # avvia il daemon in background se non attivo
#   .\scripts\start-laya.ps1 -Check   # verifica lo stato, porta 8098 e modelli caricati
#   .\scripts\start-laya.ps1 -Stop    # ferma il daemon locale
#   .\scripts\start-laya.ps1 -Restart # riavvia il servizio
#

param(
    [int]$Port = 8097,
    [switch]$Check,
    [switch]$Stop,
    [switch]$Restart
)

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Log($m)  { Write-Host "[laya]    $m" -ForegroundColor Green }
function Warn($m) { Write-Host "[warn]    $m" -ForegroundColor Yellow }
function Fail($m) { Write-Host "[error]   $m" -ForegroundColor Red }
function Head($m) { Write-Host "`n== $m ==" -ForegroundColor Cyan }

$python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { $python = 'python' }

function Get-LayaProcesses {
    return @(Get-CimInstance Win32_Process -Filter "Name like '%python%'" -ErrorAction SilentlyContinue |
             Where-Object { $_.CommandLine -and $_.CommandLine -match 'laya_service\.py' })
}

$attivi = Get-LayaProcesses

if ($Stop -or $Restart) {
    Head "Arresto Laya"
    if ($attivi.Count) {
        foreach ($p in $attivi) {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
            Log "fermato processo PID $($p.ProcessId)"
        }
    } else {
        Log "nessun processo laya_service.py trovato da fermare"
    }
    if ($Stop) { exit 0 }
    Start-Sleep -Seconds 1
    $attivi = @()
}

if ($Check) {
    Head "Verifica Stato Laya Decision Engine"
    try {
        $res = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 2 -ErrorAction Stop
        Log "Stato HTTP: OK (200)"
        Log "Modelli caricati: $($res.loaded -join ', ')"
        Log "Device computazionale: $($res.device)"
        if ($attivi.Count) {
            Log "Processi attivi: PID $($attivi.ProcessId -join ', ')"
        }
    } catch {
        Warn "Laya non risponde su http://127.0.0.1:$Port/health ($($_.Exception.Message))"
        if ($attivi.Count) {
            Warn "Processo presente (PID $($attivi.ProcessId -join ', ')) ma porta non pronta o bloccata."
        }
    }
    exit 0
}

Head "Avvio Laya Decision Engine"
if ($attivi.Count) {
    Log "Laya è già in esecuzione (PID $($attivi.ProcessId -join ', ')). Nessun duplicato avviato."
} else {
    $scriptService = Join-Path $Root 'scripts\laya_service.py'
    $logOut = Join-Path $Root 'data\laya.log'
    $logErr = Join-Path $Root 'data\laya.err.log'

    if (-not (Test-Path (Join-Path $Root 'data'))) {
        New-Item -ItemType Directory -Path (Join-Path $Root 'data') -Force | Out-Null
    }

    Start-Process -FilePath $python `
        -ArgumentList @($scriptService, '--host', '127.0.0.1', '--port', "$Port") `
        -WorkingDirectory $Root `
        -WindowStyle Hidden `
        -RedirectStandardOutput $logOut `
        -RedirectStandardError $logErr | Out-Null

    Log "Daemon avviato in background su porta $Port (Log: data\laya.log)"
    Start-Sleep -Seconds 2
}

# Verifica veloce dopo avvio
try {
    $res = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 3 -ErrorAction Stop
    Log "Health check superato: status=$($res.status), device=$($res.device), modelli=$($res.loaded -join ', ')"
} catch {
    Warn "Inizializzazione in corso o modelli in caricamento (controlla data\laya.log)."
}
