# Comic Builder

Il Comic Builder trasforma una storyline in un progetto persistente con personaggi,
continuity bible, episodi e vignette. Testo e dialoghi restano separati dalle immagini:
ComfyUI riceve una singola scena senza balloon o scritte, mentre la tavola finale può
comporre didascalie e dialoghi in modo deterministico.

API amministrative:

- `POST /comic/projects` crea storia, cast e regole di continuità;
- `POST /comic/projects/<id>/episodes` aggiunge sceneggiatura e vignette;
- `POST /comic/projects/<id>/episodes/<ep>/panels/<n>/render` accoda una vignetta;
- `GET /comic/projects/<id>` riconcilia file e stato con la coda immagini.

Le API richiedono `X-Hyperspace-Network-Token`. Nessun episodio viene pubblicato
automaticamente: diario e social saranno destinazioni esplicite di una fase successiva.

## Editor visuale

`/comics` elenca i progetti e apre `/comic/editor?project=<id>`, adattamento di
Panel Foundry v8 (MIT). Storyline, episodi e immagini restano nel JSON HyperSpace;
l'editor aggiunge il layout manuale con pagine, pannelli, crop e balloon. `SAVE
PROJECT` persiste il layout nello stesso progetto, mentre `GENERATE` accoda un job
nel bridge ComfyUI del Control Plane: la configurazione SD-Forge originale non è
usata dal percorso HyperSpace.
