#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Superficie locale, di sola lettura, per il grafo del repository (graphify).

Perche' esiste. Il grafo di graphify produce un `graph.html` statico che nessuno
serve, invecchia in silenzio e di suo non dice di essere vecchio; e le community
di default si chiamano `Community 0`, `Community 1`... perche' il naming
semantico passa da un LLM, che qui e' il passo lento. Questa superficie chiude i
tre buchi senza toccare il runtime:

- **la serve**: HTTP su loopback, come gli altri strumenti di sviluppo
  (`docs/graphify.md`); niente container, niente porte nello stack;
- **dichiara la freschezza**: il commit da cui il grafo e' stato costruito
  (`built_at_commit` in `graph.json`, `Graph Freshness` nel report) contro il
  `HEAD` di adesso, piu' l'eta' del file;
- **da' un nome alle community**, derivato localmente dal grafo (hub + directory
  dominante dei membri). E' meno bello di un nome scritto da un modello, ma e'
  deterministico, offline e c'e' sempre; per i nomi semantici la pagina mostra
  il comando che li chiede.

Regole, le stesse degli altri strumenti di sviluppo:

- solo `127.0.0.1`: nessuna esposizione, nessun host diverso da loopback di default;
- **sola lettura**: legge `graph.json` e `GRAPH_REPORT.md`, non lancia graphify,
  non scrive un byte nella working tree. Le rigenerazioni restano comandi che
  l'operatore lancia a mano e che la pagina stampa;
- **nessun percorso arbitrario**: si servono solo le directory `graphify-out*`
  che stanno nella radice del repository.

Uso:
    .venv/bin/python scripts/graphify_surface.py --check
    .venv/bin/python scripts/graphify_surface.py            # http://127.0.0.1:7871
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, Response, jsonify, request

ROOT = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"                      # invariante: solo loopback, mai l'indirizzo wildcard
PORT = int(os.getenv("GRAPHIFY_SURFACE_PORT", "7871"))
DIR_PREFIX = "graphify-out"             # ammesse: graphify-out, graphify-out-docs, ...
GIT_HEAD_ARGV = ["git", "rev-parse", "--short", "HEAD"]
_PLACEHOLDER = re.compile(r"^Community\s+\d+$")


# ── Lettura del grafo ────────────────────────────────────────────────────────

def graph_dir_candidates(root: Path = ROOT) -> list[Path]:
    """Le directory `graphify-out*` della radice che contengono un `graph.json`."""
    if not root.is_dir():
        return []
    return [p for p in sorted(root.iterdir())
            if p.is_dir() and p.name.startswith(DIR_PREFIX)
            and (p / "graph.json").is_file()]


def resolve_dir(name: str, root: Path = ROOT) -> Path | None:
    """Risolve una directory del grafo senza uscire dalla radice.

    `None` per qualunque cosa che non sia una `graphify-out*` diretta della
    radice: e' la difesa contro `?dir=../../etc`.
    """
    if not name or "/" in name or "\\" in name or name in {".", ".."}:
        return None
    candidato = (root / name).resolve()
    if candidato.parent != Path(root).resolve() or not candidato.name.startswith(DIR_PREFIX):
        return None
    return candidato if (candidato / "graph.json").is_file() else None


def load_graph(dir_path: Path) -> dict:
    """Il `graph.json` di una directory, o un errore leggibile."""
    with (dir_path / "graph.json").open(encoding="utf-8") as fh:
        dati = json.load(fh)
    if not isinstance(dati, dict):
        raise ValueError("graph.json non contiene un oggetto")
    return dati


def _mtime_iso(path: Path) -> str | None:
    try:
        ts = path.stat().st_mtime
    except OSError:
        return None
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _top_dir(node: dict) -> str:
    """La cartella di primo livello del file del nodo (`control-plane`, `docs`...)."""
    src = str(node.get("source_file") or "").strip()
    if not src:
        return "(senza file)"
    parti = Path(src).parts
    return parti[0] if len(parti) > 1 else "(radice)"


