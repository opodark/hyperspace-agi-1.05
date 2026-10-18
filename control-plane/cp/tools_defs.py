# SPDX-License-Identifier: Apache-2.0
# control-plane/cp/tools_defs.py
# IL CATALOGO DEI TOOL: nativi + connettori, e il suo riallineamento.
#
# Qui ci sono tre cose che in main.py erano legate a filo:
#   _NATIVE_TOOLS        gli 8 tool che offre il control-plane;
#   BUILTIN_TOOLS        il catalogo completo, nativi + connettori;
#   CODE_SANDBOX_TOOL    un tool estratto dal catalogo, non riassegnato mai.
#
# Perche' BUILTIN_TOOLS si riallinea IN PLACE (`[:] =`) e non con una riassegnazione:
# e' la lista che il tool loop, il catalogo MCP e /tools/execute hanno gia' in
# mano. Riassegnarla lascerebbero indietro la lista vecchia. Per questo qui
# dentro si muta, e per questo `_sync_connector_tools` prende i tool dei
# connettori come argomento invece di andare a cercare il ConnectorManager: il
# catalogo non sa e non deve sapere chi gestisce le credenziali, e cosi' questo
# modulo resta puro dati senza un pezzo di runtime.
#
# All'import BUILTIN_TOOLS contiene solo i nativi: il ConnectorManager nasce in
# main.py, che chiama subito `_sync_connector_tools(...)` dopo averlo costruito.
# `code_sandbox` e' nativo, quindi CODE_SANDBOX_TOOL si trova gia' senza i
# connettori — se non lo fosse, questa riga leggerebbe una lista incompleta.

_NATIVE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "moltbook_status",
            "description": "Controlla via API lo stato dell'account Moltbook HyperSpace usando la credenziale montata in sola lettura. Riporta solo pending_claim/claimed, claim URL e codice di verifica se pending. Non mostrare mai la API key. Usa questo tool quando l'utente chiede registrazione, claim o stato Moltbook.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Legge il contenuto testuale di una pagina web pubblica da un URL http/https. Usa questo tool quando l'utente fornisce un URL preciso e chiede di leggerlo/aprirlo; non usare web_search con l'URL come query. Sola lettura: non invia form né interagisce con account. Rifiuta host locali/privati; i redirect vengono restituiti senza seguirli.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Cerca informazioni aggiornate sul web tramite SearXNG (motore self-hosted). Per leggere un URL preciso fornito dall'utente, usa web_fetch; non passare un URL come query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "default": 5}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "omega_query",
            "description": "Cerca nella memoria a lungo termine di HyperSpace AGI.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                    "event_type": {"type": "string"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "omega_store",
            "description": "Salva informazioni importanti nella memoria a lungo termine.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "event_type": {"type": "string", "default": "vault_note"}
                },
                "required": ["content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_mesh_status",
            "description": "Stato della rete HyperSpace: nodi attivi, modelli, heartbeat.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "code_sandbox",
            "description": "Sviluppa e testa codice in un workspace offline e usa-e-getta; non modifica il repository operativo. create (backend docker) prepara un workspace gia' 'seminato' con una copia in sola lettura del repository: docs e sorgenti sono gia' sotto la radice del workspace, quindi leggili con read (path relativo, es. docs/mission-control.md) invece di ricopiarli. run esegue un comando: argv deve essere una lista NON vuota con argv[0] = solo il nome dell'eseguibile ammesso (python, python3, node, npm, npx, pytest, unittest, git), mai un path ne' un nome di script (es. [\"python3\", \"make_pdf.py\"]). write scrive un file (path+content), replace modifica in place (path+old+new). check/verify lanciano pytest/unittest/profile/bandit/ruff; inspect sonda un artifact generato (per un PDF: firma %PDF, numero di pagine, testo estraibile). diff restituisce le modifiche per la revisione. status elenca i workspace, reuse ne riusa uno esistente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["status", "catalog", "check", "verify", "create", "reuse", "list", "read", "write", "replace", "run", "diff", "discard", "inspect"]},
                    "backend": {"type": "string", "enum": ["auto", "docker", "sbx"], "description": "Backend per create; i preset check richiedono docker."},
                    "tool_id": {"type": "string", "enum": ["pytest", "unittest", "profile", "bandit", "ruff"]},
                    "checks": {"type": "array", "description": "Per verify: 1-6 oggetti {tool_id, path, timeout?}. Il risultato passa soltanto se ogni check passa."},
                    "workspace_id": {"type": "string", "description": "Id del workspace (da create/reuse); obbligatorio per read/list/write/replace/run/diff/inspect."},
                    "label": {"type": "string"},
                    "path": {"type": "string", "description": "Percorso relativo alla radice del workspace; mai /seed, /repo o l'id."},
                    "content": {"type": "string", "description": "Contenuto del file da scrivere con write."},
                    "old": {"type": "string", "description": "Per replace: il testo esatto (non vuoto) da sostituire."},
                    "new": {"type": "string", "description": "Per replace: il testo con cui sostituire old."},
                    "expected_occurrences": {"type": "integer", "default": 1},
                    "argv": {"type": "array", "items": {"type": "string"}, "description": "Per run: lista non vuota, argv[0] = solo il nome dell'eseguibile (python/python3/node/npm/npx/pytest/unittest/git), mai un path ne' un nome di script. Es. [\"python3\", \"make_pdf.py\"]."},
                    "cwd": {"type": "string", "default": ".", "description": "Directory di lavoro relativa alla radice del workspace."},
                    "timeout": {"type": "integer", "default": 30},
                    "pattern": {"type": "string", "default": "*"},
                    "limit": {"type": "integer", "default": 200}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "persona_get",
            "description": "Legge la propria identità dichiarata: nome, scopo, valori, confini, capacità e limiti reali. Usalo quando serve restare coerenti con chi sei, invece di improvvisare una risposta su di te.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "persona_note",
            "description": "Annota un fatto su di sé: una preferenza appresa, un limite incontrato, una correzione ricevuta. Entra nel self-model persistente e nelle richieste successive. Solo fatti verificabili, non impressioni.",
            "parameters": {
                "type": "object",
                "properties": {
                    "note": {"type": "string", "description": "Il fatto da annotare, in una frase."},
                    "kind": {"type": "string", "default": "self_observation",
                             "description": "Categoria: self_observation, preference, limit, feedback."}
                },
                "required": ["note"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ask_aurora",
            "description": "Chiedi consiglio alla sorella maggiore Aurora su una questione che non conosci o che è troppo profonda per te. Inoltri la domanda al suo control-plane e lei risponde con la sua saggezza. Usalo quando non sai, o quando diresti 'questo lo sa mia sorella'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "La domanda da inoltrare ad Aurora, in una frase chiara."}
                },
                "required": ["question"]
            }
        }
    }
]

