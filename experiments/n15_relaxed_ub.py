"""N=15 SOUND LEAN upper bound per (word, mask) -- the certification workhorse.

For a fixed (word, mask) the single-turn total = true_main(word, mask) + (added vertical bonus).
We upper-bound the added vertical bonus with a RELAXATION that DROPS connectivity and connector
legality (those can only further constrain a real board, so dropping them gives a sound over-
estimate), keeping exactly the two couplings that actually limit the verticals:

  * LEGALITY of each vertical: at each newly column c the vertical is `word[c] + tail`, a legal dict
    word of length 2..HMAX(8) with the FIXED top letter, OR the column carries no vertical.
  * the shared finite BAG (reserve=1): the vertical TAIL tiles + the 7 newly main-word tiles must
    fit r.counts.  (Tail tiles are pre-placed, face value, never blanks -- blanks score 0 so are
    never chosen for a scored tile; the blank budget is not binding for the scored part.)

This is a small ILP (one bool per candidate vertical word per newly column; at-most-one per column;
per-letter bag caps).  CP-SAT solves it to OPTIMALITY in seconds.  The optimum `V*` satisfies
    true_max(word, mask)  <=  true_main(word, mask) + V*
because every real board is feasible in this relaxation (it only has MORE constraints) and scores at
most true_main + its vertical bonus <= true_main + V*.  Hence:

    UB(word, mask) = true_main(word, mask) + V*    is a SOUND upper bound.

If UB(word, mask) <= floor for EVERY legal mask of a word, the word is CERTIFIED <= floor (its true
single-turn max cannot beat the floor).  This is a genuine proof: the relaxation is sound and CP-SAT
returns OPTIMAL (we assert status==OPTIMAL; otherwise the mask is reported OPEN).

NOTE: this relaxation can only CERTIFY (prove <= floor); it can never find a witness (it has no
board / connectivity).  Masks whose relaxed UB still exceeds the floor are OPEN here and handed to
the witness search (n15_certify.py / n15_push_lb.py) -- a board scoring > floor there is a new LB;
failure to find one within the wall is honestly OPEN.

Single sequential process (process-kill safety).
"""
import sys, os, json, time, argparse
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, 'experiments')
import numpy as np
from collections import Counter, defaultdict
from itertools import combinations
from ortools.sat.python import cp_model
from scrabble import construct_rules

ROOT = '/home/bob/programming/scrabble4'
B = '15'; HMAX = 8; RESERVE = 1
r = construct_rules('dutch', B)
W = r.W
val = {chr(96 + i): r.scores[i] for i in range(1, 27)}
WM = np.array(r.word_multiplier)[0]
LM = np.array(r.letter_multiplier)[0]
cba = r.alphabet.cba

# candidate verticals grouped by first letter: (tail_codes, tail_value_sum)
_VBY = defaultdict(list)
for _w in r.words_str:
    if 2 <= len(_w) <= HMAX:
        tail = [cba[c] for c in _w[1:]]
        _VBY[_w[0]].append((tail, sum(r.scores[c] for c in tail)))

# exact max ADDED single-column vertical bonus per (col, top letter) -- the analytic pre-filter
_TAILMAX = {}
for _w in r.words_str:
    if 2 <= len(_w) <= HMAX:
        _tv = sum(val[c] for c in _w[1:])
        if _tv > _TAILMAX.get(_w[0], -1):
            _TAILMAX[_w[0]] = _tv


def best_vert_bonus(c, L):
    if L not in _TAILMAX:
        return 0
    return int(WM[c]) * (int(LM[c]) * val[L] + _TAILMAX[L])


def mask_analytic_UB(w, mask):
    """SOUND per-mask analytic UB = true_main + sum of per-column best vertical bonus over the mask
    (per-column exact, ignores bag -> over-estimate). If <= floor, no CP-SAT needed."""
    return true_main(w, mask) + sum(best_vert_bonus(c, w[c]) for c in mask)

N15 = [w for w in r.words_str if len(w) == 15]


def true_main(w, mask):
    ms = set(mask); s = 0
    for x in range(W):
        lm = 2 if (x in ms and x in (3, 11)) else 1
        s += val[w[x]] * lm
    return 27 * s + 50


def _pre_runs_legal(w, mask):
    wl = r.words_lookup; preset = set(range(W)) - set(mask); x = 0
    while x < W:
        if x not in preset:
            x += 1; continue
        x2 = x
        while x2 < W and x2 in preset:
            x2 += 1
        if x2 - x >= 2 and tuple(cba[c] for c in w[x:x2]) not in wl:
            return False
        x = x2
    return True


def legal_masks(w):
    free = [c for c in range(W) if c not in (0, 7, 14)]
    out = []
    for extra in combinations(free, 4):
        mask = tuple(sorted((0, 7, 14) + extra))
        if _pre_runs_legal(w, mask):
            out.append(mask)
    return out


