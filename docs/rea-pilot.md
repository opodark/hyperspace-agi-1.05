# REA: prova statica sul web-node

Prova del 5 ottobre 2026, REA `rea-agents` 3.2.1 su macOS. REA è stato
installato solo in `/private/tmp/rea-pilot` con `--ignore-scripts`; non è stato
eseguito `rea setup`, non sono state registrate skill o connessioni MCP e non
sono stati installati Hopper o Ghidra.

## Target e comando

Una copia temporanea di `web-node/src`, `package.json`, `index.html`,
`join.html` e `serve.mjs` è stata analizzata con:

```bash
rea analyze-javascript-application /private/tmp/rea-pilot/fixture --format json
```

Hash SHA-256 dell'artefatto directory riportato da REA:
`3e66b691f99b11673ceda8fc161f82424b097cdce8ab429ccb30efac02e99ac5`.
Evidence ID: `ev_7d3b4314b0dfd3959b85a79ec11f08c75322aa830c7b83c18ce2613759a6882b`.
Il JSON completo è rimasto nella directory temporanea (17,6 MB; SHA-256
`0c07a57fe7963379aab1e7a36afdea1c7b435062e9db5d0db185e161b05b2efc`).

## Risultato

- 9 file JavaScript analizzati, 0 errori di parsing; 91 nodi e 122 archi nel
  grafo dell'app. I `findings` della statistica REA sono elementi strutturali,
  **non vulnerabilità confermate**.
- REA ha riconosciuto `src/task-runner.js` come modulo ESM ed elencato gli
  export `TaskUnsupported`, `runTask`, `supportedTaskTypes`, verificabili nel
  sorgente. Questa è evidenza utile per un inventario di capacità.
- Ha segnalato `/auto`, `/pinned` e `/external` in `src/models.js` come endpoint.
  Sono invece valori di UI (`route`) in `selectableModelOptions`, non route HTTP.
- Ha classificato `src/index.js` come `electron-main` e `join.html` come
  `electron-renderer`. Il web-node è una web app: queste etichette non descrivono
  il runtime reale. Il report avverte che le relazioni statiche non provano
  l'esecuzione a runtime.
- `rea doctor` ha confermato Node e il parser JavaScript disponibili, ma ha
  indicato Hopper e Ghidra assenti. L'analisi nativa non è stata provata.

## Decisione

REA è utile come **inventario con provenienza** per artefatti JavaScript e,
in futuro, come analista di binari propri con un provider installato. Su questa
fixture web il report va interpretato: etichette Electron ed endpoint producono
falsi positivi se diventano finding security senza verifica. Prima di esporre
REA nella UI o via MCP, serve un adapter che selezioni le operazioni statiche,
riduca il report e distingua osservazioni, inferenze e vulnerabilità verificate.
La prossima fixture migliore è un piccolo bundle Electron o binario di nostra
proprietà, con funzioni e confini noti.

Fonte: [REA README](https://github.com/morluto/rea) e
[guida all'analisi JavaScript](https://github.com/morluto/rea/blob/main/docs/javascript-artifact-reconstruction.md).
