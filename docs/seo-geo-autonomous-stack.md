# Autonomous SEO & GEO Optimization Stack

Questo stack unifica tre repository open-source d'avanguardia per l'ottimizzazione continua, il posizionamento nei motori di ricerca tradizionali (Google) e nei motori di risposta ad intelligenza artificiale (ChatGPT, Perplexity, Gemini, Claude, Google AI Overviews) per **`www.zerozerocomputer.it`** e **`os.zerozerocomputer.it`**.

---

## 1. I Tre Repository Integrati

| Progetto | Autore | Ruolo nell'Architettura HyperSpace | Modalità d'Esecuzione |
|---|---|---|---|
| **`geo-optimizer-skill`** | [Auriti-Labs](https://github.com/Auriti-Labs/geo-optimizer-skill) | **GEO / AEO (Generative Engine Optimization)**: Valuta e ottimizza la citabilità del sito dagli LLM (score 0-100), accessibilità dei crawler AI, schema JSON-LD, `/llms.txt`. | CLI (`/Users/opo/.local/bin/geo`) & MCP (`geo-mcp`) |
| **`mcp-gsc`** | [AminForou](https://github.com/AminForou/mcp-gsc) | **Google Search Console Analytics**: Query in linguaggio naturale per click, impression, CTR, anomalie di traffico e URL inspection. | Server MCP (`/Users/opo/.local/bin/mcp-gsc`) |
| **`open-seo`** | [every-app](https://github.com/every-app/open-seo) | **Technical SEO & AI Visibility Tracking**: Monitoraggio rank tracking e Lighthouse audit tecnico senza abbonamenti ricorrenti. | Server MCP (`https://app.openseo.so/mcp`) |

---

## 2. Tool Esposti agli Agenti di HyperSpace

Nel Control Plane (`control-plane/connectors/`), gli agenti possono invocare autonomamente i seguenti tool registrati:

### Connettore `seo` ([`control-plane/connectors/seo.py`](file:///Users/opo/hyperspace-agi-1.04/control-plane/connectors/seo.py))
* `seo_audit_site(url)`: Esegue l'audit GEO/AEO completo sul target.
* `seo_get_latest_report()`: Legge l'ultimo report con punteggio, check passati e azioni correttive prioritarie.
* `seo_inspect_llms(domain)`: Verifica conformità e integrità del file `/llms.txt`.
* `seo_generate_schema_jsonld(name, url)`: Genera codice schema validato per Knowledge Graph AI (Organization, WebSite, SoftwareApplication).

### Connettore `scout` ([`control-plane/connectors/scout.py`](file:///Users/opo/hyperspace-agi-1.04/control-plane/connectors/scout.py))
* `scout_web_read(url)`: Lettura pulita di pagine web senza cookie-wall né pubblicità.
* `scout_get_trends(limit)`: Restituisce le tendenze culturali attuali per ispirazione.
* `scout_harvest_trends(topic, channel)`: Interroga YouTube, Reddit, GitHub o Web a costo zero API.

---

## 3. Server MCP per Agenti Esterni & IDE

I server sono dichiarati in [`config/mcp_servers.json`](file:///Users/opo/hyperspace-agi-1.04/config/mcp_servers.json) per essere agganciati da Claude Code, Cursor, Antigravity o Windsurf:

```json
{
  "mcpServers": {
    "geo-optimizer": {
      "command": "/Users/opo/.local/bin/geo-mcp",
      "args": []
    },
    "mcp-gsc": {
      "command": "/Users/opo/.local/bin/mcp-gsc",
      "args": []
    },
    "open-seo": {
      "url": "https://app.openseo.so/mcp"
    }
  }
}
```

---

## 4. Automazione Schedulata Continua (24/7)

1. **Automazione SEO/GEO** ([`scripts/auto_seo_optimizer.py`](file:///Users/opo/hyperspace-agi-1.04/scripts/auto_seo_optimizer.py)):
   * Monitora periodicamente ogni 12 ore il punteggio del sito, verificando la compatibilità con i 27 bot AI e salvando i report in [`data/reports/seo_geo_audit_latest.json`](file:///Users/opo/hyperspace-agi-1.04/data/reports/seo_geo_audit_latest.json).
   * LaunchAgent: [`integrations/com.hyperspace.seo-optimizer.plist`](file:///Users/opo/hyperspace-agi-1.04/integrations/com.hyperspace.seo-optimizer.plist).

2. **Automazione Trend Scouting** ([`scripts/auto_trend_scout.py`](file:///Users/opo/hyperspace-agi-1.04/scripts/auto_trend_scout.py)):
   * Raccoglie ogni 6 ore e alle 23:30 le tendenze culturali e scientifiche dal web per nutrire il nocturnal dream loop di Anna e Aurora.
   * LaunchAgent: [`integrations/com.hyperspace.trend-scout.plist`](file:///Users/opo/hyperspace-agi-1.04/integrations/com.hyperspace.trend-scout.plist).
