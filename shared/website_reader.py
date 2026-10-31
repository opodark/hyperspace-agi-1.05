# SPDX-License-Identifier: Apache-2.0
"""
Modulo per la lettura approfondita di interi siti web (Crawler / Deep Site Reader).

Consente all'agente di scansionare un intero sito web (home page + pagine interne
chiave come chi-siamo, servizi, prodotti, listini, contatti) ed estrarre il
contenuto pulito in formato Markdown.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlparse
import requests

logger = logging.getLogger("website_reader")

_PRIORITY_KEYWORDS = [
    "chi-siamo", "about", "azienda", "servizi", "services", "prodotti", "products",
    "listino", "prezzi", "pricing", "tariffe", "catalogo", "catalog", "contatti", "contact"
]


def _clean_html_text(html: str) -> str:
    """Estrae testo pulito dall'HTML rimuovendo script, stili e boilerplate."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
    except Exception:
        # Fallback regex semplice se bs4 fallisce
        text = re.sub(r"<(script|style).*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)

    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    cleaned = "\n".join(chunk for chunk in chunks if chunk)
    return cleaned[:4000]


def fetch_page_markdown(url: str, timeout: int = 10) -> str:
    """Scarica una pagina web e la restituisce in testo Markdown pulito."""
    # 1. Prova tramite Jina Reader (restituisce markdown perfetto a costo zero)
    jina_url = f"https://r.jina.ai/{url}"
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; HyperSpaceAGI/1.05)"}
        resp = requests.get(jina_url, headers=headers, timeout=timeout)
        if resp.status_code == 200 and len(resp.text.strip()) > 100:
            return resp.text.strip()[:4000]
    except Exception:
        pass

    # 2. Fallback diretto con estrazione locale
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; HyperSpaceAGI/1.05)"}
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            return _clean_html_text(resp.text)
    except Exception as exc:
        logger.warning("Errore fetch diretto su %s: %s", url, exc)

    return ""


def crawl_entire_website(start_url: str, max_pages: int = 5, timeout: int = 10) -> dict:
    """Scansiona la home page e le pagine interne principali di un sito web."""
    if not start_url.startswith(("http://", "https://")):
        start_url = f"https://{start_url}"

    parsed_root = urlparse(start_url)
    root_domain = parsed_root.netloc.lower().replace("www.", "")
    if not root_domain:
        return {"ok": False, "error": "URL non valido"}

    headers = {"User-Agent": "Mozilla/5.0 (compatible; HyperSpaceAGI/1.05)"}

    # 1. Scarica la homepage per raccogliere i link interni
    try:
        resp = requests.get(start_url, headers=headers, timeout=timeout)
        if resp.status_code >= 400:
            return {"ok": False, "error": f"HTTP {resp.status_code} su {start_url}"}
        homepage_html = resp.text
    except Exception as exc:
        return {"ok": False, "error": f"Impossibile connettersi a {start_url}: {exc}"}

    # Estrazione link interni
    links: set[str] = set()
    for match in re.finditer(r'href=["\']([^"\']+)["\']', homepage_html, re.IGNORECASE):
        href = match.group(1).split("#")[0].strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        full_url = urljoin(start_url, href)
        parsed_link = urlparse(full_url)
        # Solo pagine dello stesso dominio (con o senza www)
        link_domain = parsed_link.netloc.lower().replace("www.", "")
        if link_domain == root_domain:
            # Escludi file binari o immagini
            path_lower = parsed_link.path.lower()
            if not any(path_lower.endswith(ext) for ext in (".jpg", ".png", ".pdf", ".zip", ".gif", ".webp", ".svg")):
                clean_full = f"{parsed_link.scheme}://{parsed_link.netloc}{parsed_link.path}"
                if clean_full != start_url:
                    links.add(clean_full)

    # Ordina i link prioritizzando quelli con parole chiave rilevanti
    def link_priority(link: str) -> int:
        l_lower = link.lower()
        for idx, kw in enumerate(_PRIORITY_KEYWORDS):
            if kw in l_lower:
                return idx
        return 999

    sorted_links = sorted(list(links), key=link_priority)
    pages_to_crawl = [start_url] + sorted_links[:max_pages - 1]

    crawled_pages = []
    for page_url in pages_to_crawl:
        text_content = fetch_page_markdown(page_url, timeout=timeout)
        if text_content:
            crawled_pages.append({
                "url": page_url,
                "content": text_content
            })

    # Compone il digest riepilogativo per l'agente
    summary_sections = [f"# Analisi del Sito Web: {start_url}\nPagine scansionate: {len(crawled_pages)}\n"]
    for idx, p in enumerate(crawled_pages, 1):
        summary_sections.append(f"## {idx}. URL: {p['url']}\n{p['content']}\n")

    return {
        "ok": True,
        "site": start_url,
        "pages_crawled": len(crawled_pages),
        "digest": "\n---\n".join(summary_sections)
    }
