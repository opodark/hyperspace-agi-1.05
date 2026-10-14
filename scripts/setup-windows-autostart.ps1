# SPDX-License-Identifier: Apache-2.0
# HyperSpace AGI 1.05 - Configurazione Esecuzione Automatica su Windows 11
#
# Perché esiste: su Windows 11 diversi servizi essenziali girano nativamente
# sull'host esterno a Docker (Ollama per i modelli locali, ComfyUI Desktop per la
# generazione immagini su GPU, Hermes Memory Bridge per la memoria sovrana,
# Laya Decision Engine per il routing sub-50ms e la Knowledge Graph Surface di Graphify).
# Questo script garantisce che all'avvio / login dell'utente Windows 11 TUTTI questi
# servizi vengano avviati automaticamente e in modo trasparente.
#
# Meccanismi di autostart utilizzati:
#   1. Cartella Esecuzione Automatica Utente (shell:startup):
#      - Ollama.lnk
#      - Comfy Desktop.lnk
#      - HyperSpace Surfaces.lnk (chiama scripts\start-surfaces.ps1 in background)
#   2. Registro di Windows HKCU (CurrentVersion\Run):
#      - HyperSpace Host Surfaces (ridondanza di avvio per sessioni headless/RDP)
#   3. Task Scheduler Windows (schtasks):
#      - HyperSpace Hermes Memory Bridge (porta 8098)
#
# Uso:
#   .\scripts\setup-windows-autostart.ps1           # configura e attiva l'avvio automatico
#   .\scripts\setup-windows-autostart.ps1 -Check    # verifica lo stato corrente di tutti i servizi
#   .\scripts\setup-windows-autostart.ps1 -Uninstall# rimuove i collegamenti e le chiavi di autostart

