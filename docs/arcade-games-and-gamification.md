# HyperSpace Neural Arcade — Sala Giochi Retro & Gamification Commerciale

Documentazione dell'architettura, dei motori di gioco Canvas 2D, del sintetizzatore audio Web Audio API e dell'integrazione con il cluster distribuito e il Commercial Engine.

---

## 1. Panoramica

La **Sala Giochi Arcade Neurale** è ospitata in [`web-node/apps/playground/arcade.html`](../web-node/apps/playground/arcade.html) ed è accessibile da Cockpit all'indirizzo:
- **URL**: `http://localhost:8090/arcade` (e `http://localhost:8090/arcade.html`)

La pagina realizza il 4° pilastro commerciale di HyperSpace (`neural_arcade_gamification` definito in [`shared/commercial_engine.py`](../shared/commercial_engine.py)): i visitatori e gli sviluppatori possono giocare a minigiochi arcade vintage sul canvas a tubo catodico CRT, e il punteggio ottenuto viene automaticamente convertito in **token di inferenza gratuiti** (1 token ogni 40 punti) per testare i modelli MoE del cluster sovrano.

---

## 2. Architettura dei 3 Motori di Gioco

Tutti i giochi sono eseguiti interamente nel browser tramite un unico canvas retro a 60 FPS (760x420) con effetto scanline CRT:

### 👾 1. Neural Invaders
- **Tema**: Difesa del cluster dai colli di bottiglia e dai costi dell'infrastruttura centralizzata.
- **Nemici**: *Latency Spike*, *Cloud Invoice*, *Memory Leak*, *Server Timeout*, *Overheating*.
- **Progressione a Ondate**:
  - Wave 1: nemici base a velocità standard.
  - Wave 2: nemici accelerati con proiettili a frequenza maggiorata.
  - Wave 3: **Monolithic Cloud Boss** (barra vita con 35 HP, scudi, laser radiali bilaterali e vittoria con +1000 punti).
- **Controlli**: Frecce `←` / `→` o tasti `A` / `D` per muoversi; `Spazio` per sparare impulsi token.

### 🏓 2. Pong vs AGI
- **Tema**: Rally testa a testa contro la racchetta avversaria simulata dal modello neurale (Flint 40B).
- **Fisica & IA**:
  - Calcolo predittivo dell'intercetta della pallina con lag euristico per consentire sfide bilanciate.
  - Angolo di rimbalzo proporzionale al punto di impatto sulla racchetta ($\pm 45^\circ$).
  - Incremento dinamico della velocità ad ogni scambio e scia di particelle motion trail.
- **Match**: Primo a 5 punti vince il set.
- **Controlli**: Frecce `↑` / `↓` o tasti `W` / `S`.

### ⚡ 3. Vector Matrix Runner
- **Tema**: Cyber-runner a prospettiva vettoriale pseudo-3D neon nello spazio delle rappresentazioni latenti.
- **Meccanica**:
  - 5 corsie prospettiche proiettate verso il punto di fuga centrale con griglia a scorrimento continuo.
  - Schivata ostacoli: *Latency Wall* (rosso), *Firewall Gate* (arancione), *Deadlock* (viola).
  - Raccolta *Sovereign Tokens* (verde) per bonus punteggio immediato.
  - Velocità progressiva con indicatore tachimetrico in tempo reale.
- **Controlli**: Frecce `←` / `→` o tasti `A` / `D` per cambiare corsia; `Spazio` per il boost temporaneo.

---

## 3. Sintetizzatore Chiptune (Web Audio API)

Il modulo `ArcadeAudio` genera suoni a 8-bit procedurali in tempo reale senza dipendere da asset audio esterni:
- `laser()`: oscillatore sawtooth a rampa esponenziale discendente (850 Hz $\to$ 220 Hz).
- `explosion()`: sintesi a bassa frequenza e decadimento esponenziale.
- `ping(isHigh)`: onda sinusoidale pulita per i rimbalzi di Pong (680 Hz / 440 Hz).
- `powerup()`: arpeggio ascendente chiptune a 4 note su onda quadra.
- `scorePoint()`: accordo a due toni.
- `gameOver()`: sequenza armonica discendente minore.
- `victory()`: fanfara trionfale a 5 note su onda triangolare.
- Pulsante di silenziamento rapido in testata con feedback sonoro.

---

## 4. Leaderboard & Tokenomics Commerciale

La classifica ("Hall of Fame") è integrata con il backend di Cockpit:
- **`GET /api/commercial/arcade/scores`**: restituisce i top 50 record salvati su `data/commercial/arcade_scores.json`.
- **`POST /api/commercial/arcade/score`**: convalida e registra un nuovo record, calcolando i token premio:
  $$\text{tokens\_won} = \max\left(5, \left\lfloor\frac{\text{score}}{40}\right\rfloor\right)$$
- Incrementa il contatore globale di gettoni inseriti `arcade_coins_inserted` nelle metriche del Commercial Engine.

---

## 5. Diagnostica e Collaudo

Lo script riutilizzabile in [`scripts/diagnostics/orchestrate_arcade_gameplay.py`](../scripts/diagnostics/orchestrate_arcade_gameplay.py) verifica automaticamente l'intero stack:

```bash
# Diagnostica rapida
.venv/bin/python scripts/diagnostics/orchestrate_arcade_gameplay.py

# Dettaglio completo e simulazione partita
.venv/bin/python scripts/diagnostics/orchestrate_arcade_gameplay.py --verbose --simulate-round

# Suite Pytest
.venv/bin/python -m pytest tests/test_arcade_games_and_cockpit.py -v
```
