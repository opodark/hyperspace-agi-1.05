# Anna Voice nel web-node

## Obiettivo

Dare ad Anna orecchie e voce usando prevalentemente le risorse del dispositivo
dell'utente. Il web-node acquisisce e trascrive l'audio, genera la risposta e la
legge senza impegnare per default i modelli della mesh. Il control-plane riceve
testo soltanto quando una modalità autenticata richiede memoria o capability
centrali.

Il video e i servizi esterni restano una fase successiva. Questo documento copre
solo audio, modello locale e avatar.

## Flusso locale

```text
Microfono
   ↓
push-to-talk + VAD
   ↓
Whisper locale (Transformers.js/WebGPU)
   ↓
testo correggibile dall'utente
   ↓
WebLLM locale
   ↓
risposta testuale
   ↓
TTS locale + avatar
```

L'audio grezzo non viene inviato alla mesh né conservato. La prima versione usa
push-to-talk: il microfono sempre attivo e la wake word richiedono una decisione
successiva, indicatori permanenti e un comando di pausa immediato.

Transformers.js documenta l'esecuzione di Whisper direttamente su WebGPU:
<https://huggingface.co/docs/transformers.js/guides/webgpu>.

## MVP

1. Pulsante microfono accanto al composer della chat locale.
2. Consenso browser esplicito e stato `fermo`, `ascolto`, `trascrivo`.
3. Trascrizione multilingue locale, con italiano preferito.
4. Testo inserito nel composer e modificabile prima dell'invio.
5. Risposta del modello locale con streaming.
6. Lettura tramite `speechSynthesis`, selezione della voce italiana e controlli
   di velocità, tono e volume.
7. Interruzione immediata della voce e nessuna registrazione persistente.
8. Avatar con stati `idle`, `listening`, `thinking`, `speaking`, `error`.

Il TTS di sistema chiude rapidamente il ciclo funzionale ma non garantisce la
stessa voce su tutti i computer. La seconda fase userà un modello TTS locale e
una voce sintetica propria di Anna; l'eventuale derivazione da una voce reale
richiede consenso esplicito della persona interessata.

## Modelli di chat

I modelli dimostrativi attuali (0,5B–1,7B) verificano WebLLM ma non sono una base
sufficiente per un assistente aziendale. La sola RAM di sistema non determina la
compatibilità: nel browser contano WebGPU, memoria grafica dedicata o condivisa,
limiti dei buffer e implementazione del driver.

Profili iniziali:

| Profilo | Modello | Memoria WebGPU indicativa | Destinazione |
|---|---|---:|---|
| compatibilità | `gemma-2-2b-it-q4f16_1-MLC` | ~1,9 GB | GPU limitata |
| standard | `Llama-3.2-3B-Instruct-q4f16_1-MLC` | ~2,3 GB | default iniziale |
| potenziato | `gemma-2-9b-it-q4f16_1-MLC` | ~6,4 GB | GPU realmente capace |

WebLLM dichiara supporto alla famiglia Gemma e distribuisce artefatti
precompilati per Gemma 2. Gemma 3/4B sarebbe una fascia interessante, ma non va
usata come default finché non avremo un artefatto MLC compilato, versionato e
verificato sui browser aziendali.

## Selezione adattiva

Il primo avvio non sceglie il modello dalla RAM dichiarata. Esegue invece un
benchmark breve:

1. verifica disponibilità e feature WebGPU;
2. legge i limiti esposti dall'adapter;
3. misura allocazione e inferenza con un carico piccolo;
4. classifica il dispositivo;
5. propone il modello e consente sempre di ridurlo;
6. salva localmente scelta, risultato e versione del benchmark;
7. ripete il benchmark solo dopo cambiamenti di browser, driver o policy.

Il modello viene scaricato su richiesta, conservato nella cache del browser e
scaricato dalla GPU dopo un periodo di inattività. Un errore di allocazione fa
retrocedere al profilo inferiore senza ricaricare la pagina.

## Modalità operative

### Locale pubblica

```text
Whisper locale → WebLLM locale → TTS locale
```

Non usa memoria privata né modelli della mesh. Può usare una presentazione
pubblica e compatta di Anna, ma non il suo contesto privato.

### Anna privata autenticata

La trascrizione resta locale; il testo può raggiungere il control-plane per
memoria, strumenti o richieste complesse. La risposta torna al TTS locale. Questa
modalità richiede login, consenso e quote, e non deve essere esposta dal
web-node pubblico prima dell'autenticazione.

In futuro il control-plane potrà consegnare al browser un profilo compatto e
firmato, consentendo al modello locale di mantenere tono e identità senza
scaricare memorie private non necessarie.

## Distribuzione aziendale

Su centinaia di PC il download pubblico dei pesi è un costo operativo: un modello
da circa 6 GB moltiplicato per cento dispositivi produce centinaia di GB di
traffico e picchi simultanei.

Il profilo aziendale deve quindi prevedere:

- hosting interno o cache aziendale dei pesi;
- manifest firmato con versione e checksum;
- rollout progressivo e finestre di aggiornamento;
- download scaglionati e riprendibili;
- quote CPU/GPU, rilevamento batteria e modalità risparmio;
- nessun caricamento del modello finché l'utente non apre Anna;
- telemetria tecnica senza prompt, audio o contenuti dello schermo;
- revoca centralizzata di modelli o versioni difettose;
- fallback testuale leggero sui dispositivi non compatibili.

## Criteri di riuscita

- L'utente parla in italiano e vede una trascrizione locale correggibile.
- La risposta viene generata e pronunciata senza inviare audio alla mesh.
- L'interfaccia rimane reattiva perché ASR e LLM lavorano fuori dal thread UI.
- Un PC non compatibile retrocede automaticamente senza blocchi o crash.
- Dopo inattività, microfono, stream e memoria GPU vengono rilasciati.
- Il benchmark permette di motivare la scelta del modello per ogni dispositivo.

## Sequenza di sviluppo

1. `web-node/src/voice.js`: microfono, registrazione, decoding e TTS.
2. Worker separato per Whisper.
3. UI push-to-talk e stati dell'avatar.
4. Benchmark WebGPU e selezione adattiva.
5. Nuovo catalogo Gemma/Llama con fallback.
6. Cache, unload e gestione degli errori di memoria.
7. Test Mac/Windows e matrice browser/GPU.
8. Modalità privata autenticata.
9. TTS locale dedicato ad Anna.
10. Integrazione con Anna Desktop Guide.