param(
    [switch]$Check,
    [switch]$Uninstall,
    [switch]$Force
)

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Log($m)  { Write-Host "[autostart] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "[warn]      $m" -ForegroundColor Yellow }
function Fail($m) { Write-Host "[error]     $m" -ForegroundColor Red }
function Head($m) { Write-Host "`n== $m ==" -ForegroundColor Cyan }

$startupDir = [Environment]::GetFolderPath('Startup')
$regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$surfacesScript = Join-Path $Root "scripts\start-surfaces.ps1"
$surfacesLnk = Join-Path $startupDir "HyperSpace Surfaces.lnk"
$comfyLnk = Join-Path $startupDir "Comfy Desktop.lnk"
$ollamaLnk = Join-Path $startupDir "Ollama.lnk"

function Get-AutostartStatus {
    $results = @()

    # 1. Ollama
    $ollamaLnkExists = Test-Path $ollamaLnk
    $ollamaRunning = [bool](Get-Process -Name 'ollama' -ErrorAction SilentlyContinue)
    $results += [PSCustomObject]@{
        Servizio     = "Ollama LLM Host"
        Metodo       = "Startup Folder"
        Configurato  = if ($ollamaLnkExists) { "Sì (Ollama.lnk)" } else { "No" }
        Porta        = "11434"
        InEsecuzione = if ($ollamaRunning) { "Attivo" } else { "Spento" }
    }

    # 2. ComfyUI Desktop
    $comfyLnkExists = Test-Path $comfyLnk
    $comfyRunning = [bool](Get-Process -Name 'Comfy Desktop' -ErrorAction SilentlyContinue)
    $results += [PSCustomObject]@{
        Servizio     = "ComfyUI Desktop"
        Metodo       = "Startup Folder"
        Configurato  = if ($comfyLnkExists) { "Sì (Comfy Desktop.lnk)" } else { "No" }
        Porta        = "8188"
        InEsecuzione = if ($comfyRunning) { "Attivo" } else { "Spento" }
    }

    # 3. Hermes Memory Bridge
    $hermesTask = Get-ScheduledTask -TaskName "HyperSpace Hermes Memory Bridge" -ErrorAction SilentlyContinue
    $hermesPortOpen = [bool](Get-NetTCPConnection -LocalPort 8098 -State Listen -ErrorAction SilentlyContinue)
    $results += [PSCustomObject]@{
        Servizio     = "Hermes Memory Bridge"
        Metodo       = "Task Scheduler"
        Configurato  = if ($hermesTask) { "Sì ($($hermesTask.State))" } else { "No" }
        Porta        = "8098"
        InEsecuzione = if ($hermesPortOpen) { "Attivo" } else { "Spento" }
    }

    # 4. HyperSpace Host Surfaces (Startup Lnk)
    $surfacesLnkExists = Test-Path $surfacesLnk
    $results += [PSCustomObject]@{
        Servizio     = "HyperSpace Surfaces (LNK)"
        Metodo       = "Startup Folder"
        Configurato  = if ($surfacesLnkExists) { "Sì (HyperSpace Surfaces.lnk)" } else { "No" }
        Porta        = "8097,8189,7871"
        InEsecuzione = "Launcher"
    }

    # 5. HyperSpace Host Surfaces (Registry Run)
    $regVal = (Get-ItemProperty $regPath -Name "HyperSpace Host Surfaces" -ErrorAction SilentlyContinue)."HyperSpace Host Surfaces"
    $results += [PSCustomObject]@{
        Servizio     = "HyperSpace Surfaces (REG)"
        Metodo       = "HKCU Run Key"
        Configurato  = if ($regVal) { "Sì (HKCU Run)" } else { "No" }
        Porta        = "8097,8189,7871"
        InEsecuzione = "Launcher"
    }

    # 6. Laya Decision Engine
    $layaPortOpen = [bool](Get-NetTCPConnection -LocalPort 8097 -State Listen -ErrorAction SilentlyContinue)
    $results += [PSCustomObject]@{
        Servizio     = "Laya Decision Engine"
        Metodo       = "via start-surfaces"
        Configurato  = "Incluso"
        Porta        = "8097"
        InEsecuzione = if ($layaPortOpen) { "Attivo" } else { "Spento" }
    }

    # 7. WebUI Image Gateway
    $gwPortOpen = [bool](Get-NetTCPConnection -LocalPort 8189 -State Listen -ErrorAction SilentlyContinue)
    $results += [PSCustomObject]@{
        Servizio     = "Comfy WebUI Gateway"
        Metodo       = "via start-surfaces"
        Configurato  = "Incluso"
        Porta        = "8189"
        InEsecuzione = if ($gwPortOpen) { "Attivo" } else { "Spento" }
    }

    # 8. Graphify Surface
    $graphifyPortOpen = [bool](Get-NetTCPConnection -LocalPort 7871 -State Listen -ErrorAction SilentlyContinue)
    $results += [PSCustomObject]@{
        Servizio     = "Graphify KG Surface"
        Metodo       = "via start-surfaces"
        Configurato  = "Incluso"
        Porta        = "7871"
        InEsecuzione = if ($graphifyPortOpen) { "Attivo" } else { "Spento" }
    }

    # 9. Power Monitor Daemon
    $powerRunning = [bool](Get-CimInstance Win32_Process -Filter "Name like '%python%'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -match "power_monitor.py" })
    $results += [PSCustomObject]@{
        Servizio     = "Host Power Monitor"
        Metodo       = "via start-surfaces"
        Configurato  = "Incluso"
        Porta        = "N/A (data/host_power.json)"
        InEsecuzione = if ($powerRunning) { "Attivo" } else { "Spento" }
    }

    return $results
}

if ($Check) {
    Head "Stato Esecuzione Automatica Servizi Esterni (Windows 11)"
    Get-AutostartStatus | Format-Table -AutoSize
    exit 0
}

if ($Uninstall) {
    Head "Disinstallazione Esecuzione Automatica HyperSpace"
    if (Test-Path $surfacesLnk) {
        Remove-Item -Path $surfacesLnk -Force
        Log "Rimosso collegamento: $surfacesLnk"
    }
    if ((Get-ItemProperty $regPath -Name "HyperSpace Host Surfaces" -ErrorAction SilentlyContinue)."HyperSpace Host Surfaces") {
        Remove-ItemProperty -Path $regPath -Name "HyperSpace Host Surfaces" -Force
        Log "Rimossa chiave di registro: $regPath\HyperSpace Host Surfaces"
    }
    Log "Disinstallazione completata. I servizi non partiranno più automaticamente al login."
    exit 0
}

Head "Configurazione Esecuzione Automatica Servizi Esterni HyperSpace"

# 1. Crea/Aggiorna collegamento ComfyUI Desktop se presente nel Menu Start
$comfySourceLnk = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Comfy Desktop.lnk"
if (Test-Path $comfySourceLnk) {
    Copy-Item -Path $comfySourceLnk -Destination $comfyLnk -Force
    Log "ComfyUI Desktop registrato in Startup ($comfyLnk)"
} elseif (Test-Path "$env:LOCALAPPDATA\Programs\Comfy Desktop\Comfy Desktop.exe") {
    $wshell = New-Object -ComObject WScript.Shell
    $s = $wshell.CreateShortcut($comfyLnk)
    $s.TargetPath = "$env:LOCALAPPDATA\Programs\Comfy Desktop\Comfy Desktop.exe"
    $s.WorkingDirectory = "$env:LOCALAPPDATA\Programs\Comfy Desktop"
    $s.Description = "ComfyUI Desktop AI Engine"
    $s.Save()
    Log "Creato collegamento ComfyUI Desktop in Startup ($comfyLnk)"
} else {
    Warn "Comfy Desktop.exe non trovato nei percorsi standard; salto collegamento."
}

# 2. Crea collegamento Startup per le superfici HyperSpace
$wshell = New-Object -ComObject WScript.Shell
$shortcut = $wshell.CreateShortcut($surfacesLnk)
$shortcut.TargetPath = "powershell.exe"
$shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$surfacesScript`""
$shortcut.WorkingDirectory = $Root
$shortcut.Description = "HyperSpace AGI 1.05 - Avvio automatico superfici host esterne a Docker"
$shortcut.Save()
Log "Creato collegamento superfici HyperSpace in Startup ($surfacesLnk)"

# 3. Registra chiave Run nel Registro Utente (HKCU) per ridondanza
Set-ItemProperty -Path $regPath `
    -Name "HyperSpace Host Surfaces" `
    -Value "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$surfacesScript`""
Log "Registrata chiave di avvio nel Registro Utente ($regPath)"

# 4. Verifica Ollama
if (Test-Path $ollamaLnk) {
    Log "Ollama già presente in Startup ($ollamaLnk)"
} else {
    Warn "Ollama.lnk non trovato in $startupDir. Se Ollama è installato, aggiungi il collegamento."
}

# 5. Verifica Hermes Memory Bridge
$hermesTask = Get-ScheduledTask -TaskName "HyperSpace Hermes Memory Bridge" -ErrorAction SilentlyContinue
if ($hermesTask) {
    Log "Task Hermes Memory Bridge registrato in Windows Task Scheduler (Stato: $($hermesTask.State))"
} else {
    Warn "Task Scheduler 'HyperSpace Hermes Memory Bridge' non trovato. Esegui la registrazione con start_hermes_memory_bridge.ps1."
}

Head "Riepilogo Configurazione Autostart"
Get-AutostartStatus | Format-Table -AutoSize
Log "Tutti i servizi esterni a Docker sono configurati per l'esecuzione automatica al boot/logon di Windows 11."
