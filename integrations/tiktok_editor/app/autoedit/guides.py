# SPDX-License-Identifier: Apache-2.0
"""Small, self-contained comic help cards for every editor control."""
from __future__ import annotations

from html import escape


GUIDES = {
    "webui_project": ("Progetti WebUI", "Le scene arrivano insieme", "Chiedi a WebUI di preparare un progetto reel, aggiornalo qui e aggiungi la tua musica."),
    "scene_ai": ("Analisi visiva", "Il modello guarda la scena", "Descrive soggetto e sfondo, poi suggerisce colore, movimento e un impatto breve sui beat forti. Non separa i pixel dello sfondo."),
    "files": ("Foto e video", "Anna porta le scene", "Aggiungi le immagini o i video che vuoi vedere nel reel."),
    "audio": ("Canzone", "Aurora dà il tempo", "Carica un MP3 o WAV: i tagli seguiranno i beat del brano."),
    "table": ("Ordine e selezione", "Anna sceglie", "Togli la spunta per escludere; cambia il numero in ordine per spostare una scena."),
    "edit_style": ("Stile di montaggio", "Il regista sceglie una ricetta", "Prova Pulito per iniziare. Personalizzato sblocca gli effetti scelti sotto."),
    "speed": ("Velocità tagli", "Batte il tempo", "Normale cambia scena a ogni beat; Veloce lo fa due volte."),
    "aspect": ("Formato", "La cornice cambia", "Per TikTok e Reels scegli Verticale 9:16."),
    "transition": ("Transizioni", "Una scena incontra l'altra", "Uno stacco è immediato; una dissolvenza mescola due scene."),
    "duration_preset": ("Autocut", "Il cronometro si ferma", "30 o 60 secondi producono un file di durata esatta. Il brano deve essere abbastanza lungo."),
    "preset": ("Preset", "Una ricetta nel cassetto", "Salva le impostazioni che ti piacciono e ricaricale al prossimo reel."),
    "provider": ("Provider AI", "Anna chiama l'assistente", "HyperSpace usa il suo modello locale OpenAI-compatibile. Puoi cambiarlo qui."),
    "model": ("Modello AI", "Chi suggerisce il montaggio?", "Il modello trovato automaticamente propone parametri dal tuo brief."),
    "base_url": ("Indirizzo AI", "La strada per il modello", "Di norma è già trovato: cambia URL solo se usi un server diverso."),
    "api_key": ("Chiave AI", "La porta si apre", "Per HyperSpace locale è precompilata; per servizi esterni usa la tua chiave."),
    "brief": ("Brief", "Racconta l'idea", "Scrivi per esempio: «reel dolce, tagli lenti, titolo Estate». Poi premi Compila."),
    "outline": ("Contorno neon", "La luce segue Anna", "Il bordo colorato viene ricavato dalla maschera persona; attiva prima Riconosci la persona. La maschera può perdere dettagli sottili o confondere il palo con lo sfondo."),
    "style": ("Colore", "La scena cambia luce", "Scegli l'aspetto generale: vivido, caldo o più cinematografico."),
    "motion": ("Movimento", "La foto prende vita", "Un leggero zoom rende meno statiche le immagini ferme."),
    "motion_intensity": ("Intensità movimento", "Piano o deciso?", "Tieni basso per un effetto naturale; alza per più energia."),
    "variety": ("Varietà", "Ogni scena è un po' diversa", "Alza se il reel sembra ripetitivo; abbassa per uniformità."),
    "impact": ("Effetti d'impatto", "Boom sul beat forte", "Seleziona gli effetti da usare nei momenti musicali più marcati."),
    "grain": ("Grana", "Un tocco di pellicola", "Aggiunge una texture leggera. Zero significa nessuna grana."),
    "vignette": ("Vignettatura", "L'occhio va al centro", "Scurisce appena i bordi per concentrare l'attenzione."),
    "chromatic": ("Aberrazione cromatica", "Colori che slittano", "Crea un piccolo disturbo RGB: usalo con moderazione."),
    "slowmo": ("Slow-motion", "Il tempo rallenta", "Sulle clip video alterna rallentamenti e accelerazioni."),
    "hold_prob": ("Clip hero", "Fermiamoci qui", "Aumenta la probabilità che una scena importante duri due beat."),
    "title_text": ("Titolo", "Parole in scena", "Scrivi il testo da mostrare; lascia vuoto per non aggiungerlo."),
    "title_pos": ("Posizione titolo", "Dove lo mettiamo?", "Scegli alto, centro o basso evitando volti e dettagli importanti."),
    "title_start": ("Inizio titolo", "Entra in scena", "Indica il secondo in cui il titolo compare."),
    "title_dur": ("Durata titolo", "Resta leggibile", "Dai al testo abbastanza tempo per essere letto."),
    "wm_file": ("Logo", "La tua firma", "Carica un PNG trasparente, oppure lascia vuoto."),
    "wm_pos": ("Angolo logo", "La firma si sposta", "Scegli l'angolo che copre meno la scena."),
    "wm_scale": ("Dimensione logo", "Piccolo ma visibile", "Regola quanto spazio occupa il logo."),
    "wm_opacity": ("Opacità logo", "Più o meno discreto", "Abbassa per una firma semitrasparente."),
    "hook_hold": ("Hook iniziale", "Un attimo di attenzione", "Ferma la prima scena fino a due secondi prima che inizi il ritmo."),
    "audio_start": ("Inizio canzone", "Salta l'intro", "Scegli da quale secondo del brano partire."),
    "beat_offset": ("Sincronia fine", "Sul colpo giusto", "Se i tagli sembrano tardivi, sposta leggermente il tempo."),
    "xfade_ms": ("Durata transizione", "Quanto si sovrappongono?", "Valori piccoli danno stacchi netti; valori alti sfumano le scene."),
    "snap_onsets": ("Transienti", "Ascolta i colpi reali", "Aggancia i tagli anche agli attacchi di batteria. Consigliato."),
    "dynamic_pacing": ("Ritmo dinamico", "Accelera nel ritornello", "Usa più tagli nei momenti intensi e meno in quelli calmi."),
    "strong_only": ("Beat forti", "Solo i colpi principali", "Riduce i tagli e privilegia i battiti più marcati."),
    "shuffle": ("Ordine casuale", "Mischia le scene", "Ignora l'ordine della tabella e crea una sequenza nuova."),
    "max_dur": ("Durata massima", "Un limite libero", "Vale solo con Autocut Libero/manuale; 30/60 secondi hanno priorità."),
    "seed": ("Seed", "Rifacciamolo uguale", "Usa lo stesso numero per ripetere le scelte casuali."),
    "subtitles_file": ("File sottotitoli", "I testi prendono ritmo", "Carica un file .srt o .vtt con i timestamp sincronizzati alla voce o alla canzone."),
    "subtitles_style": ("Stile sottotitoli", "Look TikTok o minimale", "Scegli il font bianco con contorno nero marcato, la classica pillola scura o il giallo virale."),
    "subtitles_pos": ("Posizione sottotitoli", "Sempre visibili", "In basso calcola la safe-zone sopra l'interfaccia di TikTok e Reels per non coprire il testo."),
    "subtitles_text": ("Sottotitoli diretti", "Incolla il testo", "Puoi incollare direttamente le battute in formato SRT o VTT con i relativi tempi."),
}


