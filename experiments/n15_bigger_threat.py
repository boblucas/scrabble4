"""N=15 THREAT-SET enumerator + per-(word,mask) CERTIFICATION for the BIGGER dictionary.

SELF-CONTAINED adaptation of experiments/n15_threat_enum.py + n15_certify.py for the
`dutch_bigger_le15` lexicon.  Does NOT import/mutate the dutch run's files; only reuses the shared
read-only primitives.

Two subcommands:

  enum   -- compute a SOUND upper bound UB(word) = x27_proxy(word) + vert_UB(word) for every
            15-letter word, and report the THREAT SET = {words : UB(word) > FLOOR}.  Any word with
            UB <= FLOOR provably cannot beat the verified LB and is discarded.  Writes
            experiments/results/n15_bigger_threats.jsonl.

  certify -- for each threat word (descending UB), prove its TRUE single-turn max <= FLOOR (CP-SAT
            maximizing the added vertical bonus to OPTIMALITY, verticals allowed on ALL newly cols
            -> sound UB), or find a board that beats the floor (a NEW verified LB, re-checked by
            witness_check and saved to N15_bigger_best_<total>.json).  Only an OPTIMAL/INFEAS CP-SAT
            status is a proof; TIMEOUT/UNKNOWN = OPEN.

SOUNDNESS (see experiments/n15_threat_enum.py docstring -- identical argument):
  * To reach x27 the main word must newly-place on all of {0,7,14} => a 15-letter word.  Any word
    not spanning all three TWS has word-mult <= x9, capped at 9*(maxlettersum+16)+50 << FLOOR.
  * x27_proxy over-estimates the main score (assumes both DLS 3/11 newly).
  * vert_UB(w) = sum of the 7 largest per-column exact best vertical bonuses (verticals add only at
    newly cols; a bingo newly-places exactly 7 cols).  Ignores bag contention -> looser, never
    tighter.  SOUND.

FLOOR = the current best VERIFIED dutch_bigger LB (pass via --floor).

Single sequential process (process-kill safety: no parallelism, no group kills).
"""
import sys, os, json, time, argparse
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, 'experiments')
import numpy as np
from collections import Counter
from itertools import combinations
from ortools.sat.python import cp_model

from scrabble import construct_rules
from dawg import position_independent_row_automaton
from solve import create_board, single_component_flow, limit_letter_count
import witness_check as wc

ROOT = '/home/bob/programming/scrabble4'
B = '15'
HMAX = 8
RESERVE = 1
CENTER = (7, 7)
WORD_FILE = 'data/words/dutch_bigger_le15'
os.environ.setdefault('CPSAT_WORKERS', '6')

r = construct_rules('dutch', B, word_file=WORD_FILE)
W = H = r.W
val = {chr(96 + i): r.scores[i] for i in range(1, 27)}
WM = np.array(r.word_multiplier)[0]
LM = np.array(r.letter_multiplier)[0]
TWS = [c for c in range(W) if WM[c] == 3]
DLS = [c for c in range(W) if LM[c] == 2]
assert TWS == [0, 7, 14] and DLS == [3, 11], (TWS, DLS)
N15 = [w for w in r.words_str if len(w) == 15]

# Precompute once (the 4.1M-word lexicon must NOT be re-scanned per mask/column):
#   _SHORT_BY_FIRST[letter] = list of (len, tail_codes) for all dict words len 2..HMAX with that
#                             first letter -> O(words-with-that-letter) vert_tail_table.
#   _TAILMAX[letter]        = exact best sum(val(tail)) over those words (the per-column vert UB).
from collections import defaultdict
_SHORT_BY_FIRST = defaultdict(list)
_TAILMAX = {}
_cba = r.alphabet.cba
for _word in r.words_str:
    if 2 <= len(_word) <= HMAX:
        _f = _word[0]
        _tail = [_cba[c] for c in _word[1:]]
        _SHORT_BY_FIRST[_f].append(_tail)
        _tv = sum(val[c] for c in _word[1:])
        if _tv > _TAILMAX.get(_f, -1):
            _TAILMAX[_f] = _tv


def x27_proxy(w):
    return 27 * (sum(val[c] for c in w) + val[w[3]] + val[w[11]]) + 50


def true_main(w, mask):
    ms = set(mask)
    s = 0
    for x in range(W):
        lm = 2 if (x in ms and x in (3, 11)) else 1
        s += val[w[x]] * lm
    return 27 * s + 50