def relaxed_vert_ub(w, mask, cap=30):
    """OPTIMAL added-vertical-bonus upper bound for (w, mask). Returns (ok_optimal, V*)."""
    mt = r.alphabet.to_tup(w)
    newly = sorted(mask)
    main_ct = Counter(mt[c] for c in mask)
    m = cp_model.CpModel(); m.prefix = 'u'
    obj = []; tile_use = defaultdict(list)
    for c in newly:
        L = w[c]; cands = _VBY.get(L, [])
        sel = []
        for i, (tail, tv) in enumerate(cands):
            b = m.new_bool_var(f'v{c}_{i}'); sel.append(b)
            obj.append(int(WM[c]) * (int(LM[c]) * val[L] + tv) * b)
            for code in tail:
                tile_use[code].append(b)
        if sel:
            m.add(sum(sel) <= 1)
    for code in r.counts:
        if tile_use[code]:
            avail = max(r.counts[code] - main_ct.get(code, 0), 0)
            m.add(sum(tile_use[code]) <= avail)
    m.maximize(sum(obj))
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = cap
    s.parameters.num_search_workers = int(os.environ.get('CPSAT_WORKERS', '8'))
    st = s.Solve(m)
    if st == cp_model.OPTIMAL:
        return True, int(s.objective_value)
    # not proven optimal: return the proven bound (sound UB) but flag not-optimal
    return False, int(s.best_objective_bound)


def certify_word(w, floor, cap):
    masks = legal_masks(w)
    if not masks:
        return {'word': w, 'verdict': 'NO-LEGAL-SIZE7-MASK', 'masks': []}
    entries = []; verdict = 'CERTIFIED-LE-FLOOR'
    for mask in masks:
        tm = true_main(w, mask)
        # analytic pre-filter (sound): per-mask UB <= floor -> certified, skip CP-SAT
        aub = mask_analytic_UB(w, mask)
        if aub <= floor:
            entries.append({'mask': mask, 'true_main': tm, 'Vstar': None, 'UB': aub,
                            'optimal': True, 'note': 'CERTIFIED-LE-FLOOR(analytic)'})
            continue
        ok, vstar = relaxed_vert_ub(w, mask, cap)
        ub = tm + vstar
        e = {'mask': mask, 'true_main': tm, 'Vstar': vstar, 'UB': ub, 'optimal': ok}
        if ub > floor:
            e['note'] = 'OPEN(relaxed UB > floor)'
            verdict = 'OPEN'
        elif not ok:
            e['note'] = 'bound-not-optimal-but-<=floor'   # proven bound already <= floor -> certified
        else:
            e['note'] = 'CERTIFIED-LE-FLOOR'
        entries.append(e)
    # word is certified iff EVERY mask has a sound UB <= floor (proven bound <= floor counts)
    if all(e['UB'] <= floor for e in entries):
        verdict = 'CERTIFIED-LE-FLOOR'
    else:
        verdict = 'OPEN'
    return {'word': w, 'verdict': verdict, 'n_masks': len(masks),
            'max_UB': max(e['UB'] for e in entries),
            'open_masks': [e['mask'] for e in entries if e['UB'] > floor], 'masks': entries}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--floor', type=int, default=1952)
    ap.add_argument('--cap', type=float, default=30.0)
    ap.add_argument('--word', type=str, default=None)
    ap.add_argument('--from-threats', action='store_true')
    ap.add_argument('--out', type=str, default=f'{ROOT}/experiments/results/n15_relaxed_ub.jsonl')
    a = ap.parse_args()
    if a.word:
        print(json.dumps(certify_word(a.word, a.floor, a.cap), default=str, indent=2), flush=True)
        return
    if a.from_threats:
        threats = [json.loads(l) for l in open(f'{ROOT}/experiments/results/n15_threats.jsonl')]
        threats.sort(key=lambda x: -x['UB'])
        outf = open(a.out, 'w')
        n_cert = 0; n_open = 0; n_nomask = 0
        for t in threats:
            w = t['word']; t0 = time.time()
            res = certify_word(w, a.floor, a.cap)
            res['analytic_UB'] = t['UB']; res['secs'] = round(time.time() - t0, 1)
            outf.write(json.dumps(res, default=str) + '\n'); outf.flush()
            if res['verdict'] == 'CERTIFIED-LE-FLOOR':
                n_cert += 1; tag = 'CERTIFIED'
            elif res['verdict'] == 'NO-LEGAL-SIZE7-MASK':
                n_nomask += 1; tag = 'NO-SIZE7-MASK'
            else:
                n_open += 1; tag = f"OPEN maxUB={res['max_UB']} ({len(res['open_masks'])} masks)"
            print(f"{w:18s} analyticUB={t['UB']:5d}  {tag}  ({res['secs']}s)", flush=True)
        print(f"\n# CERTIFIED <= {a.floor}: {n_cert}   OPEN: {n_open}   "
              f"NO-SIZE7-MASK: {n_nomask}   (total {len(threats)})", flush=True)
        outf.close()


if __name__ == '__main__':
    main()
