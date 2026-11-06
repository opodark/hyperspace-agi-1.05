import sys, collections, json
def load(f):
    d = {}
    for l in open(f):
        if l.startswith('#'):
            if 'ATTENZIONE' in l or 'fallito' in l: print('!!', l.strip())
            continue
        p = l.rstrip('\n').split('\t')
        if len(p) == 6: d[(p[0], int(p[1]) if p[1] != '-' else -1)] = tuple(p[2:])
    return d
a, b = load(sys.argv[1]), load(sys.argv[2])
cnt = collections.Counter((v[2], v[3]) for v in a.values() if v[0] == 'ok')
base = cnt.most_common(1)[0][0]
print('stato di riferimento (nessun effetto):', base, '| chiamate', len(a), len(b))
funcs = sorted({k[0] for k in a} | {k[0] for k in b})
res = collections.defaultdict(list)
for f in funcs:
    for t in range(4):
        x, y = a.get((f, t)), b.get((f, t))
        if x is None or y is None: res[f].append('manca'); continue
        if x[0].startswith('ERR') and y[0].startswith('ERR'): res[f].append('crash_entrambi'); continue
        if x[0] == 'SENZA_SIMBOLO' or y[0] == 'SENZA_SIMBOLO': res[f].append('senza_simbolo'); continue
        if x == y:
            res[f].append('uguale_effetto' if (x[2], x[3]) != base or x[1] not in ('void', '0') else 'uguale_nullo')
        else: res[f].append('DIVERSO')
tot = collections.Counter()
rows = []
for f, v in res.items():
    if 'DIVERSO' in v: cls = 'DIVERSO'
    elif 'uguale_effetto' in v: cls = 'uguale_con_effetto'
    elif 'uguale_nullo' in v: cls = 'uguale_solo_nullo'
    elif set(v) == {'crash_entrambi'}: cls = 'crash_sempre'
    else: cls = ','.join(sorted(set(v)))
    tot[cls] += 1; rows.append((cls, f, v))
for c, n in tot.most_common(): print(f'{c:22s} {n}')
for cls, f, v in sorted(rows):
    if cls == 'DIVERSO':
        print('  DIVERSO', f, v)
        for t in range(4):
            x, y = a.get((f, t)), b.get((f, t))
            if x != y: print('     t%d orig=%s bozza=%s' % (t, x, y))
json.dump({f: c for c, f, v in rows}, open(sys.argv[3], 'w'), indent=1)