def best_vert_bonus(c, L):
    if L not in _TAILMAX:
        return 0
    return int(WM[c]) * (int(LM[c]) * val[L] + _TAILMAX[L])


def vert_UB(w):
    bonuses = sorted((best_vert_bonus(c, w[c]) for c in range(W)), reverse=True)
    return sum(bonuses[:7])


def vert_UB_all(w):
    return sum(best_vert_bonus(c, w[c]) for c in range(W))


def _pre_runs_legal(w, mask):
    wl = r.words_lookup; cba = r.alphabet.cba
    preset = set(range(W)) - set(mask)
    x = 0
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


def best_legal_mask(w):
    free = [c for c in range(W) if c not in (0, 7, 14)]
    best = None; bestbonus = -1
    for extra in combinations(free, 4):
        mask = tuple(sorted((0, 7, 14) + extra))
        if not _pre_runs_legal(w, mask):
            continue
        ms = set(mask)
        bonus = 27 * ((val[w[3]] if 3 in ms else 0) + (val[w[11]] if 11 in ms else 0))
        if bonus > bestbonus:
            bestbonus = bonus; best = mask
    return best


def legal_masks(w):
    free = [c for c in range(W) if c not in (0, 7, 14)]
    out = []
    for extra in combinations(free, 4):
        mask = tuple(sorted((0, 7, 14) + extra))
        if _pre_runs_legal(w, mask):
            out.append(mask)
    return out


def mask_UB(w, mask):
    return true_main(w, mask) + sum(best_vert_bonus(c, w[c]) for c in mask)


# ---------------- enumeration ----------------
def enum(floor, out_path):
    rows = []
    for w in N15:
        xp = x27_proxy(w)
        vu = vert_UB(w)
        ub = xp + vu
        if ub > floor:
            rows.append((ub, xp, vu, w))
    rows.sort(reverse=True)
    print(f"# N=15 bigger THREAT enum  floor={floor}", flush=True)
    print(f"# 15-letter words total: {len(N15)}", flush=True)
    print(f"# words with UB = x27_proxy + vert_UB(7-best) > {floor}: {len(rows)}", flush=True)
    n_mask = 0
    with open(out_path, 'w') as f:
        for ub, xp, vu, w in rows:
            mask = best_legal_mask(w)
            if mask is not None:
                n_mask += 1
            rec = {'word': w, 'UB': ub, 'x27_proxy': xp, 'vert_UB': vu,
                   'vert_UB_all': vert_UB_all(w), 'best_mask': mask,
                   'has_legal_mask': mask is not None}
            f.write(json.dumps(rec) + '\n')
    print(f"# wrote {out_path}", flush=True)
    print(f"# threat words with a legal x27 mask: {n_mask}/{len(rows)}", flush=True)
    print(f"\n{'UB':>6} {'x27p':>6} {'vUB':>5}  {'mask?':>5}  word", flush=True)
    for ub, xp, vu, w in rows[:60]:
        mask = best_legal_mask(w)
        print(f"{ub:6d} {xp:6d} {vu:5d}  {str(mask is not None):>5}  {w}", flush=True)
    return rows


# ---------------- certification ----------------
_AUT_CACHE = {}
def _aut(maxlen):
    a = _AUT_CACHE.get(maxlen)
    if a is None:
        a = position_independent_row_automaton([w for w in r.words if 1 <= len(w) <= maxlen])
        _AUT_CACHE[maxlen] = a
    return a


def vert_tail_table(top_letter, Ltail):
    rows = [[0] * Ltail]
    for tail in _SHORT_BY_FIRST.get(top_letter, ()):
        if len(tail) > Ltail:
            continue
        rows.append(tail + [0] * (Ltail - len(tail)))
    return np.array(rows, dtype=int)


