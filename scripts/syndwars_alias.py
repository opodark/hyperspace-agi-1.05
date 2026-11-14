#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Trova gli alias nascosti tra simboli di dati che Ghidra ha separato.

Nel binario originale un array e le celle che seguono sono un'unica zona di memoria. Ghidra spesso
da' un nome all'inizio dell'array (`heap`, `veh_ma_heap`) e uno diverso a una cella interna
(`data_1c30c0` = heap[1]). In C diventano due `extern` distinti: a -O1/-O2 il compilatore deduce che
scrivere `heap[i]` non cambia `data_1c30c0` e riordina o elimina letture. A -O0 tutto funziona.

Il rilevatore legge le etichette di dati dei file .sx (indirizzo e dimensione fino all'etichetta
successiva) e segnala le coppie A, B dove:
  - A e' usata in C con un indice variabile (A[i], ((T *)&A)[i], &A + i),
  - la zona propria di A nel .sx e' di una sola cella (<= --cell byte, default 8),
  - B e' usata in C e cade dopo A entro la distanza indicata (default 0x1000 byte).
Uso: syndwars_alias.py <repo syndwars-remake> [--span 0x1000] [--define]
Con --define stampa le #define proposte quando B e' allineata a un elemento di A a 4 byte.
"""
import argparse, os, re, glob

LABEL = re.compile(r'^(?:GLOBAL\s*\((\w+)\)|(\w+):)\s*(?:/\*\s*0x([0-9A-Fa-f]+)\s*\*/)?')
SIZE = {'.long': 4, '.int': 4, '.short': 2, '.word': 2, '.byte': 1}


def directive_size(line):
    s = line.strip()
    if not s or s.startswith(('/*', '#', '//')):
        return 0
    parts = s.split(None, 1)
    d = parts[0]
    if d in SIZE:
        return SIZE[d] * (parts[1].count(',') + 1 if len(parts) > 1 else 1)
    if d == '.fill':
        args = [a.strip() for a in parts[1].split(',')]
        n = int(args[0], 0)
        unit = int(args[1], 0) if len(args) > 1 else 1
        return n * unit
    if d in ('.string', '.asciz'):
        return len(bytes(parts[1].strip()[1:-1], 'utf-8').decode('unicode_escape')) + 1
    if d == '.ascii':
        return len(bytes(parts[1].strip()[1:-1], 'utf-8').decode('unicode_escape'))
    return None  # istruzione o direttiva sconosciuta: si perde la posizione


def data_labels(path):
    """Etichette con indirizzo: quelle senza commento ricevono l'indirizzo dalla somma delle dimensioni."""
    out = []
    addr = None
    for line in open(path, errors='replace'):
        m = LABEL.match(line)
        if m:
            name = m.group(1) or m.group(2)
            if m.group(3):
                addr = int(m.group(3), 16)
            if addr is not None and not name.startswith(('jump_', 'ASM_')):
                out.append((addr, name))
            continue
        if addr is None:
            continue
        s = line.strip()
        if s.startswith('.align'):
            a = int(s.split()[1], 0)
            addr = (addr + a - 1) // a * a
            continue
        n = directive_size(line)
        if n is None:
            addr = None
        else:
            addr += n
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('repo')
    ap.add_argument('--span', type=lambda x: int(x, 0), default=0x1000)
    ap.add_argument('--define', action='store_true')
    ap.add_argument('--cell', type=lambda x: int(x, 0), default=8,
                    help='zona propria massima di A: oltre e\' un array vero, non una cella spezzata')
    a = ap.parse_args()
    labels = {}
    for sx in glob.glob(os.path.join(a.repo, 'src', '*.sx')):
        for addr, name in data_labels(sx):
            labels.setdefault(name, addr)
    # zona propria di ogni etichetta: fino all'etichetta successiva, usata o no
    order = sorted(set(labels.values()))
    nxt = {x: y for x, y in zip(order, order[1:])}
    csrc = {}
    for c in glob.glob(os.path.join(a.repo, 'src', '*.c')):
        csrc[os.path.basename(c)] = open(c, errors='replace').read()
    allc = '\n'.join(csrc.values())
    used = {n for n in labels if re.search(r'\b%s\b' % re.escape(n), allc)}
    by_addr = sorted((labels[n], n) for n in used)
    found = 0
    for i, (aa, an) in enumerate(by_addr):
        e = re.escape(an)
        var_idx = re.compile(r'\b%s\s*\[\s*(?!0x[0-9a-fA-F]+\s*\]|\d+\s*\])' % e
                             + r'|\(\s*\(\s*\w+\s*\*\s*\)\s*&\s*%s\s*\)\s*\[\s*(?!0x[0-9a-fA-F]+\s*\]|\d+\s*\])' % e
                             + r'|&\s*%s\s*\)?\s*\+' % e)
        files = [f for f, s in csrc.items() if var_idx.search(s)]
        if not files or aa not in nxt or nxt[aa] - aa > a.cell:
            continue
        for ba, bn in by_addr[i + 1:]:
            if ba - aa > a.span:
                break
            if ba == aa:
                continue
            bfiles = [f for f, s in csrc.items() if re.search(r'\b%s\b' % re.escape(bn), s)]
            common = sorted(set(files) & set(bfiles))
            found += 1
            off = ba - aa
            tag = 'STESSO FILE ' + ','.join(common) if common else 'file diversi'
            print('%-28s 0x%06X  +0x%-5X %-28s %s' % (an, aa, off, bn, tag))
            if a.define and off % 4 == 0:
                print('    #define %s (%s[%d])   /* se %s e\' un array di int */' % (bn, an, off // 4, an))
    print('coppie sospette: %d' % found)


if __name__ == '__main__':
    main()
