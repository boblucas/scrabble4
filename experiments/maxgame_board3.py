"""MAXGAME board v3 (LATTICE): rijen 0/7/14 = ankers VAST; kolommen 6/9/13 = volle verticalen
UIT KANDIDATENLIJST (allowed-assignments; matcht anker-letters op rij 0/7/14); elke overige
pre-placed ankercel krijgt een verticale buur; center-kolomcel (7,7) idem.  Zak + <=2 blanks.
Minimaliseer tegels (geen zwerf-actieven) -> connectiviteit structureel via het rooster.
LB daarna: 1724+536+1616 (ankerbeurten) + face(setup) + 50*floor(setup/7).
"""
import sys, os, json, time
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
from collections import Counter
from ortools.sat.python import cp_model
from scrabble import construct_rules
from solve import create_board, limit_letter_count
from dawg import position_independent_row_automaton

LANG = os.environ.get('N15_LANG', 'dutch2026'); HMAX = 15
r = construct_rules(LANG, '15'); W = H = 15; cba = r.alphabet.cba
R0, R7, R14 = 'geschenkcheques', 'polymyalgietjes', 'bouwcuratrixjes'
M0 = (0,3,7,8,11,12,14); M7 = (0,1,2,3,11,12,14); M14 = (0,1,3,5,7,11,14)
FULLCOLS = [6, 9, 13]
CAP = float(os.environ.get('MG_CAP', '1800'))

t0 = time.time()
# kandidaten voor volle kolommen
words15 = [w for w in r.words_str if len(w) == 15]
colcands = {}
for c in FULLCOLS:
    colcands[c] = [w for w in words15 if w[0]==R0[c] and w[7]==R7[c] and w[14]==R14[c]]
    print(f"# kol {c}: {len(colcands[c])} kandidaten", flush=True)
aut = position_independent_row_automaton([w for w in r.words if 1 <= len(w) <= HMAX])
print(f"# automaton {time.time()-t0:.0f}s", flush=True)
m = cp_model.CpModel(); m.prefix = 'g'
cells = create_board(m, [aut]*H, [aut]*W, alphabet_size=len(r.abc))
for (row, word) in ((0, R0), (7, R7), (14, R14)):
    for x in range(W):
        m.add(cells[(x, row)].letter[cba[word[x]]] == 1)
# volle kolommen: elk 1 kandidaat-woord (allowed assignments over letter_int per rij)
for c in FULLCOLS:
    sel = [m.new_bool_var(f'c{c}_{i}') for i in range(len(colcands[c]))]
    m.add(sum(sel) == 1)
    for y in range(H):
        m.add(cells[(c, y)].active == 1)
    for i, w in enumerate(colcands[c]):
        for y in range(H):
            m.add(cells[(c, y)].letter[cba[w[y]]] == 1).only_enforce_if(sel[i])
# resterende pre-placed cellen: verticale buur
pre = {0: [c for c in range(15) if c not in M0], 7: [c for c in range(15) if c not in M7],
       14: [c for c in range(15) if c not in M14]}
for c in pre[0]:
    if c not in FULLCOLS: m.add(cells[(c, 1)].active == 1)
for c in pre[14]:
    if c not in FULLCOLS: m.add(cells[(c, 13)].active == 1)
for c in pre[7]:
    if c not in FULLCOLS: m.add(cells[(c, 6)].active + cells[(c, 8)].active >= 1)
# zak
avail = Counter({c: r.counts[c] for c in r.counts})
limit_letter_count(m, cells, avail)
m.add(sum(cell.blank for cell in cells.values()) <= r.blank_count)
m.minimize(sum(cell.active for cell in cells.values()))
s = cp_model.CpSolver(); s.parameters.num_search_workers = int(os.environ.get('CPSAT_WORKERS','12'))
s.parameters.max_time_in_seconds = CAP
print(f"# solve (mintiles) cap={CAP}s ...", flush=True)
st = s.Solve(m)
name = {cp_model.OPTIMAL:'OPTIMAL',cp_model.FEASIBLE:'FEASIBLE',cp_model.INFEASIBLE:'INFEASIBLE'}.get(st,'UNKNOWN')
print(f"# status={name} tijd={time.time()-t0:.0f}s", flush=True)
if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
    grid = [[int(s.value(cells[(x,y)].letter_int)) for x in range(W)] for y in range(H)]
    nt = sum(1 for y in range(H) for x in range(W) if grid[y][x])
    print(f"# tegels: {nt}", flush=True)
    for y in range(H):
        print('  ' + ' '.join(chr(96+grid[y][x]) if grid[y][x] else '.' for x in range(W)))
    json.dump({'grid': grid}, open('experiments/results/maxgame_board3.json','w'))
    # LB
    val = {i: r.scores[i] for i in range(1,27)}
    finalcells = {(c,0) for c in M0} | {(c,7) for c in M7} | {(c,14) for c in M14}
    # blanks uit oplossing
    nblank = sum(1 for y in range(H) for x in range(W) if grid[y][x] and s.value(cells[(x,y)].blank))
    setup_face = sum(val[grid[y][x]] for y in range(H) for x in range(W)
                     if grid[y][x] and (x,y) not in finalcells and not s.value(cells[(x,y)].blank))
    nsetup = nt - 21
    lb = 1724 + 536 + 1616 + setup_face + 50 * (nsetup // 7)
    print(f"# setup-tegels {nsetup} face {setup_face} blanks {nblank}")
    print(f"# SPEL-LB >= 3876 + {setup_face} + {50*(nsetup//7)} = {lb}", flush=True)