def community_labels(graph: dict) -> dict:
    """Etichette **derivate** per community, piu' gradi e vicinanze per nodo.

    Per ogni community: il nodo piu' connesso (l'hub) e la directory dominante
    fra i membri. Il nome e' `"<hub> · <directory>"`, cosi' una community smette
    di chiamarsi `Community 37` e comincia a dire cosa c'e' dentro. Quando il
    grafo ha nomi semantici veri (`community_name` non segnaposto) quelli
    vincono: la derivazione riempie i buchi, non sovrascrive il lavoro del
    modello.
    """
    nodes = graph.get("nodes") or []
    links = graph.get("links") or []
    gradi: dict[str, int] = {}
    vicini: dict[str, list[dict]] = {}
    for arco in links:
        a, b = arco.get("source"), arco.get("target")
        if a is None or b is None:
            continue
        gradi[a] = gradi.get(a, 0) + 1
        gradi[b] = gradi.get(b, 0) + 1
        relazione = str(arco.get("relation") or "")
        vicini.setdefault(a, []).append({"id": b, "relation": relazione, "dir": "out"})
        vicini.setdefault(b, []).append({"id": a, "relation": relazione, "dir": "in"})

    per_com: dict[int, list[dict]] = {}
    for nodo in nodes:
        cid = nodo.get("community")
        if isinstance(cid, int):
            per_com.setdefault(cid, []).append(nodo)

    communities: dict[str, dict] = {}
    segnaposto = 0
    nomi_veri = 0
    for cid, membri in per_com.items():
        ordinati = sorted(membri, key=lambda n: (-gradi.get(n.get("id"), 0),
                                                 str(n.get("label") or "")))
        hub = ordinati[0]
        conteggi: dict[str, int] = {}
        for nodo in membri:
            d = _top_dir(nodo)
            conteggi[d] = conteggi.get(d, 0) + 1
        dominante = sorted(conteggi.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        dichiarato = str(hub.get("community_name") or "").strip()
        if dichiarato and not _PLACEHOLDER.match(dichiarato):
            nome, derivato, nomi_veri = dichiarato, False, nomi_veri + 1
        else:
            nome = f"{hub.get('label') or '?'} · {dominante}"
            derivato, segnaposto = True, segnaposto + 1
        communities[str(cid)] = {
            "id": cid,
            "name": nome,
            "derived": derivato,
            "hub": hub.get("label") or "",
            "hub_id": hub.get("id"),
            "hub_file": hub.get("source_file") or "",
            "dir": dominante,
            "size": len(membri),
            "files": [{"file": f, "n": n} for f, n in
                      sorted(conteggi.items(), key=lambda kv: (-kv[1], kv[0]))[:3]],
        }
    return {
        "communities": communities,
        "degree": gradi,
        "neighbours": vicini,
        "names": {"derived": segnaposto, "declared": nomi_veri, "total": len(per_com)},
    }


# ── Freschezza ───────────────────────────────────────────────────────────────

def head_commit(root: Path = ROOT) -> str | None:
    """`HEAD` abbreviato del repository, o `None` se git non risponde.

    L'unico sottoprocesso del modulo: sola lettura, nessun argomento che possa
    scrivere qualcosa.
    """
    try:
        esito = subprocess.run(GIT_HEAD_ARGV, cwd=str(root), capture_output=True,
                               text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return esito.stdout.strip() if esito.returncode == 0 and esito.stdout.strip() else None


def graph_status(dir_path: Path, root: Path = ROOT, head: str | None = None) -> dict:
    """Stato dichiarato della directory: conteggi, commit, freschezza, eta'.

    `head` si puo' passare per i test; se e' `None` si legge dal repository. Se
    nessuno dei due e' disponibile, `stale` resta `None`: non sapere non e'
    "fresco".
    """
    grafo = load_graph(dir_path)
    nodi = grafo.get("nodes") or []
    archi = grafo.get("links") or []
    costruito = str(grafo.get("built_at_commit") or "").strip() or None
    if head is None:
        head = head_commit(root)
    if costruito and head:
        stale: bool | None = not (head.startswith(costruito) or costruito.startswith(head))
    else:
        stale = None
    com = {n.get("community") for n in nodi if isinstance(n.get("community"), int)}
    segnaposto = sum(1 for n in nodi if _PLACEHOLDER.match(str(n.get("community_name") or "")))
    mtime = _mtime_iso(dir_path / "graph.json")
    eta_ore = None
    try:
        eta_ore = round((datetime.now(timezone.utc).timestamp()
                         - (dir_path / "graph.json").stat().st_mtime) / 3600, 1)
    except OSError:
        pass
    report = dir_path / "GRAPH_REPORT.md"
    html = dir_path / "graph.html"
    return {
        "dir": dir_path.name,
        "nodes": len(nodi),
        "edges": len(archi),
        "communities": len(com),
        "built_at_commit": costruito,
        "head": head,
        "stale": stale,
        "generated_at": mtime,
        "age_hours": eta_ore,
        "report": report.is_file(),
        "report_at": _mtime_iso(report),
        "html": html.is_file(),
        "html_at": _mtime_iso(html),
        "placeholder_nodes": segnaposto,
        "commands": {
            "update": "./scripts/graphify.sh update .",
            "cluster": "./scripts/graphify.sh cluster-only .",
            "html": "./scripts/graphify.sh export html",
            "service": ".venv/bin/python scripts/graphify_surface.py",
        },
    }


# ── La pagina ────────────────────────────────────────────────────────────────
# Un pagina sola, senza build: parla solo con le rotte qui sopra. La libreria
# del grafo (vis-network) arriva da CDN con hash SRI, come nel `graph.html` di
# graphify: il grafo resta locale, la libreria no.
_PAGE = r"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Grafo del repository — graphify</title>
<script src="https://unpkg.com/vis-network@9.1.6/standalone/umd/vis-network.min.js"
        integrity="sha384-Ux6phic9PEHJ38YtrijhkzyJ8yQlH8i/+buBR8s3mAZOJrP1gwyvAcIYl3GWtpX1"
        crossorigin="anonymous"></script>
<style>
:root{--bg:#0f0f1a;--surface:#171727;--surface2:#1e1e33;--border:#2a2a44;
--text:#e6e6f0;--muted:#9a9ab5;--faint:#6c6c88;--primary:#7c6cff;--ok:#3ecf8e;
--warn:#f5a623;--err:#ff5c5c;--mono:ui-monospace,SFMono-Regular,Menlo,monospace}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:13px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;height:100vh;display:flex;flex-direction:column}
header{display:flex;align-items:center;gap:10px;padding:8px 12px;background:var(--surface);border-bottom:1px solid var(--border);flex-wrap:wrap}
.brand{font-weight:600;display:flex;align-items:center;gap:8px}
.tag{font:10px var(--mono);text-transform:uppercase;color:var(--faint);border:1px solid var(--border);border-radius:99px;padding:1px 6px}
select,input,button{background:var(--surface2);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:4px 8px;font:12px inherit}
input,select{min-width:180px}
button{cursor:pointer}
button:hover{border-color:var(--primary)}
.spacer{flex:1}
.pill{font:10px var(--mono);border:1px solid var(--border);border-radius:99px;padding:2px 8px;color:var(--muted)}
.pill.ok{color:var(--ok);border-color:var(--ok)}
.pill.warn{color:var(--warn);border-color:var(--warn)}
.pill.err{color:var(--err);border-color:var(--err)}
#banner{padding:7px 12px;font-size:12px;border-bottom:1px solid var(--border);background:#221b0f;color:#f0d9a8;display:none}
#banner.ok{background:#0f221a;color:#b8efd4}
#banner code{font-family:var(--mono);background:#00000038;padding:1px 5px;border-radius:4px}
main{flex:1;display:grid;grid-template-columns:290px 1fr 300px;min-height:0}
aside{overflow:auto;border-right:1px solid var(--border);background:var(--surface);padding:8px}
#inspect{border-right:none;border-left:1px solid var(--border)}
.side-title{font:11px var(--mono);text-transform:uppercase;color:var(--faint);margin:2px 0 8px;display:flex;justify-content:space-between}
.com{display:flex;justify-content:space-between;gap:6px;padding:5px 7px;border:1px solid transparent;border-radius:6px;cursor:pointer}
.com:hover{background:var(--surface2)}
.com.sel{border-color:var(--primary);background:var(--surface2)}
.com .nm{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.com .sz{font:11px var(--mono);color:var(--faint)}
.com .der{color:var(--warn);font-size:10px;margin-left:4px}
.com .dir{color:var(--faint);font-size:10px;margin-left:4px}
.der{color:var(--warn);font-size:10px}
.hint{color:var(--muted);font-size:11px;margin-top:8px}
.row{display:flex;align-items:center}
#canvas{position:relative;min-width:0}
#net{position:absolute;inset:0}
#legend{position:absolute;left:10px;bottom:10px;font:11px var(--mono);color:var(--muted);background:#0b0b14cc;border:1px solid var(--border);border-radius:6px;padding:6px 8px;max-width:60%}
.kv{display:grid;grid-template-columns:88px 1fr;gap:2px 8px;font-size:12px;margin-bottom:10px}
.kv b{font-weight:600;color:var(--muted);font-size:11px;text-transform:uppercase}
.kv span{word-break:break-word}
.mono{font-family:var(--mono);font-size:11px}
.rel{font:11px var(--mono);padding:2px 0;border-bottom:1px solid var(--surface2);cursor:pointer}
.rel:hover{color:var(--primary)}
.empty{color:var(--faint);padding:12px;font-size:12px}
dialog{background:var(--surface);color:var(--text);border:1px solid var(--border);border-radius:10px;max-width:min(1000px,92vw);width:1000px;max-height:86vh}
dialog::backdrop{background:#000000aa}
dialog pre{white-space:pre-wrap;font:11px/1.5 var(--mono);overflow:auto;max-height:70vh;background:#0b0b14;border:1px solid var(--border);border-radius:8px;padding:10px}
footer{font:11px var(--mono);color:var(--faint);padding:4px 12px;border-top:1px solid var(--border);background:var(--surface);display:flex;gap:14px;flex-wrap:wrap}
</style>
</head>
<body>
<header>
  <div class="brand">&#128200; Grafo del repository <span class="tag">graphify</span></div>
  <select id="dirSel" title="Quale grafo"></select>
  <span class="pill" id="fresh">…</span>
  <span class="spacer"></span>
  <input id="q" placeholder="cerca community, file o simbolo…">
  <button id="btnOverview">Panoramica</button>
  <button id="btnReport">Report</button>
</header>
<div id="banner"></div>
<main>
  <aside id="side">
    <div class="side-title"><span>Community</span><span id="comCount"></span></div>
    <div id="comList"><div class="empty">Caricamento…</div></div>
  </aside>
  <section id="canvas">
    <div id="net"></div>
    <div id="legend"></div>
  </section>
  <aside id="inspect"><div class="empty">Clicca una community o un nodo per i dettagli.</div></aside>
</main>
<footer>
  <span id="foot">sola lettura &middot; loopback &middot; nessuna scrittura nel repository</span>
</footer>
<dialog id="dlg">
  <div class="row" style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
    <b style="font-size:13px">GRAPH_REPORT.md</b>
    <span class="spacer"></span>
    <button id="dlgClose">Chiudi</button>
  </div>
  <pre id="dlgBody">…</pre>
</dialog>
<script>
var G=null, ST=null, NET=null, SEL=null, DIR='';
var STYLE={bg:'#0f0f1a',border:'#2a2a44',text:'#e6e6f0',accent:'#7c6cff'};
function escH(v){return String(v==null?'':v).replace(/&/g,'&amp;').replace(/</g,'&lt;')
  .replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
async function j(url){
  var r=await fetch(url), d=await r.json().catch(function(){return {};});
  if(!r.ok)throw new Error(d.error||('HTTP '+r.status));
  return d;
}
function el(id){return document.getElementById(id);}

// ── avvio ────────────────────────────────────────────────────────────────────
async function boot(){
  var sel=el('dirSel'), gs;
  try{ gs=await j('/api/graphs'); }
  catch(e){ el('comList').innerHTML='<div class="empty">Superficie non raggiungibile: '+escH(e.message)+'</div>'; return; }
  if(!gs.graphs||!gs.graphs.length){
    el('comList').innerHTML='<div class="empty">Nessun grafo trovato in <code>'+escH(gs.root||'')+'</code>. Primo giro: <code>./scripts/graphify.sh</code></div>';
    return;
  }
  gs.graphs.forEach(function(g){
    var o=document.createElement('option');
    o.value=g.name;
    o.textContent=g.name+' — '+g.nodes+' nodi · '+g.communities+' community'+(g.stale===true?' · stantio':'');
    sel.appendChild(o);
  });
  sel.onchange=function(){openDir(sel.value);};
  await openDir(gs.graphs[0].name);
}

async function openDir(name){
  DIR=name;
  el('comList').innerHTML='<div class="empty">Caricamento…</div>';
  try{
    ST=await j('/api/status?dir='+encodeURIComponent(name));
    G=await j('/api/graph?dir='+encodeURIComponent(name));
  }catch(e){
    el('comList').innerHTML='<div class="empty">Grafo illeggibile in '+escH(name)+': '+escH(e.message)+'</div>';
    return;
  }
  renderFreshness();
  renderCommunities();
  drawOverview();
}

// ── freschezza e piede ───────────────────────────────────────────────────────
function renderFreshness(){
  var f=el('fresh'), b=el('banner');
  b.style.display='none';
  if(ST.stale===true){
    f.className='pill warn'; f.textContent='stantio';
    b.className=''; b.style.display='block';
    b.innerHTML='Questo grafo è del commit <code>'+escH(ST.built_at_commit||'?')+'</code>, ma HEAD è '
      +'<code>'+escH(ST.head||'?')+'</code>. Rigenera: <code>'+escH(ST.commands.update)+'</code> '
      +'(codice, offline, zero chiavi) e poi <code>'+escH(ST.commands.cluster)+'</code> per report e HTML.';
  }else if(ST.stale===false){
    f.className='pill ok'; f.textContent='allineato a HEAD';
  }else{
    f.className='pill'; f.textContent='freschezza ignota';
    b.className=''; b.style.display='block';
    b.innerHTML='Il grafo non dichiara il commit di partenza (o git non risponde): non posso dire se è stantio. '
      +'Rigenera con <code>'+escH(ST.commands.update)+'</code>.';
  }
  el('foot').textContent=G.nodes.length+' nodi · '+G.links.length+' archi · '
    +Object.keys(G.communities).length+' community · etichette derivate: '+G.names.derived+'/'+G.names.total
    +' · generato '+(ST.generated_at||'?')+' · report: '+(ST.report?'sì':'no');
}

// ── elenco community ────────────────────────────────────────────────────────
function renderCommunities(){
  var q=(el('q').value||'').toLowerCase();
  var ids=Object.keys(G.communities).map(function(k){return G.communities[k];})
    .sort(function(a,b){return b.size-a.size||String(a.name).localeCompare(String(b.name));});
  var vis=ids.filter(function(c){
    if(!q)return true;
    if(String(c.name).toLowerCase().indexOf(q)>=0)return true;
    if(String(c.hub_file).toLowerCase().indexOf(q)>=0)return true;
    return (c.files||[]).some(function(f){return String(f.file).toLowerCase().indexOf(q)>=0;});
  });
  el('comList').innerHTML=vis.map(function(c){
    var coda=c.derived
      ?'<span class="der" title="etichetta derivata localmente (nessun LLM)">· derivata</span>'
      :'<span class="dir" title="directory con più nodi di questa community">· '+escH(c.dir)+'</span>';
    return '<div class="com'+(SEL===c.id?' sel':'')+'" data-cid="'+c.id+'" title="'+escH(c.hub_file)+'">'
      +'<span class="nm">'+escH(c.name)+coda+'</span>'
      +'<span class="sz">'+c.size+'</span></div>';
  }).join('') || '<div class="empty">Nessuna community corrisponde alla ricerca.</div>';
  el('comCount').textContent=vis.length+'/'+ids.length;
  Array.prototype.forEach.call(document.querySelectorAll('#comList .com'),function(node){
    node.onclick=function(){drawCommunity(parseInt(node.getAttribute('data-cid'),10));};
  });
}

// ── disegno ─────────────────────────────────────────────────────────────────
function makeNet(data,options,onclick){
  if(NET)NET.destroy();
  NET=new vis.Network(el('net'),data,options);
  if(onclick)NET.on('click',onclick);
}
function baseOptions(){
  return {physics:{solver:'forceAtlas2Based',
      forceAtlas2Based:{gravitationalConstant:-60,springLength:120},
      stabilization:{iterations:200,fit:true}},
    nodes:{shape:'dot',font:{color:STYLE.text,size:12},borderWidth:1,
      color:{background:'#4c3fd8',border:'#7c6cff'}},
    edges:{color:{color:STYLE.border,highlight:STYLE.accent,hover:STYLE.accent},
      smooth:{type:'continuous'},width:0.5},
    interaction:{hover:true,tooltipDelay:120}};
}
function drawOverview(){
  SEL=null; renderCommunities();
  var byId={}, w={};
  G.nodes.forEach(function(n){byId[n.id]=n;});
  G.links.forEach(function(l){
    var a=byId[l.source], b=byId[l.target];
    if(!a||!b)return;
    var ca=a.community, cb=b.community;
    if(ca==null||cb==null||ca===cb)return;
    var k=(ca<cb?ca+'-'+cb:cb+'-'+ca);
    w[k]=(w[k]||0)+1;
  });
  var nodes=Object.keys(G.communities).map(function(k){
    var c=G.communities[k];
    return {id:'c'+k,label:c.name,value:Math.max(1,c.size),
      title:'<b>'+escH(c.name)+'</b><br>'+c.size+' nodi · directory '+escH(c.dir)
        +(c.derived?'<br><i>etichetta derivata (hub + directory)</i>':'')
        +'<br>'+(c.files||[]).map(function(f){return escH(f.file)+' ('+f.n+')';}).join('<br>')};
  });
  var edges=Object.keys(w).map(function(k){
    var p=k.split('-');
    return {from:'c'+p[0],to:'c'+p[1],value:w[k],title:w[k]+' archi fra le due community'};
  });
  var opt=baseOptions();
  opt.nodes.scaling={min:10,max:40};
  opt.nodes.color={background:'#2f2f5c',border:'#6f6fb0'};
  makeNet({nodes:new vis.DataSet(nodes),edges:new vis.DataSet(edges)},opt,function(p){
    if(p.nodes.length)drawCommunity(parseInt(String(p.nodes[0]).slice(1),10));
  });
  el('legend').innerHTML='<b>Panoramica</b> — 1 nodo = 1 community (dimensione = quanti nodi), '
    +'1 arco = collegamenti fra community. Clicca per aprirne una.';
}

function drawCommunity(cid){
  var c=G.communities[String(cid)];
  if(!c)return;
  SEL=cid; renderCommunities();
  var ids={}, nodes=[], edges=[];
  G.nodes.forEach(function(n){ if(n.community===cid)ids[n.id]=1; });
  G.nodes.forEach(function(n){
    if(!ids[n.id])return;
    var d=G.degree[n.id]||0;
    nodes.push({id:n.id,label:n.label,value:1+d/3,
      title:'<b>'+escH(n.label)+'</b><br>'+escH(n.source_file||'(senza file)')+':'
        +escH(n.source_location||'')+'<br>grado '+d});
  });
  G.links.forEach(function(l){
    if(ids[l.source]&&ids[l.target])
      edges.push({from:l.source,to:l.target,label:l.relation||'',
        title:escH(l.relation||'')+' '+escH(l.source_file||'')+':'+escH(l.source_location||'')});
  });
  var opt=baseOptions();
  opt.edges.font={color:'#8a8aa8',size:10,strokeWidth:0};
  makeNet({nodes:new vis.DataSet(nodes),edges:new vis.DataSet(edges)},opt,function(p){
    if(p.nodes.length)inspectNode(String(p.nodes[0]));
  });
  el('legend').innerHTML='<b>'+escH(c.name)+'</b> — '+c.size+' nodi, '+edges.length
    +' archi interni. Clicca un nodo per i dettagli, o <a href="#" id="back">torna alla panoramica</a>.';
  var back=el('back');
  if(back)back.onclick=function(ev){ev.preventDefault();drawOverview();};
  showCommunity(c);
}

// ── ispettore ───────────────────────────────────────────────────────────────
function kv(pairs){
  return '<div class="kv">'+pairs.map(function(p){
    return '<b>'+escH(p[0])+'</b><span>'+p[1]+'</span>';}).join('')+'</div>';
}
function fileLine(o){
  var f=o&&o.source_file?String(o.source_file):'(senza file)';
  return escH(f)+(o&&o.source_location?':'+escH(o.source_location):'');
}
function showCommunity(c){
  var files=(c.files||[]).map(function(f){return escH(f.file)+' <span class="sz">('+f.n+')</span>';}).join('<br>');
  el('inspect').innerHTML=kv([
    ['community','#'+c.id+' — '+escH(c.name)+(c.derived?' <span class="der">· derivata</span>':''),],
    ['nodi',String(c.size)],
    ['hub',escH(c.hub)+' <span class="mono">'+escH(c.hub_file)+'</span>'],
    ['file',files||'—'],
    ['etichetta',c.derived
      ? 'derivata localmente: hub + directory dominante. Per un nome semantico: <code>./scripts/graphify.sh cluster-only .</code> (LLM locale).'
      : 'dichiarata dal grafo (naming del modello).'],
  ])+'<div class="hint">Clicca un nodo nel disegno per i suoi collegamenti.</div>';
}
function inspectNode(id){
  var byId={}, nodo=null;
  G.nodes.forEach(function(n){byId[n.id]=n;if(n.id===id)nodo=n;});
  if(!nodo){el('inspect').innerHTML='<div class="empty">Nodo '+escH(id)+' non trovato.</div>';return;}
  var com=G.communities[String(nodo.community)]||{name:'?'};
  var rel=(G.neighbours[id]||[]);
  var out=rel.filter(function(r){return r.dir==='out';}), inn=rel.filter(function(r){return r.dir==='in';});
  function riga(r){
    var n2=byId[r.id]||{label:r.id};
    return '<div class="rel" data-jump="'+escH(r.id)+'">'+(r.dir==='out'?'&rarr;':'&larr;')
      +' '+escH(n2.label)+' <span style="color:var(--faint)">'+(r.relation?escH(r.relation)+' · ':'')
      +escH(n2.source_file||'')+'</span></div>';
  }
  el('inspect').innerHTML=kv([
    ['simbolo',escH(nodo.label||id)],
    ['tipo',escH(nodo.file_type||nodo.node_type||'?')+(nodo._callable?' <span class="sz">callable</span>':'')],
    ['file',fileLine(nodo)],
    ['community','#'+nodo.community+' — '+escH(com.name)],
    ['grado',String(G.degree[id]||0)+' collegamenti'],
    ['righe',String(nodo.source_location||'?')],
  ])
  +'<div class="side-title"><span>Chiama ('+out.length+')</span></div>'
  +(out.slice(0,80).map(riga).join('')||'<div class="empty">nessuno</div>')
  +'<div class="side-title" style="margin-top:10px"><span>Chiamato da ('+inn.length+')</span></div>'
  +(inn.slice(0,80).map(riga).join('')||'<div class="empty">nessuno</div>');
  Array.prototype.forEach.call(document.querySelectorAll('#inspect [data-jump]'),function(node){
    node.onclick=function(){
      var t=node.getAttribute('data-jump'), byCom={};
      G.nodes.forEach(function(n){if(n.id===t)byCom=n.community;});
      drawCommunity(byCom);
      if(NET)NET.selectNodes([t]); NET.focus(t,{scale:1.1,animation:true});
      inspectNode(t);
    };
  });
}

// ── report ──────────────────────────────────────────────────────────────────
async function showReport(){
  var pre=el('dlgBody');
  pre.textContent='Caricamento…';
  el('dlg').showModal();
  try{
    var r=await fetch('/api/report?dir='+encodeURIComponent(DIR));
    pre.textContent=r.ok?await r.text():(JSON.parse(await r.text()).error||('HTTP '+r.status));
  }catch(e){ pre.textContent='Report non raggiungibile: '+e.message; }
}

// ── agganci e avvio ─────────────────────────────────────────────────────────
el('q').oninput=function(){ if(G)renderCommunities(); };
el('btnOverview').onclick=function(){ if(G)drawOverview(); };
el('btnReport').onclick=showReport;
el('dlgClose').onclick=function(){ el('dlg').close(); };
boot();
</script>
</body>
</html>
"""


# ── L'app HTTP ───────────────────────────────────────────────────────────────

# Il `graph.json` intero e' ~11 MB e porta campi che la pagina non usa: qui si
# serve la stessa cosa senza gli extra, cosi' il browser scarica e interpreta un
# payload piu' piccolo (i campi tenuti sono quelli che la pagina legge).
_CAMPI_NODO = ("id", "label", "community", "community_name", "source_file",
               "source_location", "file_type", "_callable")
_CAMPI_ARCO = ("source", "target", "relation", "source_file", "source_location",
               "confidence")


def _nodo_slim(nodo: dict) -> dict:
    return {k: nodo[k] for k in _CAMPI_NODO if k in nodo}


def _arco_slim(arco: dict) -> dict:
    return {k: arco[k] for k in _CAMPI_ARCO if k in arco}


def build_app(root: Path = ROOT) -> Flask:
    """L'app della superficie: tutte le rotte sono di sola lettura."""
    app = Flask(__name__)

    def _scegli_dir():
        """La directory chiesta (`?dir=`), o la prima disponibile."""
        chiesto = request.args.get("dir") or request.args.get("d") or ""
        if not chiesto:
            disponibili = graph_dir_candidates(root)
            return disponibili[0] if disponibili else None
        return resolve_dir(chiesto, root)

    def _manca() -> tuple[Response, int]:
        return jsonify({
            "error": "nessuna directory del grafo",
            "detail": f"servono una {DIR_PREFIX}*/graph.json nella radice del repository",
            "root": str(root),
            "commands": {"primo_giro": "./scripts/graphify.sh"},
        }), 404

    @app.route("/health")
    def health():
        disponibili = graph_dir_candidates(root)
        return jsonify({"ok": True, "service": "graphify-surface", "read_only": True,
                        "graphs": [p.name for p in disponibili]})

    @app.route("/api/graphs")
    def api_graphs():
        fuori = []
        for p in graph_dir_candidates(root):
            try:
                st = graph_status(p, root)
            except (OSError, ValueError) as exc:
                fuori.append({"name": p.name, "error": str(exc)})
                continue
            fuori.append({"name": p.name, "nodes": st["nodes"], "edges": st["edges"],
                          "communities": st["communities"], "stale": st["stale"],
                          "built_at_commit": st["built_at_commit"], "generated_at": st["generated_at"]})
        return jsonify({"root": str(root), "graphs": fuori})

    @app.route("/api/status")
    def api_status():
        d = _scegli_dir()
        if d is None:
            return _manca()
        try:
            return jsonify(graph_status(d, root))
        except (OSError, ValueError) as exc:
            return jsonify({"error": "graph.json illeggibile", "detail": str(exc), "dir": d.name}), 500

    @app.route("/api/graph")
    def api_graph():
        d = _scegli_dir()
        if d is None:
            return _manca()
        try:
            grafo = load_graph(d)
            etichette = community_labels(grafo)
        except (OSError, ValueError) as exc:
            return jsonify({"error": "graph.json illeggibile", "detail": str(exc), "dir": d.name}), 500
        return jsonify({
            "dir": d.name,
            "nodes": [_nodo_slim(n) for n in (grafo.get("nodes") or [])],
            "links": [_arco_slim(a) for a in (grafo.get("links") or [])],
            "built_at_commit": grafo.get("built_at_commit"),
            "communities": etichette["communities"],
            "degree": etichette["degree"],
            "neighbours": etichette["neighbours"],
            "names": etichette["names"],
        })

    @app.route("/api/report")
    def api_report():
        d = _scegli_dir()
        if d is None:
            return _manca()
        percorso = d / "GRAPH_REPORT.md"
        if not percorso.is_file():
            return jsonify({"error": "GRAPH_REPORT.md assente in " + d.name,
                            "detail": "si genera con ./scripts/graphify.sh cluster-only ."}), 404
        return Response(percorso.read_text(encoding="utf-8", errors="replace"),
                        mimetype="text/plain; charset=utf-8")

    @app.route("/")
    def index():
        return Response(_PAGE, mimetype="text/html; charset=utf-8")

    return app


# ── L'avvio ──────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Superficie locale del grafo del repository (graphify)")
    parser.add_argument("--check", action="store_true",
                        help="verifica radice e grafi disponibili senza avviare il servizio")
    parser.add_argument("--host", default=HOST, help=f"interfaccia (default {HOST}: solo loopback)")
    parser.add_argument("--port", type=int, default=PORT, help=f"porta (default {PORT})")
    args = parser.parse_args(argv)

    disponibili = graph_dir_candidates(ROOT)
    if args.check:
        if not disponibili:
            print(f"nessun grafo: serve una {DIR_PREFIX}*/graph.json in {ROOT}", flush=True)
            return 1
        print("Superficie pronta: " + ", ".join(p.name for p in disponibili), flush=True)
        return 0
    if not disponibili:
        print(f"nessun grafo in {ROOT}: lancia prima ./scripts/graphify.sh", flush=True)
        return 1
    if args.host != HOST:
        print(f"avviso: questa superficie e' pensata per loopback; host={args.host}", flush=True)
    print(f"Grafo del repository: http://{args.host}:{args.port} "
          f"({', '.join(p.name for p in disponibili)})", flush=True)
    build_app(ROOT).run(host=args.host, port=args.port, debug=False, threaded=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