def certify_mask(word, mask, cap, rows=H, maxlen=HMAX):
    """Maximize added vertical bonus for (word,mask) to OPTIMALITY (verticals on ALL newly cols)."""
    mt = r.alphabet.to_tup(word)
    newly = set(mask)
    pre = [x for x in range(W) if x not in newly]
    runlen = 1; cur = 0
    for x in range(W):
        if x in pre:
            cur += 1; runlen = max(runlen, cur)
        else:
            cur = 0
    aut = _aut(max(maxlen, runlen))
    m = cp_model.CpModel(); m.prefix = 'q'
    vert_cols = sorted(newly)
    col_auts = [None if x in vert_cols else aut for x in range(W)]
    cells = create_board(m, [aut] * H, col_auts, alphabet_size=len(r.abc))
    for y in range(rows, H):
        for x in range(W):
            m.add(cells[(x, y)].active == 0)
    for x in pre:
        m.add(cells[(x, 0)].letter[mt[x]] == 1)
    for x in newly:
        m.add(cells[(x, 0)].active == 0)
    Ltail = min(HMAX - 1, rows - 1)
    val_arr = [0] + [int(r.scores[code]) for code in range(1, len(r.abc) + 1)]
    obj_terms = []
    for c in vert_cols:
        top_letter = word[c]
        table = vert_tail_table(top_letter, Ltail)
        tail_vars = [cells[(c, y)].letter_int for y in range(1, 1 + Ltail)]
        m.add_allowed_assignments(tail_vars, table)
        for y in range(1 + Ltail, H):
            m.add(cells[(c, y)].active == 0)
        has_vert = cells[(c, 1)].active
        obj_terms.append(int(WM[c]) * int(LM[c]) * int(val[top_letter]) * has_vert)
        for y in range(1, 1 + Ltail):
            cell = cells[(c, y)]
            m.add(cell.blank == 0)
            cv = m.new_int_var(0, max(val_arr), f'{m.prefix}_cv_{c}_{y}')
            m.add_element(cell.letter_int, val_arr, cv)
            obj_terms.append(int(WM[c]) * cv)
    m.add(cells[CENTER].active == 1)
    single_component_flow(m, cells, CENTER)
    newly_ct = Counter(mt[c] for c in mask)
    avail = Counter({code: r.counts[code] - newly_ct[code] for code in r.counts})
    limit_letter_count(m, cells, avail)
    m.add(sum(cell.blank for cell in cells.values()) <= r.blank_count)
    total_cap = sum(r.counts.values()) + r.blank_count - RESERVE - 7
    m.add(sum(cell.active for cell in cells.values()) <= total_cap)
    m.maximize(sum(obj_terms))
    s = cp_model.CpSolver()
    s.parameters.num_search_workers = int(os.environ.get('CPSAT_WORKERS', '6'))
    s.parameters.max_time_in_seconds = cap
    st = s.Solve(m)
    statusmap = {cp_model.OPTIMAL: 'OPTIMAL', cp_model.FEASIBLE: 'FEASIBLE',
                 cp_model.INFEASIBLE: 'INFEAS', cp_model.UNKNOWN: 'TIMEOUT',
                 cp_model.MODEL_INVALID: 'INVALID'}
    sst = statusmap.get(st, str(st))
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        grid = [[int(s.value(cells[(x, y)].letter_int)) for x in range(W)] for y in range(H)]
        for x in range(W):
            grid[0][x] = int(mt[x])
        return sst, int(s.objective_value), grid
    if st == cp_model.INFEASIBLE:
        return 'INFEAS', None, None
    return sst, None, None


def verify(word, mask, grid):
    turn = ''.join(c.upper() if i in set(mask) else c.lower() for i, c in enumerate(word))
    mask_b = [turn[x].isupper() for x in range(W)]
    r2 = construct_rules('dutch', B, word_file=WORD_FILE)
    blank, info = wc.derive_blanks(r2, grid, mask_b, W, H)
    if blank is None:
        return False, None, {'fail': f'blank: {info}'}
    ok, rep = wc.check_witness(r2, W, H, grid, blank, mask_b, claimed_total=None, require_center=True)
    return ok, (int(rep['total']) if ok else None), rep


