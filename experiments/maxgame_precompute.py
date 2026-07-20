"""Precompute per 15-woord: beste x27-completie, beste x9-completie (col7 verboden), beste opening,
letter-multiset. Dump TSV voor de Rust-triple-kernel. Alleen woorden met s27>0 of s9>0."""
import sys, os
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, 'experiments')
os.environ['N15_LANG'] = 'dutch2026'
from itertools import combinations
import maxgame_score as MG
r = MG.r; cba = r.alphabet.cba
val = {ch: r.scores[cba[ch]] for ch in 'abcdefghijklmnopqrstuvwxyz'}
lk = r.words_lookup
w15 = sorted({w for w in r.words_str if len(w) == 15})
DLS = (3, 11)
ALPH = 'abcdefghijklmnopqrstuvwxyz'

def prl(w, maskset):
    pre = [c for c in range(15) if c not in maskset]; i = 0
    while i < len(pre):
        j = i
        while j+1 < len(pre) and pre[j+1] == pre[j]+1: j += 1
        if j > i and tuple(cba[c] for c in w[pre[i]:pre[j]+1]) not in lk: return False
        i = j+1
    return True

# masker-lijsten eenmalig (indices van 4 resp 5 extra cols)
M27 = [set((0, 7, 14)) | set(e) for e in combinations([c for c in range(15) if c not in (0, 7, 14)], 4)]
M9 = [set((0, 14)) | set(e) for e in combinations([c for c in range(15) if c not in (0, 14, 7)], 5)]

def best27(w):
    base = sum(val[c] for c in w); best = -1
    for m in M27:
        if not prl(w, m): continue
        sc = 27*(base + sum(val[w[c]] for c in DLS if c in m)) + 50
        if sc > best: best = sc
    return best

def best9(w):
    base = sum(val[c] for c in w); best = -1
    for m in M9:
        if not prl(w, m): continue
        sc = 9*(base + sum(val[w[c]] for c in DLS if c in m)) + 50
        if sc > best: best = sc
    return best

def isw2(s): return tuple(cba[c] for c in s) in lk
AFTER_OK = {ch for ch in ALPH if any(isw2(ch+x) for x in ALPH)}
BEFORE_OK = {ch for ch in ALPH if any(isw2(x+ch) for x in ALPH)}

def runs_of(w, maskset):
    pre = [c for c in range(15) if c not in maskset]; out = []; i = 0
    while i < len(pre):
        j = i
        while j+1 < len(pre) and pre[j+1] == pre[j]+1: j += 1
        out.append([pre[k] for k in range(i, j+1)]); i = j+1
    return out
def best27_role(w, ok_set):
    """beste muur-veilige x27: elke LOSSE pre-run-cel moet connector-veilig (letter in ok_set);
    woord-runs (len>=2) OK (prl gecheckt)."""
    base = sum(val[c] for c in w); best = -1
    for m in M27:
        if not prl(w, m): continue
        runs = runs_of(w, m)
        safe = all(len(rr) >= 2 or w[rr[0]] in ok_set for rr in runs)
        if not safe: continue
        sc = 27*(base + sum(val[w[c]] for c in DLS if c in m)) + 50
        if sc > best: best = sc
    return best

def bestopen(w):
    best = -1
    for x0 in range(1, 8):
        x1 = x0+6
        s = sum(val[w[c]] for c in range(x0, x1+1)) + sum(val[w[c]] for c in DLS if x0 <= c <= x1)
        sc = 2*s+50
        if sc > best: best = sc
    return best

out = open('experiments/results/maxgame_words.tsv', 'w')
out.write("word\ts27\ts9\topen\tv27r0\tv27r14\t" + "\t".join(ALPH) + "\n")
n = 0
from collections import Counter
for idx, w in enumerate(w15):
    if idx % 10000 == 0: print(f"  {idx}/{len(w15)} ({n} qualifiers)", flush=True)
    s27 = best27(w); s9 = best9(w)
    if s27 <= 0 and s9 <= 0: continue
    op = bestopen(w) if s9 > 0 else 0
    v0 = best27_role(w, AFTER_OK) if s27 > 0 else 0
    v14 = best27_role(w, BEFORE_OK) if s27 > 0 else 0
    cc = Counter(w)
    out.write(f"{w}\t{s27}\t{s9}\t{op}\t{v0}\t{v14}\t" + "\t".join(str(cc.get(ch, 0)) for ch in ALPH) + "\n")
    n += 1
out.close()
print(f"KLAAR: {n} qualifiers -> maxgame_words.tsv", flush=True)
