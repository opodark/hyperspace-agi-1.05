# Automazione Vocale HyperSpace (Kokoro TTS & Telegram)

HyperSpace integra un motore di sintesi vocale neurale avanzato basato su **Kokoro-82M v1.0** e ONNX Runtime. Il sistema permette di dare voce istantanea a qualsiasi agente, prompt o testo, con riproduzione diretta sugli altoparlanti di sistema, esportazione file e consegna come messaggio vocale su Telegram.

## Architettura e Componenti

1. **Microservizio Neurale (`scripts/kokoro_tts_service.py`)**:
   - Porta: `8880`
   - Runtime: `data/kokoro-venv` (ONNX Runtime, espeakng-loader, soundfile)
   - Modello: `kokoro-v1.0.onnx` (310 MB) + `voices-v1.0.bin` (27 MB)
   - Endpoint: `POST /v1/audio/speech` (compatibile OpenAI TTS), `POST /v1/audio/transcriptions` (STT Whisper)
   - Voci supportate: `if_sara` (italiano femminile, naturale), `im_nicola` (italiano maschile), `af_heart` (inglese)

2. **Strumento CLI (`scripts/speak.py`)**:
   - Esegue la sintesi e gestisce riproduzione immediata, output su file e consegna Telegram.

## Utilizzo dello Script CLI

### 1. Lettura Immediata ad Alta Voce
```bash
# Legge il testo direttamente dagli altoparlanti (afplay su macOS / SoundPlayer su Windows):
python scripts/speak.py "Mi piace pensare a un prato cibernetico..."

# Con voce maschile italiana:
python scripts/speak.py "Aggiornamento di sistema completato." --voice im_nicola

# Modulando la velocità:
python scripts/speak.py "Lettura lenta e scandita." --speed 0.85
```

### 2. Lettura da File di Testo o Poesia
```bash
python scripts/speak.py -f docs/poesia.txt --voice if_sara
```

### 3. Pipeline da Standard Input (Pipe)
```bash
cat messaggio.txt | python scripts/speak.py
```

### 4. Salvataggio su File Audio
```bash
python scripts/speak.py "Messaggio importante" --out data/audio/notifica.wav --no-play
```

### 5. Invio come Nota Vocale su Telegram
```bash
# Invia una vera nota vocale (sendVoice) alla chat specificata:
python scripts/speak.py "Ecco il riepilogo vocale di oggi" --telegram 123456789
```

## Integrazione con Open WebUI

- **Engine**: `OpenAI`
- **API Base URL**: `http://host.docker.internal:8880/v1`
- **Voice**: `if_sara`
