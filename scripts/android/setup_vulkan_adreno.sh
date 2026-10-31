#!/data/data/com.termux/files/usr/bin/bash
# SPDX-License-Identifier: Apache-2.0
# ==============================================================================
# HyperSpace AGI — setup_vulkan_adreno.sh
# Abilita l'accelerazione hardware GPU (Adreno 750) su Samsung S24 Ultra in Termux.
#
# Compila llama.cpp con backend Vulkan nativo (-DGGML_VULKAN=1) linkando il loader
# Vulkan di sistema Android per scaricare i layer LLM sulla GPU dell'S24 Ultra.
#
# Uso su S24 Ultra (dentro Termux):
#   bash ~/.00mesh/app/scripts/android/setup_vulkan_adreno.sh
# ==============================================================================

set -euo pipefail

G='\033[0;32m'; Y='\033[1;33m'; R='\033[0;31m'; C='\033[0;36m'; B='\033[1m'; N='\033[0m'
log()  { echo -e "${G}[vulkan-setup]${N} $*"; }
warn() { echo -e "${Y}[warn]${N}         $*"; }
err()  { echo -e "${R}[errore]${N}       $*"; exit 1; }

echo -e "\n${B}${C}⚡ HyperSpace — Abilitazione GPU Adreno 750 (Vulkan) su S24 Ultra${N}\n"

# 1. Verifica architettura
ARCH=$(uname -m)
if [ "$ARCH" != "aarch64" ]; then
    err "Architettura non supportata: $ARCH (richiesto aarch64 / S24 Ultra)"
fi

# 2. Installa dipendenze Termux
log "Aggiornamento pacchetti e installazione dipendenze di compilazione..."
pkg update -y || warn "pkg update ha segnalato avvisi, proseguo..."
pkg install -y git clang cmake ninja vulkan-loader vulkan-headers libandroid-support || err "Installazione pacchetti fallita"

# 3. Directory di lavoro
INSTALL_DIR="${HOME}/.00mesh/llama-vulkan"
mkdir -p "${INSTALL_DIR}"
cd "${INSTALL_DIR}"

# 4. Clone o aggiornamento di llama.cpp
if [ ! -d "llama.cpp" ]; then
    log "Download sorgenti llama.cpp..."
    git clone --depth 1 https://github.com/ggerganov/llama.cpp.git
else
    log "Aggiornamento sorgenti llama.cpp..."
    cd llama.cpp && git pull && cd ..
fi

cd llama.cpp

# 5. Configurazione e compilazione CMake con backend Vulkan
log "Configurazione CMake con flag Vulkan (-DGGML_VULKAN=1)..."
cmake -B build \
    -GNinja \
    -DGGML_VULKAN=1 \
    -DCMAKE_BUILD_TYPE=Release

log "Compilazione di llama-server e llama-cli su tutti i core..."
cmake --build build --config Release -j"$(nproc)" --target llama-server llama-cli

# 6. Verifica presenza binari
if [ ! -f "build/bin/llama-server" ]; then
    err "Compilazione fallita: build/bin/llama-server non trovato."
fi

# 7. Crea link simbolico in $PREFIX/bin
mkdir -p "${PREFIX}/bin"
ln -sf "${INSTALL_DIR}/llama.cpp/build/bin/llama-server" "${PREFIX}/bin/llama-server-vulkan"
ln -sf "${INSTALL_DIR}/llama.cpp/build/bin/llama-cli" "${PREFIX}/bin/llama-cli-vulkan"

log "Binari installati con successo:"
log "  - ${PREFIX}/bin/llama-server-vulkan"
log "  - ${PREFIX}/bin/llama-cli-vulkan"

# 8. Modello consigliato e script di avvio rapido
MODELS_DIR="${HOME}/.00mesh/models"
mkdir -p "${MODELS_DIR}"

cat << 'EOF' > "${PREFIX}/bin/00mesh-vulkan-start"
#!/data/data/com.termux/files/usr/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Avvia il server Vulkan per S24 Ultra su GPU Adreno 750
MODEL_PATH="${1:-$HOME/.00mesh/models/Qwen2.5-3B-Instruct-Q4_K_M.gguf}"
PORT="${2:-8080}"

if [ ! -f "$MODEL_PATH" ]; then
    echo "Modello non trovato in $MODEL_PATH"
    echo "Puoi scaricarlo con:"
    echo "  curl -L -o ~/.00mesh/models/Qwen2.5-3B-Instruct-Q4_K_M.gguf https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf"
    exit 1
fi

echo "Avvio llama-server Vulkan su GPU Adreno 750 (porta $PORT)..."
exec llama-server-vulkan \
    --model "$MODEL_PATH" \
    --host 0.0.0.0 \
    --port "$PORT" \
    -ngl 99 \
    --ctx-size 4096 \
    --threads 4 \
    --temp 0.2
EOF

chmod +x "${PREFIX}/bin/00mesh-vulkan-start"

echo -e "\n${G}================================================================${N}"
echo -e "${B}Accelerazione Hardware Vulkan configurata con successo!${N}"
echo -e "Per scaricare un modello 3B ultrarapido su S24 Ultra:"
echo -e "  ${C}curl -L -o ~/.00mesh/models/Qwen2.5-3B-Instruct-Q4_K_M.gguf https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf${N}"
echo -e "\nPer avviare il server GPU Adreno:"
echo -e "  ${C}00mesh-vulkan-start${N}"
echo -e "${G}================================================================${N}\n"
