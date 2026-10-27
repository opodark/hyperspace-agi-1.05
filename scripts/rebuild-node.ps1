# SPDX-License-Identifier: Apache-2.0
# Ricostruisce il container del nodo (servizio compose che finisce in "node-1")
# con lo stesso progetto, file compose e cartella con cui è stato avviato.
#
# Serve dopo un `git pull` che tocca node/, control-plane/ o shared/: il codice è
# dentro l'immagine, e la git mesh confronta il commit del repository, non quello
# dell'immagine. Su Mac, OMEN e ASUS progetto e nomi dei servizi sono diversi:
# lo script li legge dalle etichette com.docker.compose.* del container in esecuzione.
#
# Uso:
#   .\scripts\rebuild-node.ps1            # ricostruisce e riavvia il nodo
#   .\scripts\rebuild-node.ps1 -DryRun    # mostra solo cosa farebbe

param(
    [switch]$DryRun,
    [string]$ServicePattern = "node-1$"
)

$ErrorActionPreference = 'Stop'

$ctr = $null
foreach ($n in (docker ps --format "{{.Names}}")) {
    $l = docker inspect $n --format "{{json .Config.Labels}}" | ConvertFrom-Json
    if ($l."com.docker.compose.service" -match $ServicePattern) { $ctr = $n; break }
}
if (-not $ctr) {
    Write-Host "[rebuild-node] ERRORE: nessun container in esecuzione con servizio compose '$ServicePattern'" -ForegroundColor Red
    exit 1
}

$l = docker inspect $ctr --format "{{json .Config.Labels}}" | ConvertFrom-Json
$proj = $l."com.docker.compose.project"
$svc = $l."com.docker.compose.service"
$dir = $l."com.docker.compose.project.working_dir"
$fargs = ($l."com.docker.compose.project.config_files" -split ",") | ForEach-Object { "-f"; $_ }

Write-Host "[rebuild-node] Container: $ctr | progetto: $proj | servizio: $svc" -ForegroundColor Green
Write-Host "[rebuild-node] Cartella: $dir"
Write-Host "[rebuild-node] Comando: docker compose -p $proj $fargs up -d --build $svc"
if ($DryRun) { exit 0 }

Push-Location $dir
try {
    docker compose -p $proj @fargs up -d --build $svc
    if ($LASTEXITCODE -ne 0) { throw "docker compose ha restituito $LASTEXITCODE" }
} finally {
    Pop-Location
}
Write-Host "[rebuild-node] Nodo ricostruito." -ForegroundColor Green
