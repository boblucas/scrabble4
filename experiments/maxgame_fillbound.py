"""maxfill(skelet)-UB: per lijn max pasbare woordscore (patroon+restzak) x stage-knapsack.
Sound: elke vul/mop-up-stage is een woord op één lijn passend op het skelet-patroon (extra
vulcellen als jokers uit de restzak); stages(lijn) <= vulcellen(lijn); Σ vulcellen <= 15;
Σ stages <= 2x15 (elke vulzet: 1 hoofd + <=n kruisen; #zetten <= #tegels).
Slotzet-kruisboost zit erin: kolom-woorden door maskercellen krijgen WM(maskcel) mee."""
import sys, os, json
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, 'experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
from collections import Counter
import maxgame_score as MG
r = MG.r; cba = r.alphabet.cba
val = {ch: r.scores[cba[ch]] for ch in 'abcdefghijklmnopqrstuvwxyz'}
LM = r.letter_multiplier; WM = r.word_multiplier
BB = os.environ.get('MGBACKBONE')
if BB:
    w0, w7, w14 = BB.split(',')
    G = [[0]*15 for _ in range(15)]
    for c in range(15):
        G[0][c] = cba[w0[c]]; G[7][c] = cba[w7[c]]; G[14][c] = cba[w14[c]]
    bl = set()
    skelcells = {(c, y) for c in range(15) for y in (0, 7, 14)}
else:
    d = json.load(open('experiments/results/maxgame_BEST.json'))
    G = d['grid']; bl = {tuple(b) for b in d['blanks']}
    moves = [[tuple(c) for c in mv] for mv in d['moves']]
    finals = [i for i, mv in enumerate(moves) if len(mv) == 7 and len({c[1] for c in mv}) == 1
              and mv[0][1] in (0, 7, 14) and i >= 15]
    skelcells = {c for i in list(range(15))+finals for c in moves[i]}
bag0 = Counter({chr(96+c): r.counts[c] for c in r.counts})
used = Counter()
for (x, y) in skelcells:
    if (x, y) not in bl: used[chr(96+G[y][x])] += 1
rest = Counter(bag0); rest.subtract(used)
rest = Counter({k: v for k, v in rest.items() if v > 0})
NREST = sum(rest.values()) - 1   # reserve
print(f"skeletcellen: {len(skelcells)}; restzak: {dict(sorted(rest.items()))} -> {NREST} legbaar")

def linecaps(cells):
    """cells: [(x,y)] langs de lijn.  Voor n=1..7: max woordscore met precies n vulcellen."""
    fixed = [chr(96+G[cy][cx]) if (cx, cy) in skelcells else None for (cx, cy) in cells]
    caps = {}
    for w in r.words_str:
        Lw = len(w)
        if Lw < 2 or Lw > 15: continue
        for st in range(0, 16-Lw):
            # randen: buiten woord geen vaste cel direct ervoor/erna (anders langere run)
            if st > 0 and fixed[st-1] is not None: continue
            if st+Lw < 15 and fixed[st+Lw] is not None: continue
            need = Counter(); okp = True
            s = 0; wm = 1; n = 0
            for i in range(Lw):
                f = fixed[st+i]
                if f is not None:
                    if f != w[i]: okp = False; break
                    s += val[w[i]]
                else:
                    (cx, cy) = cells[st+i]
                    lm = int(LM[cy][cx]); s += val[w[i]]*lm
                    wm *= int(WM[cy][cx]); need[w[i]] += 1; n += 1
            if not okp or n == 0 or n > 7: continue
            if any(need[c] > rest[c] for c in need): continue
            sc = s*wm + (50 if n == 7 else 0)
            if sc > caps.get(n, 0): caps[n] = sc
    return caps

lines = [[(x, y) for x in range(15)] for y in range(15)] + \
        [[(x, y) for y in range(15)] for x in range(15)]
allcaps = [linecaps(c) for c in lines]
top = sorted((max(c.values()) for c in allcaps if c), reverse=True)
print("top lijn-caps:", top[:8])
# per lijn: g(m) = max som stage-caps met totaal m vulcellen (herhaling toegestaan)
def gline(caps, mmax):
    g = [0]*(mmax+1)
    for m in range(1, mmax+1):
        for n, sc in caps.items():
            if n <= m and g[m-n]+sc > g[m]: g[m] = g[m-n]+sc
    return g
def dpdir(caps_list, budget):
    dp = [0]*(budget+1)
    for li, caps in caps_list:
        if not caps: continue
        empty = sum(1 for (cx, cy) in lines[li] if (cx, cy) not in skelcells)
        g = gline(caps, min(budget, empty))
        nd = dp[:]
        for m in range(1, len(g)):
            if g[m] == 0: continue
            for b in range(budget, m-1, -1):
                if dp[b-m]+g[m] > nd[b]: nd[b] = dp[b-m]+g[m]
        dp = nd
    return max(dp)
rowsc = [(i, allcaps[i]) for i in range(15)]
colsc = [(i, allcaps[i]) for i in range(15, 30)]
Ur = dpdir(rowsc, NREST); Uc = dpdir(colsc, NREST)
U_fill = Ur + Uc
print(f"\nmaxfill-UB v2 (rijen {Ur} + kolommen {Uc}, elk <= {NREST} cellen) = {U_fill}")
print(f"klasse-bracket: [3930, {3728 + U_fill}]")