def certify_word(word, floor, cap, rows=H):
    masks = legal_masks(word)
    result = {'word': word, 'n_masks': len(masks), 'masks': [], 'verdict': None,
              'best_total_found': 0, 'best_grid': None, 'best_mask': None}
    if not masks:
        result['verdict'] = 'NO-LEGAL-MASK'
        return result
    all_certified = True
    for mask in masks:
        tm = true_main(word, mask)
        mub = mask_UB(word, mask)
        if mub <= floor:
            result['masks'].append({'mask': mask, 'true_main': tm, 'status': 'ANALYTIC',
                                    'obj': None, 'max_total': None, 'mask_UB': mub,
                                    'note': 'CERTIFIED-LE-FLOOR(analytic)', 'secs': 0.0})
            continue
        t0 = time.time()
        sst, obj, grid = certify_mask(word, mask, cap, rows=rows)
        dt = time.time() - t0
        entry = {'mask': mask, 'true_main': tm, 'status': sst, 'obj': obj,
                 'max_total': (tm + obj) if obj is not None else None, 'secs': round(dt, 1)}
        if grid is not None:
            ok, total, rep = verify(word, mask, grid)
            entry['verified_total'] = total if ok else None
            entry['verify_ok'] = ok
            if ok and total > result['best_total_found']:
                result['best_total_found'] = total
                result['best_grid'] = grid
                result['best_mask'] = mask
        if sst == 'OPTIMAL':
            entry['note'] = 'OPTIMAL-EXCEEDS-FLOOR' if (tm + obj) > floor else 'CERTIFIED-LE-FLOOR'
        elif sst == 'INFEAS':
            entry['note'] = 'mask-infeasible(<=floor trivially)'
        else:
            entry['note'] = 'OPEN'; all_certified = False
        result['masks'].append(entry)
    exceeds = any(e.get('max_total') is not None and e['status'] == 'OPTIMAL'
                  and e['max_total'] > floor for e in result['masks'])
    result['verdict'] = 'EXCEEDS-FLOOR' if exceeds else ('CERTIFIED-LE-FLOOR' if all_certified else 'OPEN')
    return result


def save_lb(word, mask, grid, total):
    turn = ''.join(c.upper() if i in set(mask) else c.lower() for i, c in enumerate(word))
    blob = {'board': B, 'main_word': word, 'turn_str': turn, 'require_center': True,
            'claimed_total': total, 'grid': grid}
    path = f'{ROOT}/experiments/results/turns/N15_bigger_best_{total}.json'
    json.dump(blob, open(path, 'w'))
    return path


def certify_run(floor, cap, rows, limit, skip, threats_path, out_path):
    threats = [json.loads(l) for l in open(threats_path)]
    threats.sort(key=lambda x: -x['UB'])
    threats = threats[skip:]
    if limit:
        threats = threats[:limit]
    outf = open(out_path, 'a')
    for t in threats:
        w = t['word']
        print(f"\n=== {w}  UB={t['UB']}  (floor={floor}) ===", flush=True)
        res = certify_word(w, floor, cap, rows=rows)
        res['UB'] = t['UB']
        for e in res['masks']:
            print(f"   mask={e['mask']} main={e['true_main']} {e['status']} obj={e['obj']} "
                  f"max_total={e['max_total']} {e['note']} ({e['secs']}s)", flush=True)
        print(f"   VERDICT {w}: {res['verdict']}  best_found={res['best_total_found']}", flush=True)
        if res['best_total_found'] > floor and res['best_grid'] is not None:
            total = res['best_total_found']; mask = res['best_mask']
            path = save_lb(w, mask, res['best_grid'], total)
            print(f"   *** NEW LB {total} saved {path} -- RAISE FLOOR & re-run threats ***", flush=True)
            floor = total
        outf.write(json.dumps({k: v for k, v in res.items() if k != 'best_grid'}, default=str) + '\n')
        outf.flush()
    outf.close()
    print(f"\n# certify pass done; floor now {floor}; results appended to {out_path}", flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['enum', 'certify'])
    ap.add_argument('--floor', type=int, required=True)
    ap.add_argument('--cap', type=float, default=120.0)
    ap.add_argument('--rows', type=int, default=H)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--skip', type=int, default=0)
    ap.add_argument('--word', type=str, default=None)
    ap.add_argument('--threats', type=str, default=f'{ROOT}/experiments/results/n15_bigger_threats.jsonl')
    ap.add_argument('--out', type=str, default=f'{ROOT}/experiments/results/n15_bigger_certify.jsonl')
    a = ap.parse_args()
    if a.cmd == 'enum':
        enum(a.floor, a.threats)
    elif a.cmd == 'certify':
        if a.word:
            res = certify_word(a.word, a.floor, a.cap, rows=a.rows)
            print(json.dumps(res, default=str, indent=2), flush=True)
        else:
            certify_run(a.floor, a.cap, a.rows, a.limit, a.skip, a.threats, a.out)
