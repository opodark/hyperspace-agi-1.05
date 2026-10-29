# SPDX-License-Identifier: Apache-2.0
<#
.SYNOPSIS
    Script di automazione per il training Unsloth su HP OMEN 16 o ASUS V16 tramite WSL2.
.DESCRIPTION
    1. Verifica la presenza di WSL2 e della GPU NVIDIA (nvidia-smi).
    2. Esporta i dati sintetici di HyperSpace in formato Alpaca.
    3. Esegue lo script Python di fine-tuning dentro l'istanza WSL2 con Unsloth.
    4. Registra il modello GGUF risultante direttamente in Ollama.
#>

[CmdletBinding()]
param(
    [string]$Distro = "Ubuntu",
    [string]$Model = "unsloth/Qwen2.5-Coder-7B-Instruct-bnb-4bit",
    [int]$Epochs = 1
)

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "🦥 HYPERSPACE UNSLOTH LORA REFINERY — LAUNCHER WSL2" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

# 1. Verifica GPU
try {
    $gpu = nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    Write-Host "[✓] GPU Rilevata: $gpu" -ForegroundColor Green
} catch {
    Write-Warning "nvidia-smi non trovato. Assicurati che i driver NVIDIA siano aggiornati."
}

# 2. Generazione dataset
Write-Host "[1/3] Generazione dataset di addestramento dai log di HyperSpace..." -ForegroundColor Yellow
$pyCmd = "from shared.unsloth_dataset_adapter import UnslothDatasetAdapter; a = UnslothDatasetAdapter(); n = a.export_alpaca_json('data/unsloth_dataset.json'); print(f'Dataset generato con {n} campioni.')"
python -c $pyCmd

# 3. Esecuzione dentro WSL2
Write-Host "[2/3] Lancio training in WSL2 ($Distro)..." -ForegroundColor Yellow
$wslScript = "cd /mnt/c/Users/opo/hyperspace-agi-1.04 2>/dev/null || cd /Users/opo/hyperspace-agi-1.04; python3 scripts/unsloth/train_hyperspace_lora.py --model $Model --epochs $Epochs"
wsl -d $Distro bash -c $wslScript

Write-Host "[3/3] Operazione completata." -ForegroundColor Green
