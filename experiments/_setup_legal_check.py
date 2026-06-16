"""Corrected legality check: every maximal run >=2 in the SETUP board (final minus the 7 newly
row-0 tiles) must be a legal word. This is the constraint witness_check MISSED (it only checked
final-board runs). Reports setup-illegal runs per saved board."""
import json, os, sys
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, 'experiments')
from scrabble import construct_rules
r = construct_rules('dutch', '15'); W = H = 15; wl = r.words_lookup

def setup_bad_runs(path):
    d = json.load(open(path)); g = d['grid']; turn = d['turn_str']
    mask = {x for x, c in enumerate(turn) if c.isupper()}
    s = [[(0 if (y == 0 and x in mask) else g[y][x]) for x in range(W)] for y in range(H)]
    bad = []
    for x in range(W):
        y = 0
        while y < H:
            if s[y][x] == 0: y += 1; continue
            y2 = y
            while y2 < H and s[y2][x] != 0: y2 += 1
            run = tuple(s[k][x] for k in range(y, y2))
            if len(run) >= 2 and run not in wl:
                bad.append('V(%d,%d)=%s' % (x, y, ''.join(chr(96+c) for c in run)))
            y = y2
    for y in range(H):
        x = 0
        while x < W:
            if s[y][x] == 0: x += 1; continue
            x2 = x
            while x2 < W and s[y][x2] != 0: x2 += 1
            run = tuple(s[y][k] for k in range(x, x2))
            if len(run) >= 2 and run not in wl:
                bad.append('H(%d,%d)=%s' % (x, y, ''.join(chr(96+c) for c in run)))
            x = x2
    return d.get('claimed_total'), bad

for p in sorted(__import__('glob').glob('experiments/results/turns/N15_best_*.json')):
    tot, bad = setup_bad_runs(p)
    print('%-40s total=%s SETUP=%s' % (os.path.basename(p), tot, 'LEGAL' if not bad else 'ILLEGAL %d: %s' % (len(bad), bad[:6])))
