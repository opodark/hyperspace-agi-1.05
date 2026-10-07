# Website Builder

MVP statico end-to-end: una richiesta strutturata genera un progetto isolato con
`index.html`, `styles.css`, `app.js`, manifest, preview locale e ZIP scaricabile.

- `POST /website/projects` accetta `name`, `brief`, `template` (`landing` o
  `showcase`), `headline` e `call_to_action`;
- `GET /website/preview/<id>/` serve esclusivamente i file statici consentiti;
- `GET /website/projects/<id>/download` produce il bundle ZIP con manifest.

La creazione richiede `X-Hyperspace-Network-Token`; il tool produce per il download
un URL firmato limitato al singolo progetto. La preview non esegue codice server e
non può attraversare la directory del progetto. Nessun deploy avviene automaticamente.

`create_website` accetta inoltre `source_html`, limitato agli HTML presenti nella
cartella output ComfyUI montata in sola lettura. Copia sotto `assets/` fino a 40
immagini effettivamente citate dal documento e le include nell'anteprima e nello ZIP.
Gli URL locali `file:///...` non vengono conservati e gli originali non sono modificati.
