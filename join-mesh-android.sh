#!/data/data/com.termux/files/usr/bin/bash
# SPDX-License-Identifier: Apache-2.0
# =============================================================
# HyperSpace AGI v1.05 — join-mesh-android.sh
# Trasforma un telefono Android in un nodo "mobile" della mesh, dentro Termux.
#
# Di giorno il telefono è una console (vede la mesh, resta in heartbeat);
# di notte, collegato al caricatore e fresco, diventa un worker: il gate di
# shared/mobile_gate.py apre il lavoro solo quando carica, batteria minima,
# temperatura e finestra oraria lo permettono.
#
# Prerequisiti (dalla STESSA fonte, F-Droid o GitHub — non mescolare con
# la versione del Play Store, che è ferma e incompatibile):
#   - Termux
#   - Termux:API   (lettura batteria e temperatura)
#   - Termux:Boot  (facoltativo, avvio automatico all'accensione)
#   - Tailscale    (app Android, per essere raggiungibile dalla mesh)
#
# Uso, dentro Termux:
#   bash join-mesh-android.sh
# oppure, una volta che lo script è sul branch principale:
#   bash <(curl -fsSL https://raw.githubusercontent.com/opodark/hyperspace-agi-1.05/main/join-mesh-android.sh)
#
# Perimetro: installa pacchetti Termux, scrive solo in ~/.00mesh,
# ~/.termux/boot/00mesh e $PREFIX/bin/00mesh. Non richiede root.
# =============================================================
set -uo pipefail

REPO_URL="${REPO_URL:-https://github.com/opodark/hyperspace-agi-1.05}"
REPO_BRANCH="${REPO_BRANCH:-main}"

HOME_DIR="${HOME}/.00mesh"
APP_DIR="${HOME_DIR}/app"
VENV="${HOME_DIR}/venv"
ENV_FILE="${HOME_DIR}/node.env"

G='\033[0;32m'; Y='\033[1;33m'; R='\033[0;31m'; C='\033[0;36m'; B='\033[1m'; N='\033[0m'
log()  { echo -e "${G}[join-android]${N} $*"; }
warn() { echo -e "${Y}[warn]${N}         $*"; }
err()  { echo -e "${R}[errore]${N}       $*"; exit 1; }
hdr()  { echo -e "\n${B}${C}$*${N}"; }

# read da /dev/tty: lo script funziona anche lanciato con bash <(curl ...)
ask() {  # variabile, domanda, default
    local __var="$1" __q="$2" __def="${3:-}" __ans=""
    if [ -n "$__def" ]; then
        read -rp "  ${__q} [${__def}]: " __ans < /dev/tty
    else
        read -rp "  ${__q}: " __ans < /dev/tty
    fi
    __ans="$(echo "${__ans:-$__def}" | tr -d ' ')"
    printf -v "$__var" '%s' "$__ans"
}

echo -e "\n${B}${C}⧢  HyperSpace AGI — nodo mobile Android${N}"
echo    "    console di giorno, worker di notte"

