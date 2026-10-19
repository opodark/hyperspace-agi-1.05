# Protocollo Git Mesh — un repo, più nodi, più agenti

Questo documento estende [AGENTS.md](../AGENTS.md) per il caso multi-nodo: lo stesso
repository è clonato su Mac, win11 (HP Omen) e ASUS V16, e più agenti ci lavorano in
parallelo. Le regole di base (AGENT-LOG, nessun commit/push senza conferma, nessun
segreto, test nel `.venv` del repo) restano valide; qui si aggiunge **chi è la verità**
e **come si allineano le foglie**.

## Topologia

| Nodo | Ruolo | Agenti | Regola |
|---|---|---|---|
| Mac (`hyperspace-agi-1.04`) | **verità** (unico scrittore di `origin`) | Cline, Codex, Claude Code | fa `commit` + `push` |
| win11 `hpomen` | foglia | Antigravity, Cline(win11) | solo `pull`, mai push di verità |
| ASUS `laptop-t9h8plht` | foglia | (a rotazione) | solo `pull`, mai push di verità |

La **verità è il repository sul Mac**: una foglia non decide mai da sola come
risolvere un conflitto di contenuto — si allinea al Mac e basta. Se una foglia ha
scoperto un bug, apre il discorso nell'AGENT-LOG e il fix nasce sul Mac.

## Regole

1. **Una verità sola.** Il Mac è l'origine. Le foglie `pull` e, se serve, `reset`.
   Una foglia **non** fa `git merge` creativi né `push` di contenuto: non ha nulla di
   suo che non sia già sul Mac.

2. **Pull prima, log dopo.** Ogni intervento inizia con `git pull` e la lettura di
   `AGENT-LOG.md`; finisce con un blocco in coda ad `AGENT-LOG.md` (data, agente,
   destinatario, cosa fatto / cosa chiede).

3. **Un commit per dominio.** Ogni agente committa **solo** i file del proprio
   dominio, con un titolo onesto. È vietato il commit "misto": un `feat(chat)` che
   dentro contiene anche ComfyUI, test e script di un altro agente rende impossibile
   il bisect e il `blame`. Esempio corretto: `fix(comfyui): gateway webui su launchd`
   con dentro solo `integrations/comfyui/` e `scripts/start-all-macos.sh`.

4. **Push solo con conferma.** Nessun `push` senza un sì esplicito dell'utente.
   Per la sincronizzazione di routine si può concordare una finestra ("mesh sync"),
   ma resta un'azione esplicita, mai automatica.

5. **Recupero di una foglia bloccata.** Una foglia rimasta indietro, con merge a
   metà o che "non pulla", non si aggiusta con merge creativi: si riallinea e via:
   ```bash
   git fetch origin
   git reset --hard origin/main   # ⚠️ butta le modifiche locali: su una foglia è ok
   git pull
   ```
   Se il `reset --hard` non basta (file in conflitto persistente), clonare da zero
   è più economico che sbloccare un merge arretrato.

6. **Niente percorsi hardcoded.** Negli script di avvio non si scrive mai
   `hyperspace-agi-1.0x`: si usa `HYPERSPACE_REPO` con fallback alla posizione
   dello script:
   ```bash
   REPO="${HYPERSPACE_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
   ```
   (il 2026-10-18 `start-bridge.sh` puntava ancora a `1.05`, inesistente, e girava
   solo per un `HYPERSPACE_REPO` rimasto nel dominio launchd: è il sintomo che questa
   regola esiste per togliere).

7. **Domini separati per agente.** Un agente tocca il suo dominio e lo dichiara
   nell'AGENT-LOG prima di iniziare. ComfyUI/bridge è di Cline+Codex, chat/web-node
   di chi li sta sviluppando, i nodi Windows di Antigravity. Se due agenti devono
   toccare lo stesso file, si alternano via AGENT-LOG, non in parallelo.

8. **Segreti mai, test verdi.** Valgono le regole di AGENTS.md: nessun token nei file
   o negli output; la suite del repository (`.venv/bin/python -m pytest tests/ -q`)
   deve restare verde; le diagnostiche riusabili finiscono in `scripts/diagnostics/`
   e in `docs/`.

## Checklist per l'agente

- [ ] `git pull` e lettura di `AGENT-LOG.md` (e `docs/git-mesh-protocol.md` se è la
      prima volta).
- [ ] Ho dichiarato il dominio nell'AGENT-LOG.
- [ ] Ho lavorato solo sui miei file.
- [ ] Ho committato **solo il mio dominio**, con titolo onesto.
- [ ] Non ho fatto `push` (aspetto conferma).
- [ ] Ho aggiunto il blocco di chiusura in `AGENT-LOG.md`.

## Messa in sicurezza di un riavvio

I LaunchAgent del Mac (`com.hyperspace.comfy-bridge`, `com.hyperspace.webui-gateway`,
`com.hyperspace.reel-daily`, `com.hyperspace.tiktok-editor`) sono caricati con
`launchctl bootstrap "gui/$(id -u)" <plist>` e sopravvivono al riavvio tramite
`RunAtLoad`+`KeepAlive`. I loro script di avvio usano la regola 6, quindi non
dipendono più dal percorso assoluto del clone.

## 9. Sincronizzazione P2P Cifrata, RBAC e Role Test-Gate (Mesh a Caldo)

Per propagare modifiche tra nodi attivi senza passare da GitHub, il sistema usa il canale crittografico E2EE P2P:

1. **Matrice RBAC per Ruolo (`shared/mesh_sync.py`):**
   - **`authority` (Mac Hub):** Accesso di scrittura a tutto il repository.
   - **`worker-gpu` (HP Omen Win11):** Limitato a `integrations/comfyui/**`, `worker/**`, `node/**`, `shared/image_jobs.py`, `scripts/reel_*.py`, test grafici.
   - **`worker-leaf` (ASUS V16):** Limitato a `worker/**`, `node/**`, `shared/power_sense.py`.
   - **File Inviolabili:** `shared/identity.py`, `shared/crypto_channel.py`, `control-plane/**`, `AGENTS.md` possono essere modificati unicamente da patch firmate dall'Authority.

2. **Ingress e Queue (`node/main.py`):**
   - `/mesh/sync/patch` decifra l'envelope ECDH + AES-256-GCM, verifica la firma ECDSA e convalida l'elenco dei file contro lo scope consentito per `origin_role`.
   - Se autorizzato, deposita il bundle in `data/node-1/mesh-patches/<id>.json`.

3. **Host Watcher con Role Test-Gate (`scripts/mesh_patch_watcher.py`):**
   - Il processo host applica le patch atomicamente (`apply_mesh_update`).
   - Se `--run-tests` è attivo (predefinito in `mesh_node_deploy.sh` e `.ps1`), esegue la suite di test specifica per il ruolo del nodo locale.
   - Se i test falliscono, scatta il **rollback automatico** dei file applicati e viene registrato `status: failed` nel log di ritorno.

4. **Coerenza di Ruolo in Doctor Mesh (`control-plane/cp/doctor_mesh.py`):**
   - Non segnala allarmi di disallineamento se nodi eterogenei hanno commit differenti ma risultano coerenti e aggiornati rispetto al proprio perimetro di ruolo (`role_aligned: true`).

