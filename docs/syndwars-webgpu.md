# Syndicate Wars su WebGPU e nello sviluppo automatico di HyperSpace

Piano del 2026-11-08. Parte dalla decompilazione chiusa: in `syndwars-remake` la logica di gioco, il Breakout e l'audio sono in C; restano in assembly solo la rete (esclusa per scelta) e qualche ponte. Questo documento dettaglia le fasi 6.2 e 6.4 di `ROADMAP.md` e aggiunge il collegamento con i cicli automatici di HyperSpace.

## Principi

- **Il binario x86 a 32 bit resta il riferimento.** Ogni passo si misura contro di lui con le prove che esistono già: stato di gioco (things, sthings, mappa) ai turni delle partite registrate, chiamate dirette, banco del Breakout.
- **Prima identico, poi migliore.** Ogni fase ha un criterio d'uscita che si verifica da una macchina, non a occhio. Le migliorie (risoluzione, effetti) arrivano dopo, dietro un'opzione.
- **Dati originali solo in locale.** Le prove usano la copia del gioco sull'OMEN e sul Mac; immagini e video del gioco non escono da lì. Una build pubblica carica i dati dell'utente ("porta i tuoi dati") finché il problema di IP non è risolto da un legale.
- **Niente applicazione automatica.** Come per il sogno notturno: gli agenti propongono su rami, le prove decidono se la proposta è valida, l'utente fonde.

## Fase A — Il gioco in WebAssembly con la grafica di oggi

Obiettivo: lo stesso gioco, con il rasterizzatore software attuale, gira nel browser.