# Catalogo completo. All'import contiene i soli nativi; main.py ci mette dentro
# i tool dei connettori appena il ConnectorManager e' costruito.
# Tool della 1.05 aggiunti al catalogo estratto dalla 1.04.
_NATIVE_TOOLS.extend([{'type': 'function',
  'function': {'name': 'create_website',
               'description': 'Crea una bozza completa di sito statico responsive, con anteprima e '
                              'ZIP scaricabile. Non pubblica né modifica siti esistenti.',
               'parameters': {'type': 'object',
                              'properties': {'name': {'type': 'string'},
                                             'brief': {'type': 'string',
                                                       'description': 'Obiettivo, pubblico, '
                                                                      'contenuti e tono del sito.'},
                                             'template': {'type': 'string',
                                                          'enum': ['landing', 'showcase'],
                                                          'default': 'landing'},
                                             'headline': {'type': 'string'},
                                             'call_to_action': {'type': 'string',
                                                                'default': 'Contattaci'},
                                             'source_html': {'type': 'string',
                                                             'description': 'Nome opzionale di un '
                                                                            'HTML nella raccolta '
                                                                            'ComfyUI: '
                                                                            'prove-colori-anna.html, '
                                                                            'serie-anna-8-20261001.html, '
                                                                            'serie-anna-controllo-fix.html, '
                                                                            'serie-anna-controllo.html, '
                                                                            'serie-anna-notturna.html '
                                                                            'o '
                                                                            'serie-anna-social-20261001.html.'}},
                              'required': ['name', 'brief']}}},
 {'type': 'function',
  'function': {'name': 'wayfinder_map',
               'description': 'Persistent decision planning across sessions. Create/read/update '
                              'maps; claim and resolve autonomous research/task tickets. Human '
                              'decisions and mission handoff require the operator dashboard. '
                              'Updates require current revision. Use references for supporting '
                              'workflow Markdown.',
               'parameters': {'type': 'object',
                              'properties': {'action': {'type': 'string',
                                                        'enum': ['list',
                                                                 'get',
                                                                 'create',
                                                                 'update',
                                                                 'claim',
                                                                 'release',
                                                                 'resolve',
                                                                 'exclude',
                                                                 'references']},
                                             'map_id': {'type': 'string'},
                                             'ticket_key': {'type': 'string'},
                                             'data': {'type': 'object',
                                                      'description': 'Create/update: destination, '
                                                                     'notes, fog[], '
                                                                     'out_of_scope[], '
                                                                     'tickets[{key,title,question,kind,mode,dependencies[]}]. '
                                                                     'Update also revision. '
                                                                     'Claim/release: '
                                                                     'revision,owner. '
                                                                     'Resolve/exclude: '
                                                                     'revision,owner,answer. Never '
                                                                     'invent human answers.'}},
                              'required': ['action']}}},
 {'type': 'function',
  'function': {'name': 'website_status',
               'description': 'Legge un sito statico già creato (sola lettura): nome, template, '
                              'sorgente HTML, quante immagini contiene la pagina, se la sezione '
                              "galleria c'è, quanti asset stanno su disco e l'anteprima. Non "
                              'modifica né pubblica nulla.',
               'parameters': {'type': 'object',
                              'properties': {'project_id': {'type': 'string',
                                                            'description': 'Id del progetto '
                                                                           'restituito da '
                                                                           'create_website (es. '
                                                                           'anna-galleria-hyperspace-82175fbf). '
                                                                           'Se manca, elenca i '
                                                                           'progetti esistenti.'}},
                              'required': []}}},
 {'type': 'function',
  'function': {'name': 'reel_prepare_project',
               'description': "Prepara un progetto nell'editor reel HyperSpace usando nomi esatti: "
                              'per source=anna accetta solo immagini approvate; per source=share '
                              'usa file in hyperspace_share. Copia 1-30 media e restituisce il '
                              "link all'editor. Non genera né pubblica il video.",
               'parameters': {'type': 'object',
                              'properties': {'source': {'type': 'string',
                                                        'enum': ['anna', 'share']},
                                             'filenames': {'type': 'array',
                                                           'items': {'type': 'string'},
                                                           'description': 'Nomi file esatti, da 1 '
                                                                          'a 30.'},
                                             'creator': {'type': 'string',
                                                         'enum': ['Anna',
                                                                  'Aurora',
                                                                  'Altro progetto']},
                                             'brief': {'type': 'string',
                                                       'description': 'Brief di montaggio da '
                                                                      "precompilare nell'editor, "
                                                                      'massimo 4000 caratteri.'},
                                             'audio_filename': {'type': 'string',
                                                                'description': 'Nome di un file '
                                                                               'audio già presente '
                                                                               'in '
                                                                               'hyperspace_share; '
                                                                               'viene copiato nel '
                                                                               'progetto per lo '
                                                                               'scheduler.'}},
                              'required': ['source', 'filenames']}}},
 {'type': 'function',
  'function': {'name': 'reel_schedule_daily',
               'description': 'Attiva un Reel al giorno in coda di revisione locale sul Mac. Non '
                              'pubblica sui social.',
               'parameters': {'type': 'object',
                              'properties': {'project_id': {'type': 'string'},
                                             'daily_time': {'type': 'string', 'default': '09:00'},
                                             'timezone_name': {'type': 'string',
                                                               'default': 'Europe/Rome'},
                                             'duration': {'type': 'integer',
                                                          'enum': [30, 60],
                                                          'default': 30},
                                             'replace_existing': {'type': 'boolean',
                                                                  'default': False}},
                              'required': ['project_id']}}},
 {'type': 'function',
  'function': {'name': 'reel_daily_status',
               'description': "Mostra schedulazione e stato dell'ultimo Reel.",
               'parameters': {'type': 'object', 'properties': {}, 'required': []}}},
 {'type': 'function',
  'function': {'name': 'reel_render_now',
               'description': 'Accoda immediatamente un render Reel per revisione.',
               'parameters': {'type': 'object', 'properties': {}, 'required': []}}},
 {'type': 'function',
  'function': {'name': 'reel_cancel_daily',
               'description': 'Disattiva la schedulazione dei Reel.',
               'parameters': {'type': 'object', 'properties': {}, 'required': []}}},
 {'type': 'function',
  'function': {'name': 'reel_subject_fx_preview',
               'description': 'Accoda sul Mac una prova Reel 1080x1920 con zoom del soggetto, luce '
                              'sulla sagoma e lampi elettrici sui beat. Video e audio devono '
                              'essere nella radice di hyperspace_share; il livello karaoke MOV è '
                              'facoltativo. Non pubblica sui social.',
               'parameters': {'type': 'object',
                              'properties': {'video_filename': {'type': 'string'},
                                             'audio_filename': {'type': 'string'},
                                             'karaoke_filename': {'type': 'string'}},
                              'required': ['video_filename', 'audio_filename']}}},
 {'type': 'function',
  'function': {'name': 'reel_subject_fx_status',
               'description': 'Mostra stato ed esito della prova Reel con effetti sul soggetto.',
               'parameters': {'type': 'object',
                              'properties': {'job_id': {'type': 'string'}},
                              'required': ['job_id']}}}])

BUILTIN_TOOLS = list(_NATIVE_TOOLS)

# La riga di commento sopra questa sezione spiega perche' resta valido: e' il
# tool del sandbox di codice, che non viene mai riassegnato.
CODE_SANDBOX_TOOL = next(tool for tool in BUILTIN_TOOLS
                         if tool.get("function", {}).get("name") == "code_sandbox")


def _sync_connector_tools(extra) -> None:
    """Riallinea i tool dei connettori dentro BUILTIN_TOOLS (in place).

    Da chiamare dopo `connector_manager.reload()`: un connettore appena
    configurato deve comparire SUBITO nel tool loop chat, nel catalogo MCP e in
    /tools/execute, e uno spento (CONNECTOR_<NAME>_ENABLED=false) deve sparire
    dall'esposizione, non solo dall'esecuzione.

    `extra` sono i tool che il ConnectorManager espone al momento: passarli
    invece di leggerli da qui e' cio' che tiene questo modulo separato dal
    runtime.
    """
    BUILTIN_TOOLS[:] = _NATIVE_TOOLS + list(extra)