def comic_styles() -> str:
    # colori dalle variabili del tema Gradio: leggibili sia in chiaro sia in scuro
    return """<style>
    .hs-comic-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:6px;margin:6px 0 10px}
    .hs-comic{border:1px solid var(--border-color-primary);border-radius:10px;background:var(--block-background-fill);
      color:var(--body-text-color);overflow:hidden;font-size:13px}
    .hs-comic summary{cursor:pointer;padding:6px 10px;font-weight:600;list-style:none;color:var(--body-text-color-subdued)}
    .hs-comic summary:hover{color:var(--body-text-color)}
    .hs-comic summary::before{content:'💬 ';}
    .hs-comic summary::-webkit-details-marker{display:none}
    .hs-comic[open]{grid-column:span 2}
    .hs-comic-panels{display:grid;grid-template-columns:1fr 1fr;gap:6px;padding:0 8px 9px}
    .hs-comic-panel{border:1px solid var(--border-color-primary);border-radius:8px;padding:7px;
      background:var(--background-fill-secondary);font-size:12px;line-height:1.4}
    .hs-comic-face{font-size:18px;display:block;margin-bottom:3px}
    .hs-head{align-items:center}
    .hs-head h1{margin:0}
    .hs-draft{text-align:right;color:var(--body-text-color-subdued)}
    .hs-side{position:sticky;top:12px;align-self:flex-start}
    .hs-note{font-size:12px;color:var(--body-text-color-subdued)}
    @media (max-width:900px){.hs-side{position:static}.hs-comic[open]{grid-column:auto}}
    </style>"""


def comics_for(*keys: str) -> str:
    cards = []
    for key in keys:
        title, scene, tip = GUIDES[key]
        cards.append(
            '<details class="hs-comic"><summary>' + escape(title) + '</summary>'
            '<div class="hs-comic-panels"><div class="hs-comic-panel">'
            '<span class="hs-comic-face">🎬</span>' + escape(scene) + '</div>'
            '<div class="hs-comic-panel"><span class="hs-comic-face">✨</span>'
            + escape(tip) + '</div></div></details>'
        )
    return '<div class="hs-comic-grid">' + ''.join(cards) + '</div>'
