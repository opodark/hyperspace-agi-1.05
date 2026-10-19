# Automazione social — Anna e Aurora, un profilo condiviso

> Stato: **Fase 0 + 1 completate** (freeze, policy, coda, tetti, test). Fase 2
> (publisher + rotte + innesto nei loop) e Fase 3 (X) da fare. Pubblicazione
> **congelata** finché la Fase 2 non è pronta.

## Scopo

Un solo profilo per piattaforma (Instagram + X), condiviso da Anna e Aurora:
`author` è un metadato, non un account. L'agente (il control-plane) scrive e
compone i contenuti; un publisher con le sole credenziali social li esegue,
governato da una policy e da tetti giornalieri. La pubblicazione è
**automatica**: nessuna approvazione per post, ma una finestra di annullamento
(hold) e un dry-run per i canali nuovi.

## Invarianti di sicurezza

1. **Token mai all'agente e mai nel `.env`.** L'agente non vede i tool di
   scrittura social; il publisher usa credenziali proprie in
   `~/.config/hyperspace/social/` (vedi sotto).
2. **Un solo publisher.** I nodi del mesh non tengono token e non pubblicano.
3. **Nessuna automazione browser**: solo API ufficiali (Graph API Instagram,
   API v2 X). L'automazione di un profilo personale via browser viola i ToS.
4. **Disclosure IA**: bio e didascalia (marcatore `#AI…`); su X etichetta
   *Automated account*, operatore in bio e `made_with_ai: true`.
5. **Pubblico ≠ privato**: arte/poesia/sogni nel feed; il contenuto intimo
   resta nel ramo DM (`shared/intimate_diary.py`).
6. **Esito incerto → `needs_review`, mai retry cieco** (regola di
   `shared/instagram_outbox.py`).
7. **Kill switch**: `SOCIAL_PUBLISH_ENABLED=false` + revoca token su Meta/X.

## Stati dell'item

`scheduled → publishing → published | needs_review | dry_run`;
`cancelled` e `rejected` sono terminali decisi dall'operatore.

## Configurazione

| Variabile | Default | Significato |
|---|---|---|
| `SOCIAL_PUBLISH_ENABLED` | true | interruttore generale |
| `SOCIAL_IG_ENABLED` | true | canale Instagram (alias storico: `INSTAGRAM_DREAM_PUBLISH_ENABLED`) |
| `SOCIAL_X_ENABLED` | false | canale X, acceso solo dopo il dry-run |
| `SOCIAL_DRY_RUN` | true | registra senza chiamare le API |
| `SOCIAL_HOLD_MINUTES` | 15 | finestra di annullamento |
| `SOCIAL_MAX_PER_DAY` | 3 | tetto per canale |
| `SOCIAL_MIN_GAP_MINUTES` | 180 | distanza minima fra due invii |
| `DREAM_PER_DAY` | 1 | tetto totale sogni/giorno |

Tetti per tipo: sogno 1, poesia 1, dialogo 1, post 0 (solo bozze).
Finestre (Europa/Roma): sogno 07–10, poesia 12–15, dialogo 18–21; X +30 minuti.

## File

- `shared/social_policy.py` — guardie e finestre (puro, senza rete).
- `shared/social_queue.py` — coda SQLite (tabella `social_queue` nel DB del CP).
- `shared/social_text.py` — didascalie e adattamento X (deterministico).
- `shared/dream_schedule.py` — `choose_author` con tetto totale.
- `control-plane/main.py` — `_decisione_sogno` e `_sogni_config` con `DREAM_PER_DAY`.

## Credenziali (da completare in Fase 2)

I token vivranno in `~/.config/hyperspace/social/{instagram,x}.json` (`chmod
600`), montati `:ro` solo nel container del publisher. **Non** nel `.env`, che
oggi arriva a molti container. Il token Instagram attuale resta dov'è finché il
publisher non ha il proprio percorso di lettura.

## Stato attuale

- Freeze in `.env`: `POST_LOOP_ENABLED=false`,
  `INSTAGRAM_DREAM_PUBLISH_ENABLED=false`,
  `CONNECTOR_WRITE_TOOLS` senza `instagram_publish_image`, `DREAM_PER_DAY=1`.
  **Perché il freeze valga, il container va ricreato**
  (`docker compose up -d --no-deps control-plane`).
- `CONNECTOR_READ_ONLY` resta `false` perché le risposte ai DM (funzione viva)
  passano dal connector manager; il feed publisher non passerà più da lì.