- **Bersaglio `wasm32` con Emscripten.** È un ambiente a 32 bit come l'originale: le strutture del gioco tengono la stessa disposizione in memoria, quindi le correzioni a 64 bit del porting macOS non servono qui (male non fanno).
- **SDL2 e OpenAL esistono già in Emscripten**, e il gioco usa SDL2 per finestra e input e OpenAL per l'audio.
- **Ciclo principale.** Il gioco ha un ciclo che non restituisce mai il controllo; il browser lo richiede a ogni fotogramma. Prima versione con `ASYNCIFY` (cambia poco codice, costa prestazioni); poi, se serve, il ciclo spezzato in un passo per fotogramma con `emscripten_set_main_loop`.
- **File di gioco.** File system virtuale di Emscripten: in prova la cartella dati si monta da disco (Node) o si carica in IndexedDB/OPFS dal browser, scelta dall'utente.
- **Rete e joystick DOS.** Esclusi dalla build: uno strato di rete vuoto (partita singola) e niente `sjoyst.c` DOS.
- **Modalità senza schermo** (`-q -H` o un'opzione nuova) per far girare le partite registrate in Node senza browser.

**Criterio d'uscita:** le 6 partite registrate e la partita lunga 0,1 girate in WebAssembly (Node) danno lo stesso stato di gioco del binario x86 a ogni turno controllato. Il gioco usa aritmetica intera: se c'è una differenza è un difetto (variabile non inizializzata, comportamento indefinito), non arrotondamento.

## Fase B — Lo schermo nel browser, identico

Obiettivo: quello che si vede nel browser è lo stesso schermo del gioco nativo.

- Il gioco disegna in un buffer a 8 bit con palette. Nel browser: buffer → texture R8, palette → texture 256×1, conversione nello shader, una sola presentazione per fotogramma (WebGPU se c'è, altrimenti WebGL2 o il canvas di SDL).
- **Criterio d'uscita:** schermate identiche, pixel per pixel, a quelle del nativo agli stessi turni delle partite registrate (stessa risoluzione, stessa palette).

## Fase C — Rasterizzatore WebGPU

Obiettivo: il mondo e gli sprite disegnati dalla GPU, prima uguali al software, poi a risoluzione piena.

- **Dove tagliare.** Il motore costruisce liste di disegno ordinate da dietro in avanti e chiama, per ogni elemento, il disegno di un poligono (`trigpoly`, modi 2…27), di uno sprite o di una linea. Si introduce un'interfaccia di disegno con due implementazioni: software (riferimento, quella di oggi) e GPU.
- **Poligoni.** Vertici in coordinate di schermo con UV e modo. Pagine di texture come texture a indici R8 (array di pagine 256×256, o 512×512 con le versioni ingrandite già pronte). Tabelle di sfumatura e trasparenza (`pixmap.fade_table` e simili) come texture. Il fragment shader applica la formula del modo: sono formule semplici e già mappate per il rasterizzatore ad alta risoluzione (`poly_hires_supports`, `draw_poly_hires`).
- **Sprite.** Atlante R8 dei banchi, rettangoli per sprite, indice trasparente scartato, scala come oggi. Versioni a doppia risoluzione già pronte come opzione.
- **Ordine.** Si tiene l'ordine delle liste (pittore), senza depth buffer: stesso risultato del software. Un depth buffer vero è una miglioria successiva.
- **Risoluzione.** I vertici sono già numeri: la GPU disegna direttamente a 1920×1080 o oltre, con precisione sotto il pixel.
- **Criteri d'uscita.** (1) A 640×480 con le texture originali, confronto con il rasterizzatore software agli stessi turni: differenze ammesse solo sui bordi dei poligoni (regole di copertura diverse), sotto una soglia fissata all'inizio e misurata. (2) Fotogrammi al secondo misurati su Mac e OMEN.
- **Rischio principale:** luci e ombre passano dalle tabelle della palette. Si tengono a indici fino in fondo; il colore vero si calcola solo all'ultimo passaggio.

## Fase D — Collegamento allo sviluppo automatico di HyperSpace

Obiettivo: le prove girano da sole ogni notte sull'OMEN, gli agenti lavorano su compiti piccoli con una prova d'accettazione chiara, e l'utente vede un rapporto.

- **Un cancello unico: `scripts/syndwars_gate.py`.** Restituisce un JSON con: compilazione (x86 di riferimento, x86 attuale, wasm), determinismo (attuale contro riferimento, wasm contro attuale), schermate (fase B), differenza GPU contro software (fase C), prestazioni. Lo usano gli agenti prima di proporre e i cicli notturni. Riusa `par_check.sh`, `breakout_check.sh` e il confronto delle chiamate dirette.
- **Lavoro notturno.** Un compito `syndwars` in `nightly_omen_orchestrator.py` (e nel ciclo 24/7, con la stessa guardia termica): aggiorna i rami, lancia il cancello su `master` e sui rami aperti, scrive il rapporto in `data/nightly/syndwars/` (solo numeri, niente immagini del gioco fuori dall'OMEN) e una riga nel diario del codebase. Se `master` peggiora, una nota in `AGENT-LOG.md`.
- **Coda di compiti per i modelli locali.** Claude Code e Antigravity scompongono le fasi in compiti con prova d'accettazione ("shader del modo 12 entro la soglia", "disegno sprite scalati via GPU", "partita 0,8 identica in wasm"). I modelli locali sull'OMEN propongono; il cancello decide; un agente rivede; l'utente fonde. Nessuna fusione automatica.
- **Partite con comandi del giocatore.** Una registrazione con input vero (armi, veicoli, Persuadertron) va aggiunta alle prove: oggi molte funzioni non girano mai nelle partite registrate.

## Ordine e primi passi

1. Rimettere in piedi la prova completa sull'OMEN sul `master` attuale e fissare i riferimenti (oggi l'accesso SSH è da sbloccare).
2. `syndwars_gate.py` con quello che esiste già (x86), così ogni passo successivo ha il suo controllo.
3. Fase A: build wasm in Node senza schermo e confronto dello stato sulle partite registrate.
4. Fase B, poi C un modo di disegno alla volta, poi gli sprite.
5. Il compito notturno appena il cancello copre la fase A.

Multiplayer (6.3) e asset nuovi (piano di lancio) vengono dopo e usano lo stesso cancello: il determinismo misurato nella fase A è la base anche del multiplayer a passi fissi.

## Domande aperte

- Hosting della versione web per alpha e beta: privato (Tailscale) o pubblico con "porta i tuoi dati"; decisione legata all'IP.
- Soglia di differenza accettata tra GPU e software nella fase C.
- Quale macchina fa da riferimento per le prestazioni WebGPU.
