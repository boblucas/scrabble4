"""Vul de top-N woordbare schema's uit mg_schedsearch.py met echte letters (footprint-CP-SAT),
arbiter-geverifieerd, en bewaar de beste. Env: SFIN (json met schema's), SFBASE (spel-json voor
grid/blanks), TLIM (per schema), SFOUT, NTRY."""
import sys, os, json
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
import maxgame_score as MG

src = open('/home/bob/programming/scrabble4/experiments/mg_ladder.py').read()
head = src.split("fin_idx = set(")[0].replace("os.environ.get('LDBASE'", "os.environ.get('SFBASE'")
G = {}
exec(compile(head, 'fit_head', 'exec'), G)
solve_mv = G['solve_mv']; D = G['D']

SCH = json.load(open(os.environ.get('SFIN', '/tmp/claude-1000/-home-bob-programming-scrabble4/da7ed622-7493-428d-96da-a3b3144f633e/scratchpad/sched_top.json')))
TLIM = float(os.environ.get('TLIM', '400'))
NTRY = int(os.environ.get('NTRY', '3'))
base = int(D.get('total', 0))
print(f"basis {base}; {len(SCH)} schema's, ik probeer er {NTRY}", flush=True)

best = (base, None)
seen = set()
for k, item in enumerate(SCH):
    if k >= NTRY: break
    mv = [[tuple(c) for c in m] for m in item['moves']]
    key = tuple(tuple(sorted(m)) for m in mv)
    if key in seen: continue
    seen.add(key)
    st, ob, grid2, blset = solve_mv(mv, TLIM)
    if st != 'ok':
        print(f"schema {k} (plafond {item['ceiling']}): {st}", flush=True); continue
    tot, per, ok, msg = MG.score_game([row[:] for row in grid2], mv, blset)
    print(f"schema {k} (plafond {item['ceiling']}): model {ob} | arbiter {int(tot)} ok={ok} "
          f"{msg[:50] if not ok else ''}", flush=True)
    if ok and int(tot) > best[0]:
        best = (int(tot), k)
        json.dump({'grid': grid2, 'moves': [[list(c) for c in m] for m in mv],
                   'blanks': [list(b) for b in sorted(blset)], 'total': int(tot),
                   'triple': D['triple'], 'plan': f'woordbaar schema #{k} (plafond {item["ceiling"]})'},
                  open(os.environ.get('SFOUT', '/tmp/claude-1000/-home-bob-programming-scrabble4/da7ed622-7493-428d-96da-a3b3144f633e/scratchpad/schedfit_best.json'), 'w'))
        print("NIEUW BEST", int(tot), flush=True)
print("BEST:", best, flush=True)
