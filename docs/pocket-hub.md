# Pocket Hub — il telefono come control-plane di riserva

Il nodo mobile (S24 con Termux) può fare da CP di riserva quando il Mac non
risponde, e tiene un registro di ciò che succede nel frattempo per riconsegnarlo
a Hermes quando il Mac torna. Codice: `shared/pocket_hub_guard.py` (stati),
`shared/pocket_hub_outbox.py` (registro), `node/pocket_hub.py` (servizio).

## Come funziona

1. `STANDBY`: il hub controlla `GET <primario>/health` ogni 30 s (`POCKET_HUB_CHECK_S`). In standby gli
   endpoint di hub rispondono 503; `/health` e `/pocket/status` rispondono sempre.
2. Dopo 3 mancate risposte (~90 s) → `ACTIVE_FAILOVER`. Serve `GET /nodes/active`,
   `POST /mesh/announce` e `POST /v1/chat/completions` (inoltrata all'Ollama del
   telefono, con un prompt di emergenza se non c'è un system prompt). Già dal
   primo mancato controllo risponde alla chat, per non lasciare Anna muta fino alla promozione.
3. Registra in `~/.00mesh/pocket_hub/outbox.ndjson`: transizioni di stato, un
   annuncio per nodo ed episodio, e ogni chat (testo incluso).
4. Con il primario di nuovo vivo (`RECOVERING`/`STANDBY`) riconsegna in ordine a
   `POST <primario>/memory/push`, da dove entra in Hermes. Una voce è spedita solo
   se il CP risponde 2xx; la coda riparte dopo un riavvio; ogni voce porta
   `interaction_id` stabile per deduplicare. Oltre 5000 voci in attesa scarta le
   più vecchie e lo scrive in un marker `outbox_overflow`.

## Attivarlo (telefono)

In `00mesh config` (`~/.00mesh/node.env`):

```dotenv
POCKET_HUB_ENABLED=true
# POCKET_HUB_PRIMARY_CP=http://100.81.234.102:8085   # default: CONTROL_PLANE_URL
# POCKET_HUB_PORT=8086  POCKET_HUB_MODEL=  POCKET_HUB_CHECK_S=30  POCKET_HUB_MISSES=3
```

Poi `00mesh restart`. `00mesh hub` mostra stato, primario e voci da riconsegnare;
`curl localhost:8086/pocket/flush -XPOST` forza la riconsegna.
`anna` passa da solo al hub se il Mac non risponde.

## Limiti dichiarati

- Il modello è quello piccolo del telefono: Anna in failover ha un prompt di
  emergenza, non la persona completa né la memoria Hermes.
- **I peer devono sapere che il telefono è il fallback** (URL del hub nella loro
  configurazione): il hub non si fa trovare da solo. Non ancora configurato.
- Le conversazioni restano in chiaro sul telefono fino alla riconsegna.
- Il traffico non ha token: la tailnet è il confine di fiducia.
- Gli endpoint del hub sono il minimo, non una copia del CP.

## Timer

Rilassati di proposito (30 s di controllo, 3 mancati, riconsegna ogni 60 s):
oggi non ci sono utenti da servire. Da rivedere in base a nodi e richieste
prima del demo aziendale: più nodi e carico → controllo più frequente e soglia
più bassa; il valore giusto va misurato, non indovinato.
