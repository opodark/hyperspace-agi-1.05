# Prototipo testuale Anna su Hermes Gadget

Questo prototipo usa il simulatore e il protocollo originali di
[Hermes Gadget SDK](https://github.com/Adolanium/hermes-gadget-sdk). Il server
locale in `scripts/hermes_gadget_text.py` sostituisce la risposta dimostrativa
con `POST /v1/chat/completions` del control plane HyperSpace. Non installa il
plugin nel gateway Hermes e non aggiunge un secondo archivio di memoria.

## Avvio su macOS

Richiede Python 3.10+, Tkinter, un compilatore C++17 e il control plane già
raggiungibile su `http://127.0.0.1:8085`. Da una directory di lavoro separata:

```bash
git clone https://github.com/Adolanium/hermes-gadget-sdk.git
cd hermes-gadget-sdk
python3 -m venv .venv
.venv/bin/python -m pip install -e . cmake
PATH="$PWD/.venv/bin:$PATH" .venv/bin/hermes-gadget build-sim --test
```

In un primo terminale, dalla directory del repository HyperSpace:

```bash
/percorso/hermes-gadget-sdk/.venv/bin/python scripts/hermes_gadget_text.py
```

In un secondo terminale, dalla directory dell'SDK:

```bash
.venv/bin/hermes-gadget sim --url ws://127.0.0.1:8765/gadget --board sim-466x466-round
```

Il simulatore mostra un codice di pairing. Digita `approve CODICE` nel primo
terminale, poi scrivi un messaggio nel campo testo del simulatore. Per scegliere
un modello usa `--model NOME`; senza, il control plane usa il proprio default.
Per cambiare indirizzo usa `--control-plane URL`. `quit` arresta il server.

## Cosa verifica

- Gli stati visibili del gadget passano da pronto a elaborazione e di nuovo a
  pronto; la risposta di Anna arriva sul display e nel pannello conversazione.
- Il gateway del gadget fa pairing prima di accettare messaggi.
- La cronologia testuale resta in RAM, separata per dispositivo e limitata a 20
  messaggi. Una nuova sessione la cancella.
- La richiesta al control plane usa `X-Hyperspace-Tools: off`: questa prova
  testa solo la conversazione, senza invocare tool o connettori.

Questa versione accetta solo testo. Il tasto TALK risponde con un avviso; non
trascrive audio e non genera voce. Le richieste già partite al control plane
possono terminare in background dopo CANCEL, ma la loro risposta non viene
mostrata né aggiunta alla cronologia. Il server WebSocket ascolta solo su
`127.0.0.1`. Se il control plane è remoto, usa un tunnel privato: l'endpoint
`/v1/chat/completions` non richiede un token proprio.

Verificato il 5 ottobre 2026 con SDK 0.2.0, commit `323e330`: build del
simulatore, test C++, round trip contro un control plane HTTP finto e prova
end-to-end con il control plane locale e il modello
`maternion/minicpm5-heretic:2b`. Il simulatore ha completato pairing, inviato
un messaggio e mostrato la risposta del modello (`Ciao Anna.`).
