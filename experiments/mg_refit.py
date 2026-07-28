"""HERLETTEREN op het gecorrigeerde bord: zelfde geometrie en zetvolgorde, maar de letters
zijn destijds geoptimaliseerd tegen een bord dat 7 letterpremies miste. Dit script lost het
footprint-model opnieuw op (CP-SAT + blanco's + zak), geverifieerd door score_game.

Env: RFBASE (spel-json), TLIM (seconden), RFOUT (json-uitvoer).
"""
import sys, os, json
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
import maxgame_score as MG

src = open('/home/bob/programming/scrabble4/experiments/mg_ladder.py').read()
head = src.split("fin_idx = set(")[0]
head = head.replace("os.environ.get('LDBASE'", "os.environ.get('RFBASE'")
head = head.replace("sol.parameters.num_workers = 8", "sol.parameters.num_workers = int(os.environ.get('NW','8'))")
g = {}
exec(compile(head, 'refit_head', 'exec'), g)

TLIM = float(os.environ.get('TLIM', '900'))
D = g['D']; moves = g['moves_init']
st, ob, grid2, blset = g['solve_mv'](moves, TLIM)
print("solver:", st, ob, flush=True)
if st == 'ok':
    tot, per, ok, msg = MG.score_game([row[:] for row in grid2], moves, blset)
    base = int(D.get('total', 0))
    print(f"arbiter {int(tot)} (ok={ok}) | basis {base} | winst {int(tot)-base}", flush=True)
    if ok and int(tot) > base:
        out = os.environ.get('RFOUT', '/tmp/claude-1000/-home-bob-programming-scrabble4/da7ed622-7493-428d-96da-a3b3144f633e/scratchpad/refit_best.json')
        json.dump({'grid': grid2, 'moves': [[list(c) for c in m] for m in moves],
                   'blanks': [list(b) for b in sorted(blset)], 'total': int(tot),
                   'triple': D['triple'], 'plan': 'herlettering op gecorrigeerd bord'},
                  open(out, 'w'))
        print("NIEUW BEST", int(tot), "->", out, flush=True)
