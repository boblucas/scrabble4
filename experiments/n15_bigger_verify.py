"""Re-verify an N=15 turn witness JSON under the BIGGER Dutch lexicon (data/words/dutch_bigger_le15).

Self-contained: loads `construct_rules('dutch', '15', word_file=...)` so it keeps the Dutch tile
values/bag/blanks but swaps the word list for the bigger one.  Since dutch is a SUBSET of
dutch_bigger, any board legal under `dutch` is legal under `dutch_bigger` (more words can only add
cross-word options, never remove legality), so a dutch witness re-verifies here -> a sound
dutch_bigger LB.  Uses witness_check.check_witness as the sole authority (require_center=True,
reserve via board <= T-1 is implicit in the bag check; we additionally enforce the explicit
reserve invariant the dutch gameplan uses: total occupied <= bag+blanks-RESERVE).
"""
import sys, os, json, argparse
from collections import Counter
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
from scrabble import construct_rules
import witness_check as wc

ROOT = '/home/bob/programming/scrabble4'
WORD_FILE = 'data/words/dutch_bigger_le15'
B = '15'
RESERVE = 1


def verify_blob(blob, word_file=WORD_FILE):
    rules = construct_rules('dutch', B, word_file=word_file)
    W, H = rules.W, rules.H
    turn = blob['turn_str']
    mask = [turn[x].isupper() for x in range(W)]
    grid = blob['grid']
    blank, info = wc.derive_blanks(rules, grid, mask, W, H)
    if blank is None:
        return False, None, {'fail': f'blank: {info}'}
    ok, rep = wc.check_witness(rules, W, H, grid, blank, mask,
                              claimed_total=blob.get('claimed_total'), require_center=True)
    # explicit reserve invariant: opponent holds >=1 tile -> board <= bag+blanks-RESERVE
    occ = sum(1 for y in range(H) for x in range(W) if grid[y][x] != 0)
    cap = sum(rules.counts.values()) + rules.blank_count - RESERVE
    rep['occupied'] = occ
    rep['bag_cap_with_reserve'] = cap
    if occ > cap:
        return False, None, {**rep, 'fail': f'reserve: {occ} tiles > cap {cap}'}
    return ok, (int(rep['total']) if ok else None), rep


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='inp', required=True, help='witness JSON path')
    ap.add_argument('--word-file', default=WORD_FILE)
    ap.add_argument('--save-as', default=None, help='if OK, write a dutch_bigger witness JSON here')
    a = ap.parse_args()
    blob = json.load(open(a.inp))
    print(f"# verifying {a.inp} (main={blob.get('main_word')}) under {a.word_file}", flush=True)
    ok, total, rep = verify_blob(blob, a.word_file)
    print(f"ok={ok} total={total}", flush=True)
    print(f"  main_score={rep.get('main_score')} vertical_score={rep.get('vertical_score')} "
          f"verticals={rep.get('verticals')}", flush=True)
    print(f"  occupied={rep.get('occupied')} cap(reserve={RESERVE})={rep.get('bag_cap_with_reserve')}", flush=True)
    if not ok:
        print(f"  FAIL: {rep.get('fail')}", flush=True)
        sys.exit(1)
    if a.save_as:
        out = dict(blob)
        out['claimed_total'] = total
        out['lexicon'] = a.word_file
        json.dump(out, open(a.save_as, 'w'))
        print(f"  saved dutch_bigger witness -> {a.save_as}", flush=True)