# ── 0. Ambiente ─────────────────────────────────────────
hdr "0/7 — Ambiente"
case "${PREFIX:-}" in
    */com.termux/*) log "Termux rilevato ✓" ;;
    *) err "questo script va eseguito dentro Termux su Android" ;;
esac
[ "$(uname -m)" = "aarch64" ] || warn "architettura $(uname -m): testato su aarch64 (S24 Ultra)"

# ── 1. Pacchetti ────────────────────────────────────────
hdr "1/7 — Pacchetti Termux"
pkg update -y || warn "pkg update non riuscito: proseguo con l'indice attuale"
pkg install -y python git curl termux-api python-cryptography \
    || err "installazione pacchetti base fallita"

SERVE_MODELS=true
if pkg install -y ollama; then
    log "ollama ✓"
else
    warn "ollama non disponibile nei repository Termux di questo telefono:"
    warn "il nodo entra in mesh come console, senza servire modelli."
    SERVE_MODELS=false
fi

# pydantic-core (dipendenza di FastAPI) è in Rust e su Termux non ha wheel
# precompilate. Prima si prova il pacchetto Termux; se manca serve la
# toolchain Rust e pip lo compila (una volta sola, 10-20 minuti).
if ! python -c "import pydantic_core" 2>/dev/null; then
    if ! pkg install -y python-pydantic-core 2>/dev/null; then
        log "pydantic-core verrà compilato: installo Rust (una tantum)"
        pkg install -y rust binutils || err "toolchain Rust non installabile"
    fi
fi

if timeout 8 termux-battery-status >/dev/null 2>&1; then
    log "Termux:API risponde ✓ (batteria e temperatura leggibili)"
else
    warn "termux-battery-status non risponde: installa l'app Termux:API dalla"
    warn "stessa fonte di Termux. Senza, il nodo si considera a batteria e non lavora."
fi

# ── 2. Codice del nodo ──────────────────────────────────
hdr "2/7 — Codice del nodo"
mkdir -p "$HOME_DIR"
if [ -d "$APP_DIR/.git" ]; then
    git -C "$APP_DIR" pull --ff-only || warn "aggiornamento non riuscito, uso il codice presente"
else
    # Solo node/ e shared/: il resto del repository (sito, editor, media)
    # non serve al telefono.
    git clone --depth 1 --filter=blob:none --sparse --branch "$REPO_BRANCH" "$REPO_URL" "$APP_DIR" \
        || err "clone di $REPO_URL fallito"
    git -C "$APP_DIR" sparse-checkout set node shared scripts/android \
        || err "sparse-checkout fallito"
fi
[ -f "$APP_DIR/shared/mobile_gate.py" ] \
    || err "il branch $REPO_BRANCH non contiene ancora il supporto mobile (shared/mobile_gate.py)"
log "codice in $APP_DIR ✓"

# ── 3. Ambiente Python ──────────────────────────────────
hdr "3/7 — Ambiente Python"
# --system-site-packages: cryptography arriva già compilata da pkg.
[ -x "$VENV/bin/python" ] || python -m venv --system-site-packages "$VENV" || err "venv non creato"
# uvicorn senza [standard]: uvloop/httptools/watchfiles andrebbero compilati
# e al nodo non servono.
"$VENV/bin/pip" install --upgrade fastapi uvicorn httpx requests \
    || err "installazione dipendenze Python fallita"
"$VENV/bin/python" -c "import fastapi, uvicorn, httpx, requests, cryptography" \
    || err "dipendenze Python incomplete"
log "fastapi, uvicorn, httpx, requests, cryptography ✓"

# ── 4. Rete: Tailscale ──────────────────────────────────
hdr "4/7 — Rete"
# Indirizzo sorgente verso 100.100.100.100 (il resolver di Tailscale): se la
# VPN è attiva è l'IP Tailscale del telefono. Funziona senza root.
TS_IP="$(python - <<'PYEOF' 2>/dev/null
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("100.100.100.100", 53))
ip = s.getsockname()[0]
print(ip if ip.startswith("100.") else "")
PYEOF
)"
if [ -n "$TS_IP" ]; then
    log "Tailscale attivo, IP del telefono: ${C}${TS_IP}${N}"
    DEFAULT_ENDPOINT="http://${TS_IP}:8084"
    DEFAULT_BIND="$TS_IP"
else
    warn "Tailscale non rilevato: apri l'app Tailscale e attiva la VPN, poi"
    warn "rilancia lo script. Senza, gli hub non possono contattare il telefono."
    DEFAULT_ENDPOINT=""
    DEFAULT_BIND="127.0.0.1"
fi

echo ""
echo "  Dove gira il control-plane della tua mesh (il cockpit sul Mac)?"
echo "  Con Tailscale è l'IP 100.x del Mac, porta 8085."
ask CP_URL "CONTROL_PLANE_URL (es. http://100.x.y.z:8085)" ""
CP_URL="${CP_URL%/}"
[ -n "$CP_URL" ] || err "serve l'URL del control-plane"
CP_HOST="$(echo "$CP_URL" | sed -E 's#^https?://([^:/]+).*#\1#')"
ask REG_URL "REGISTRY_URL" "http://${CP_HOST}:8086"
ask PEERS "BOOT_PEERS (hub separati da virgola)" "$CP_URL"
ask PUBLIC_EP "PUBLIC_ENDPOINT di questo telefono" "$DEFAULT_ENDPOINT"

if curl -sf --max-time 6 "${CP_URL}/health" >/dev/null 2>&1; then
    log "control-plane raggiungibile ✓"
else
    warn "control-plane non risponde su ${CP_URL}/health: controlla Tailscale e che il Mac sia acceso"
fi

# ── 5. Lavoro notturno ──────────────────────────────────
hdr "5/7 — Regole di lavoro"
echo "  Il telefono lavora per la mesh solo se TUTTE queste condizioni valgono:"
echo "  collegato al caricatore, batteria sopra il minimo, temperatura sotto"
echo "  la soglia, e dentro la finestra oraria (vuota = sempre)."
echo ""
ask WINDOW "Finestra di lavoro HH:MM-HH:MM" "23:00-07:00"
ask MIN_PCT "Batteria minima %" "40"
ask MAX_TEMP "Temperatura batteria massima °C (intero)" "41"
[[ "$WINDOW" =~ ^([0-9]{2}:[0-9]{2}-[0-9]{2}:[0-9]{2})?$ ]] || { warn "finestra non valida, uso 23:00-07:00"; WINDOW="23:00-07:00"; }
[[ "$MIN_PCT" =~ ^[0-9]+$ ]] || { warn "batteria minima non valida, uso 40"; MIN_PCT=40; }
[[ "$MAX_TEMP" =~ ^[0-9]+$ ]] || { warn "temperatura non valida, uso 41"; MAX_TEMP=41; }

MODEL=""
if [ "$SERVE_MODELS" = true ]; then
    echo ""
    echo "  Modello da servire. Su 12 GB di RAM un 3-4B quantizzato è il punto"
    echo "  giusto per lavorare tutta la notte; un 7-8B gira ma scalda di più."
    ask MODEL "Modello Ollama" "qwen3:4b"
fi

# ── 6. Configurazione ───────────────────────────────────
hdr "6/7 — Configurazione"
mkdir -p "$HOME_DIR/data" "$HOME_DIR/logs" "$HOME_DIR/run"
[ -f "$ENV_FILE" ] && cp "$ENV_FILE" "$ENV_FILE.bak" && log "configurazione precedente salvata in node.env.bak"
umask 077
cat > "$ENV_FILE" <<EOF
# Generato da join-mesh-android.sh — $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# Modifica con: 00mesh config   (poi 00mesh restart)
NODE_TIER=mobile
NODE_SPECIALIZATION=mobile-night-worker
NODE_AVATAR=📱
NODE_HOSTNAME=${TS_IP:-localhost}
NODE_PORT=8084
NODE_BIND=${DEFAULT_BIND}
PUBLIC_ENDPOINT=${PUBLIC_EP}
BOOT_PEERS=${PEERS}
CONTROL_PLANE_URL=${CP_URL}
REGISTRY_URL=${REG_URL}
SIGN_REQUESTS=true
HEARTBEAT_EVERY=30
DATA_DIR=${HOME_DIR}/data

INFERENCE_BACKEND=ollama
NODE_SERVE_MODELS=${SERVE_MODELS}
OLLAMA_URL=http://127.0.0.1:11434
OLLAMA_PROXY_URL=http://127.0.0.1:11435
OLLAMA_MODEL=${MODEL}
# Memoria condivisa CPU/GPU: quanta RAM può tenere il modello.
VRAM_GB=6
# Libera la RAM dopo 2 minuti senza richieste: di giorno il telefono è tuo.
OLLAMA_KEEP_ALIVE=2m
OLLAMA_NUM_PARALLEL=1
OLLAMA_MAX_LOADED_MODELS=1
DREAM_ENABLED=false

# Ruolo: failover = il telefono non fa da worker; il suo modello serve solo ad Anna/CP
# in emergenza (Pocket Hub). Per tornare worker: 00mesh role worker.
MOBILE_ROLE=failover
POCKET_HUB_ENABLED=true

MOBILE_REQUIRE_CHARGER=true
MOBILE_WORK_WINDOW=${WINDOW}
MOBILE_MIN_BATTERY_PCT=${MIN_PCT}
MOBILE_MAX_TEMP_C=${MAX_TEMP}
MOBILE_RESUME_TEMP_C=$((MAX_TEMP > 3 ? MAX_TEMP - 3 : MAX_TEMP))
EOF
umask 022
log "configurazione in $ENV_FILE ✓"

cp "$APP_DIR/scripts/android/00mesh" "$PREFIX/bin/00mesh" && chmod 755 "$PREFIX/bin/00mesh"
log "comando 00mesh installato ✓"

if mkdir -p "$HOME/.termux/boot"; then
    cat > "$HOME/.termux/boot/00mesh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/sh
# Avvio del nodo 00mesh all'accensione (richiede l'app Termux:Boot, aperta una volta).
termux-wake-lock
00mesh start >> "$HOME/.00mesh/logs/boot.log" 2>&1
EOF
    chmod 755 "$HOME/.termux/boot/00mesh"
    log "avvio automatico pronto (serve l'app Termux:Boot, aperta almeno una volta)"
fi

# ── 7. Avvio ────────────────────────────────────────────
hdr "7/7 — Avvio"
00mesh start
if [ -n "$MODEL" ]; then
    echo ""
    log "scarico ${MODEL} (qualche GB: meglio su Wi-Fi)..."
    00mesh pull "$MODEL" || warn "download non riuscito: riprova con 00mesh pull ${MODEL}"
fi

echo ""
echo -e "  ${B}Nodo mobile pronto ✓${N}"
echo ""
echo "  00mesh status        stato, batteria, gate"
echo "  00mesh bench         token/s e temperatura del modello"
echo "  00mesh logs          log del nodo"
echo "  00mesh stop|start    ferma / riavvia"
echo ""
echo "  Consiglio: nelle impostazioni Android metti Termux su 'Batteria: senza"
echo "  restrizioni', altrimenti il sistema può chiudere il nodo di notte."
echo ""
