# SPDX-License-Identifier: Apache-2.0
$ErrorActionPreference = "Continue"

$binDir = "C:\HyperSpace\bin\bonsai"
$serverExe = Join-Path $binDir "llama-server.exe"
$modelPath = "C:\HyperSpace\models\Ternary-Bonsai-2-27B-Uncensored-Heretic-PQ2_0.gguf"
$logDir = "C:\HyperSpace\logs"
$stdoutLog = Join-Path $logDir "bonsai-server.log"
$stderrLog = Join-Path $logDir "bonsai-server.err"

New-Item -ItemType Directory -Path $logDir -Force | Out-Null

# Stop any existing instance
Get-Process -Name "llama-server" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 1

$argsList = @(
    "-m", $modelPath,
    "--host", "127.0.0.1",
    "--port", "8082",
    "-ngl", "99",
    "--ctx-size", "8192",
    "--alias", "bonsai-2-abliterated",
    "--temp", "0.7",
    "--top-p", "0.95",
    "--jinja"
)

Write-Host "Launching llama-server for Bonsai 2..."
$proc = Start-Process -FilePath $serverExe -WorkingDirectory $binDir -ArgumentList $argsList -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -WindowStyle Hidden -PassThru

Write-Host "Started llama-server PID: $($proc.Id)"
Write-Host "Waiting for server to become healthy on port 8082..."

for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 2
    try {
        $res = Invoke-RestMethod -Uri "http://127.0.0.1:8082/health" -TimeoutSec 2 -ErrorAction Stop
        if ($res.status -eq "ok") {
            Write-Host "[SUCCESS] Bonsai 2 server is live and healthy on http://127.0.0.1:8082!"
            exit 0
        }
    } catch {
        # Still loading
    }
}

Write-Host "[WARN] Health check did not return 'ok' within 60s. Check logs at $stdoutLog"
