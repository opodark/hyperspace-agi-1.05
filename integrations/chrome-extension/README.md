# 00MESH Local Bridge — Chrome Extension (AI Node Connector)

L'estensione Chrome **00MESH Local Bridge** consente a qualsiasi utente di collegare la propria scheda grafica o acceleratore AI (tramite **Ollama** o **LM Studio** in esecuzione locale) direttamente alla rete decentralizzata **HyperSpace 00MESH**, condividendo potenza di calcolo ed accumulando token tramite *Proof-of-Useful-Work*.

---

## 🌟 Perché un'Estensione Chrome?

1. **Zero Configurazione / Zero Installazioni Complesse**: Nessun container Docker, nessun ambiente Python o riga di comando richiesta per il nodo esterno.
2. **Bypass dei Blocchi di Rete (CORS & PNA)**: Le pagine web convenzionali non possono chiamare `http://localhost:11434` o `http://127.0.0.1:1234` a causa delle policy di sicurezza del browser (*Private Network Access*). L'estensione ha permessi espliciti per comunicare con il localhost ed il server remoto contemporaneamente.
3. **Massima Velocità Hardware**: L'inferenza non passa da WebGPU ma sfrutta **NVIDIA CUDA, AMD ROCm o Apple Metal** al 100% della velocità nativa dei modelli installati su Ollama o LM Studio.
4. **Tokenomics Integrata**: Collegando il proprio indirizzo wallet Solana (Phantom o Solflare), l'utente riceve l'accredito dei token per ogni task completato e validato dal Control Plane.

---

## 📦 Come installare l'estensione nel Browser (Chrome, Brave, Edge)

1. Apri il browser su `chrome://extensions/` (oppure `brave://extensions/` o `edge://extensions/`).
2. Attiva la spunta **"Modalità sviluppatore"** (*Developer mode*) in alto a destra.
3. Clicca su **"Carica estensione non pacchettizzata"** (*Load unpacked*).
4. Seleziona la cartella:
   ```
   /Users/opo/hyperspace-agi-1.04/integrations/chrome-extension
   ```
5. L'icona **00MESH Bridge** comparirà nella barra degli strumenti del browser.

---

## 🚀 Guida Rapida all'Uso

1. Assicurati che **Ollama** o **LM Studio** sia aperto e in esecuzione sul tuo computer:
   - **Ollama**: in ascolto su `http://localhost:11434` (default)
   - **LM Studio**: avvia il Local Server su `http://127.0.0.1:1234`
2. Clicca sull'icona dell'estensione **00MESH**:
   - I motori locali e i modelli presenti verranno rilevati automaticamente (badge verde).
3. Inserisci il tuo indirizzo **Wallet Solana** per ricevere le ricompense Proof-of-Useful-Work.
4. Lascia la spunta attiva su **"Condivisione GPU"**:
   - Il nodo si registra sull'Hub e rimane in ascolto di task in background, elaborando richieste di chat completion e ritrasmettendo i token generati in streaming.
