# SPDX-License-Identifier: Apache-2.0
# HyperSpace AGI 1.05 - Setup e Automazione 24/7 per i nodi Windows 11 (HP OMEN 16, ASUS V16)
#
# Configura l'ambiente Windows 11 host e WSL2 per l'operatività continua H24:
# 1. Configurazione C:\Users\<utente>\.wslconfig (16 GB RAM, 8 processori, 8 GB swap)
# 2. Hardening energetico Windows (disattivazione sospensione AC, ibernazione, coperchio)
# 3. Registrazione del Watchdog Termico (scripts\diagnostics\omen_watchdog_247.py)
# 4. Registrazione dell'avvio automatico di start-tutto.ps1
#
# Uso:
#   .\scripts\setup-omen-247.ps1          # Applica configurazioni e registra servizi
#   .\scripts\setup-omen-247.ps1 -Check   # Verifica lo stato corrente
#   .\scripts\setup-omen-247.ps1 -Start   # Avvia subito tutti i servizi e il watchdog
#   .\scripts\setup-omen-247.ps1 -Stop    # Ferma i servizi

param(
    [switch]$Check,
    [switch]$Start,
    [switch]$Stop,
    [switch]$Force
)

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Log($m)  { Write-Host "[omen-247] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "[omen-247] AVVISO: $m" -ForegroundColor Yellow }
function Fail($m) { Write-Host "[omen-247] ERRORE: $m" -ForegroundColor Red }
function Head($m) { Write-Host ""; Write-Host "== $m ==" -ForegroundColor Cyan }

$wslConfigPath = Join-Path $env:USERPROFILE ".wslconfig"
$startupDir = [Environment]::GetFolderPath('Startup')
$nodeName = $env:COMPUTERNAME

# WSL2 dimensionato sulla macchina (OMEN e ASUS hanno RAM diverse): meta' della RAM
# fisica, al massimo 16 GB; al massimo 8 processori logici.
$cs = Get-CimInstance Win32_ComputerSystem -ErrorAction SilentlyContinue
$totalRamGB = if ($cs) { [math]::Floor($cs.TotalPhysicalMemory / 1GB) } else { 16 }
$wslMemGB = [math]::Max(4, [math]::Min(16, [math]::Floor($totalRamGB / 2)))
$wslCpus = if ($cs) { [math]::Min(8, $cs.NumberOfLogicalProcessors) } else { 8 }
$python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

$watchdogScript = Join-Path $Root "scripts\diagnostics\omen_watchdog_247.py"
$watchdogLnk = Join-Path $startupDir "HyperSpace OMEN Watchdog.lnk"
$startTuttoScript = Join-Path $Root "scripts\start-tutto.ps1"
$startTuttoLnk = Join-Path $startupDir "HyperSpace Start-Tutto.lnk"

# Servizi 24/7 come attività pianificate (non .lnk in shell:startup, che partono solo
# al login): all'accensione anche senza login, riavvio se si chiudono.
# - Dev Loop: cicli di sviluppo/ricerca; finché lo stack Docker non è su, i cicli
#   falliscono e riprovano al giro dopo.
# - Mesh Patch Watcher: l'unico processo che applica al repository le patch della
#   git mesh depositate dal nodo (con test del ruolo e rollback).
$nodeRole = if ($env:NODE_ROLE) { $env:NODE_ROLE } else { "worker-gpu" }
$bgTasks = @(
    @{
        Name  = "HyperSpace Dev Loop 247"; Label = "Dev Loop 24/7"; Match = "omen_dev_loop_247\.py"
        Args  = "`"$(Join-Path $Root 'scripts\omen_dev_loop_247.py')`" --daemon --interval 300"
        Out   = Join-Path $Root "data\omen_dev_loop.out.log"
    },
    @{
        Name  = "HyperSpace Mesh Patch Watcher"; Label = "Mesh Patch Watcher"; Match = "mesh_patch_watcher\.py"
        Args  = "`"$(Join-Path $Root 'scripts\mesh_patch_watcher.py')`" --patches data/node-1/mesh-patches --repo . --role $nodeRole --run-tests"
        Out   = Join-Path $Root "data\mesh_patch_watcher.out.log"
    }
)

function Register-BackgroundTask($t) {
    $cmdLine = "/c `"`"$python`" $($t.Args) >> `"$($t.Out)`" 2>&1`""
    $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $cmdLine -WorkingDirectory $Root
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $trigger.Delay = "PT3M"
    # S4U: gira come l'utente corrente anche senza sessione aperta, senza salvare la password.
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 5) `
        -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName $t.Name -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings -Force -ErrorAction Stop | Out-Null
}

function Get-BackgroundProcs($t) {
    Get-CimInstance Win32_Process -Filter "Name like '%python%'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -match $t.Match }
}

# --- STOP ---
if ($Stop) {
    Head "Arresto Servizi 24/7 ($nodeName)"
    $wProcs = Get-CimInstance Win32_Process -Filter "Name like '%python%'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -match "omen_watchdog_247\.py" }
    foreach ($p in $wProcs) {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        Log "Fermato Watchdog Termico (PID $($p.ProcessId))"
    }

    foreach ($t in $bgTasks) {
        if (Get-ScheduledTask -TaskName $t.Name -ErrorAction SilentlyContinue) {
            Stop-ScheduledTask -TaskName $t.Name -ErrorAction SilentlyContinue
        }
        foreach ($p in (Get-BackgroundProcs $t)) {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
            Log "Fermato $($t.Label) (PID $($p.ProcessId)); ripartira' al prossimo avvio"
        }
    }

    if (Test-Path $startTuttoScript) {
        & powershell -NoProfile -ExecutionPolicy Bypass -File $startTuttoScript -Stop
    }
    exit 0
}

# --- CHECK ---
if ($Check) {
    Head "Verifica Stato 24/7 ($nodeName, RAM ${totalRamGB}GB)"

    # 1. WSL2 Config
    if (Test-Path $wslConfigPath) {
        $cfg = Get-Content $wslConfigPath -Raw
        if ($cfg -match "memory=${wslMemGB}GB") {
            Log "WSL2 Config: Ottimale (${wslMemGB}GB RAM allocata in $wslConfigPath)"
        } else {
            Warn "WSL2 Config: presente ma con parametri diversi:`n$cfg"
        }
    } else {
        Warn "WSL2 Config: NON trovato ($wslConfigPath non esiste). WSL2 potrebbe saturare la RAM."
    }

    # 2. Watchdog
    $wRunning = [bool](Get-CimInstance Win32_Process -Filter "Name like '%python%'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -match "omen_watchdog_247\.py" })
    if ($wRunning) { Log "Supervisore Termico Watchdog: ATTIVO" }
    else { Warn "Supervisore Termico Watchdog: SPENTO" }

    # 3. Autostart Lnk
    if (Test-Path $watchdogLnk) { Log "Autostart Watchdog: Configurato in shell:startup" }
    else { Warn "Autostart Watchdog: Manca collegamento $watchdogLnk" }

    if (Test-Path $startTuttoLnk) { Log "Autostart Stack: Configurato in shell:startup" }
    else { Warn "Autostart Stack: Manca collegamento $startTuttoLnk" }

    # Servizi 24/7 (attività pianificate)
    foreach ($t in $bgTasks) {
        $task = Get-ScheduledTask -TaskName $t.Name -ErrorAction SilentlyContinue
        if ($task) { Log "Attivita' $($t.Label): registrata (stato: $($task.State))" }
        else { Warn "Attivita' $($t.Label): NON registrata (esegui lo script senza parametri, da amministratore)" }
        $procs = @(Get-BackgroundProcs $t)
        if ($procs.Count -eq 1) { Log "$($t.Label): IN ESECUZIONE" }
        elseif ($procs.Count -gt 1) { Warn "$($t.Label): $($procs.Count) istanze attive (dovrebbe essere una sola)" }
        else { Warn "$($t.Label): FERMO" }
        if (Test-Path $t.Out) {
            Log "Ultime righe di $($t.Out) :"
            Get-Content $t.Out -Tail 5 | ForEach-Object { Write-Host "    $_" }
        }
    }
    & $python -c "import cryptography" 2>$null
    if ($LASTEXITCODE -ne 0) { Warn "Il watcher richiede 'cryptography' nel .venv: uv pip install --python `"$python`" cryptography" }

    # 4. Verifica Porte
    $ports = @(8081, 11434, 8188, 8098, 8085)
    foreach ($pt in $ports) {
        $open = [bool](Get-NetTCPConnection -LocalPort $pt -State Listen -ErrorAction SilentlyContinue)
        if ($open) { Log "Porta $pt : IN ASCOLTO" }
        else { Warn "Porta $pt : Chiusa/Non in ascolto" }
    }

    exit 0
}

# --- CONFIGURAZIONE E SETUP ---
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Fail "Serve PowerShell da amministratore (tasto destro > Esegui come amministratore) per registrare Dev Loop e Mesh Patch Watcher."
    exit 1
}

Head "Configurazione $nodeName per Lavoro Continuo 24/7"

# 1. Scrittura .wslconfig
Log "1. Configurazione WSL2 VM (~/.wslconfig)..."
$wslContent = @"
[wsl2]
memory=${wslMemGB}GB
processors=$wslCpus
swap=8GB
localhostForwarding=true
"@

if (Test-Path $wslConfigPath) {
    $existing = Get-Content $wslConfigPath -Raw
    if ($existing.Trim() -ne $wslContent.Trim()) {
        Copy-Item $wslConfigPath "$wslConfigPath.bak" -Force
        Set-Content -Path $wslConfigPath -Value $wslContent -Encoding Ascii
        Log "File $wslConfigPath aggiornato (backup in .bak)"
    } else {
        Log "File $wslConfigPath gia' allineato (${wslMemGB}GB RAM, $wslCpus CPU)."
    }
} else {
    Set-Content -Path $wslConfigPath -Value $wslContent -Encoding Ascii
    Log "Creato nuovo file $wslConfigPath (${wslMemGB}GB RAM su ${totalRamGB}GB, $wslCpus CPU, 8GB Swap)"
}

# 2. Hardening Energetico Powercfg
Log "2. Hardening Energetico Windows (No-Sleep & No-Lid-Action)..."
try {
    # Mai sospendere quando collegato alla corrente
    & powercfg -change -standby-timeout-ac 0 2>$null
    & powercfg -change -hibernate-timeout-ac 0 2>$null
    # Spegni schermo dopo 5 minuti per evitare calore del display
    & powercfg -change -monitor-timeout-ac 5 2>$null
    # Chiudi coperchio = Nessuna azione
    & powercfg -setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0 2>$null
    & powercfg -SetActive SCHEME_CURRENT 2>$null
    Log "Criteri energetici applicati con successo: sospensione MAI, monitor 5 min, coperchio INERTE."
} catch {
    Warn "Impossibile applicare tutti i comandi powercfg (richiede privilegi standard o admin): $_"
}

# 3. Creazione Collegamenti Startup & Hermes Shadow Memory
Log "3. Configurazione Hermes Shadow Memory e Registrazione Servizi di Autostart..."
$wscript = New-Object -ComObject WScript.Shell
$hermesBridgeScript = Join-Path $Root "scripts\start_hermes_memory_bridge.ps1"
$tokenFile = Join-Path $Root "data\hermes-memory.token"

# Generazione token di memoria se non presente
if (-not (Test-Path $tokenFile)) {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $hexToken = -join ($bytes | ForEach-Object { "{0:x2}" -f $_ })
    $tokenDir = Split-Path -Parent $tokenFile
    if (-not (Test-Path $tokenDir)) { New-Item -ItemType Directory -Path $tokenDir -Force | Out-Null }
    Set-Content -Path $tokenFile -Value $hexToken -NoNewline -Encoding Ascii
    Log "Generato token crittografico Hermes in $tokenFile"
}
$shadowDir = Join-Path $Root "data\hermes_shadow"
if (-not (Test-Path $shadowDir)) { New-Item -ItemType Directory -Path $shadowDir -Force | Out-Null }

# Shortcut Hermes Shadow Memory Bridge
$hLnkPath = Join-Path $startupDir "HyperSpace Hermes Shadow Bridge.lnk"
$hLnk = $wscript.CreateShortcut($hLnkPath)
$hLnk.TargetPath = "powershell.exe"
$hLnk.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$hermesBridgeScript`""
$hLnk.WorkingDirectory = $Root
$hLnk.WindowStyle = 7
$hLnk.Description = "HyperSpace Hermes Shadow Memory Bridge (porta 8098)"
$hLnk.Save()
Log "Creato collegamento di avvio: $hLnkPath"

# Shortcut Watchdog
$wLnk = $wscript.CreateShortcut($watchdogLnk)
$wLnk.TargetPath = $python
$wLnk.Arguments = "`"$watchdogScript`" --daemon --interval 30"
$wLnk.WorkingDirectory = $Root
$wLnk.WindowStyle = 7 # Minimized/Hidden
$wLnk.Description = "HyperSpace Thermal Watchdog & 24/7 Health Supervisor ($nodeName)"
$wLnk.Save()
Log "Creato collegamento di avvio: $watchdogLnk"

# Shortcut Start-Tutto
$tLnk = $wscript.CreateShortcut($startTuttoLnk)
$tLnk.TargetPath = "powershell.exe"
$tLnk.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$startTuttoScript`""
$tLnk.WorkingDirectory = $Root
$tLnk.WindowStyle = 7
$tLnk.Description = "HyperSpace AGI Start-Tutto Launcher"
$tLnk.Save()
Log "Creato collegamento di avvio: $startTuttoLnk"

# Attività pianificate 24/7 (richiede PowerShell da amministratore)
foreach ($t in $bgTasks) {
    try {
        Register-BackgroundTask $t
        Log "Registrata attivita' pianificata '$($t.Name)' (all'accensione, anche senza login; log: $($t.Out))"
    } catch {
        Warn "Impossibile registrare '$($t.Name)': $_"
    }
}

# 4. Avviso Batteria & Dissipazione
Head "PROMEMORIA SICUREZZA FISICA HARDWARE"
Write-Host "1. BATTERIA: nel BIOS o nell'utility del produttore (OMEN Gaming Hub, MyASUS) attiva la protezione/limite di carica." -ForegroundColor Yellow
Write-Host "2. DISSIPAZIONE: Rialza il retro del laptop di 3-5 cm per mantenere la GPU sotto i 75 gradi." -ForegroundColor Yellow
Write-Host "3. COPERCHIO: Lascia il display leggermente socchiuso a 30 gradi per far sfiatare il calore della tastiera." -ForegroundColor Yellow

# 5. Avvio Immediato se richiesto
if ($Start) {
    Head "Avvio Immediato dei Servizi"
    # Avvio Hermes Shadow Bridge se non in ascolto
    $hermesOpen = [bool](Get-NetTCPConnection -LocalPort 8098 -State Listen -ErrorAction SilentlyContinue)
    if (-not $hermesOpen) {
        Log "Avvio Hermes Shadow Memory Bridge (porta 8098)..."
        Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$hermesBridgeScript`"" -WorkingDirectory $Root -WindowStyle Hidden
    } else {
        Log "Hermes Shadow Memory Bridge gia' attivo (porta 8098)"
    }
    Log "Avvio del Watchdog..."
    Start-Process -FilePath $python -ArgumentList "`"$watchdogScript`" --daemon --interval 30" -WorkingDirectory $Root -WindowStyle Hidden
    foreach ($t in $bgTasks) {
        if (@(Get-BackgroundProcs $t).Count -gt 0) {
            Log "$($t.Label) gia' in esecuzione"
        } elseif (Get-ScheduledTask -TaskName $t.Name -ErrorAction SilentlyContinue) {
            Log "Avvio di $($t.Label) (attivita' pianificata)..."
            Start-ScheduledTask -TaskName $t.Name
        } else {
            Warn "$($t.Label) non registrato: rilancia lo script da amministratore"
        }
    }
    Log "Avvio dello stack HyperSpace Start-Tutto..."
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$startTuttoScript`"" -WorkingDirectory $Root
    Log "Tutti i servizi sono stati lanciati in background."
}

Head "Completato"
Log "Configurazione 24/7 completata. Per verificare: .\scripts\setup-omen-247.ps1 -Check"
