"""Witness elke MAX-board uit een ladder-trede; exit 0 als een geverifieerd bord > LB bestaat
(NEW LB, opgeslagen), anders exit 1.  Argv: mask_csv shard_dir lb."""
import sys, os, json, glob
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', os.environ.get('N15_LANG', 'dutch2026'))
os.environ.setdefault('N15_HMAX', '15')
import n15_twolevel as T
from n15_varmax_certify import reconstruct_board

WORD = sys.argv[4] if len(sys.argv) > 4 else 'geschenkcheques'
mask = tuple(int(x) for x in sys.argv[1].split(','))
sd = sys.argv[2]
lb = int(sys.argv[3])
found = None
for vf in glob.glob(f'{sd}/verdict_*.txt'):
    boards = {}
    for line in open(vf):
        if line.startswith('BOARD '):
            t = line.split()
            boards[t[1]] = [int(x) for x in t[2:]]
    for key, b in boards.items():
        grid = reconstruct_board(WORD, b)
        ok, vt, rep = T.verify_board(WORD, mask, grid)
        print(f"  MAX {key}: witness ok={ok} vt={vt}", flush=True)
        if ok and vt > lb and (found is None or vt > found):
            blob = {'board': T.B, 'main_word': WORD,
                    'turn_str': ''.join(ch.upper() if i in set(mask) else ch.lower()
                                        for i, ch in enumerate(WORD)),
                    'require_center': True, 'claimed_total': vt, 'grid': grid}
            p = f'/home/bob/programming/scrabble4/experiments/results/turns/N15_best_{vt}.json'
            json.dump(blob, open(p, 'w'))
            print(f"  *** NEW LB {vt} saved {p} ***", flush=True)
            found = vt
sys.exit(0 if found else 1)
