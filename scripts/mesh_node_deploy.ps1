# SPDX-License-Identifier: Apache-2.0
# Deploy del nodo Git Mesh su Windows: pull, rebuild container e avvio watcher.
#
# Il nodo (container) ha il repo in sola lettura, quindi riceve e VERIFICA le
# patch ma le deposita in <data>/node-1/mesh-patches/. Questo script ricompila il
# nodo e avvia il watcher sull'host, l'unico processo autorizzato ad applicare le
# patch al repository.
#
# Uso (da PowerShell):
#   .\scripts\mesh_node_deploy.ps1                          # rebuild + watcher
#   .\scripts\mesh_node_deploy.ps1 -Pull                    # prima: git pull
#   .\scripts\mesh_node_deploy.ps1 -Test -Target http://100.104.238.125:8081
param(
  [switch]$Pull,
  [switch]$Test,
  [string]$Target = "http://127.0.0.1:8081"
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

if ($Pull) {
  Write-Host "[deploy] git pull..."
  git fetch origin --prune
  git pull --ff-only
}

Write-Host "[deploy] rebuild container (control-plane + nodo)..."
docker compose -f docker-compose.windows.yml up -d --build control-plane node-1

$running = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -like '*mesh_patch_watcher*' }
if ($running) {
  Write-Host "[deploy] watcher già attivo"
} else {
  $role = if ($env:NODE_ROLE) { $env:NODE_ROLE } else { "worker-gpu" }
  Start-Process -FilePath "python" -WindowStyle Hidden -ArgumentList @(
    "scripts/mesh_patch_watcher.py",
    "--patches", "data/node-1/mesh-patches",
    "--repo", ".",
    "--role", $role,
    "--run-tests"
  )
  Write-Host "[deploy] watcher avviato (role: $role)"
}

if ($Test) {
  Write-Host "[deploy] test di propagazione verso $Target"
  python scripts/mesh_distribute.py --files README.md --target $Target
}
