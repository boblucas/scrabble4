"""N=13 center-constrained BATCHED witness scanner (one Python pass, one xfill call per round).

Same verified witnesses as the per-word n13_witness/n13_ranksweep path, but the dict loads ONCE
(xfill `--batch ... --emit`) instead of one fresh Python process + dict-write + xfill spawn PER word.
On the infeasible-heavy ranked slice (most candidates are rejected by xfill in nodes=1, microseconds)
the per-word path is dominated entirely by wrapper/startup overhead -- this kills it.

Pipeline:
  1. ONE Python pass: read ranked candidates (experiments/results/n13/rank.txt; `opt_total main vert word`),
     write the dict ONCE, build each (word,lvec) instance via xtest.build_instance/dump_simple to a
     per-instance file, accumulate a LISTFILE `<key> <path> <floor>`.  key encodes word+lvec index.
  2. ONE `xfill --batch LISTFILE --emit` call (dict cached across all instances; sound per-instance
     wall via BATCHWALL).  Emits `RES <key> <line>` + (when best>floor, incl. TO incumbents)
     `BOARD <key> <codes...>`.
  3. ONE Python pass: parse results, reconstruct each emitted grid (row 0 = the main word, exactly as
     n13_witness does), and verify EVERY board with witness_check (the independent authority).  Track
     the best verified TOTAL.

RATCHETING: candidates are processed best-opt-first in ROUNDS (--round-size).  At the start of each
round the per-instance floor is recomputed as max(0, best_total - main(word)) using the current best,
and any candidate whose optimistic opt_total <= best_total is dropped (it cannot beat the floor).
So later rounds run at a higher floor and root-prune harder -- the same ratchet the per-word sweep
gets, but amortized over a whole round per xfill call.

Usage:
  .venv/bin/python experiments/n13_batchscan.py [--rank experiments/results/n13/rank.txt] \
      [--start-total 366] [--wall 20] [--max-words 3000] [--round-size 400] \
      [--out-prefix experiments/results/n13/batchscan] [--xfill PATH] \
      [--extra "WORD:TURN:LVEC,..."]
  (--extra injects explicit (word,turn,lvec) candidates -- e.g. for the correctness gate -- that may
   not be in rank.txt; turn is the literal turn_str, lvec is comma-joined-with-dashes e.g. 8-2-2-2-2-2-7.)
"""
import sys, os, json, subprocess, argparse, time
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'experiments'))
import xtest
import witness_check as wc
from scrabble import construct_rules

DEFAULT_XFILL = os.path.join(ROOT, 'experiments/xfill_rs/target/release/xfill_lev3')
# length-vectors over scoring cols 0..6 (col6=center must reach center row 6 => len>=7).
# x3 cols are 0 and 6 -> make them long for high vertical (matches n13_ranksweep's LVECS).
LVECS = [(8, 2, 2, 2, 2, 2, 8), (8, 2, 2, 2, 2, 2, 7), (8, 3, 2, 2, 2, 3, 8)]


def parse_rank(path):
    out = []
    for line in open(path):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split()
        try:
            opt, main, vert, word = int(parts[0]), int(parts[1]), int(parts[2]), parts[3]
        except Exception:
            continue
        if len(word) == 13:
            out.append((opt, main, word))
    return out


def left_block_turn(word):
    return ''.join(c.upper() if i < 7 else c.lower() for i, c in enumerate(word))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rank', default='experiments/results/n13/rank.txt')
    ap.add_argument('--start-total', type=int, default=366)
    ap.add_argument('--wall', type=float, default=20.0)
    ap.add_argument('--max-words', type=int, default=3000)
    ap.add_argument('--round-size', type=int, default=400)
    ap.add_argument('--out-prefix', default='experiments/results/n13/batchscan')
    ap.add_argument('--board', default='13')
    ap.add_argument('--xfill', default=DEFAULT_XFILL)
    ap.add_argument('--reserve', type=int, default=1,
                    help='tiles reserved for the opponent (>=1): total setup <= sum(counts)+blanks-reserve')
    ap.add_argument('--extra', default='', help='WORD:TURN:LVEC[,...] explicit candidates (LVEC dash-joined)')
    a = ap.parse_args()

    xfill = a.xfill
    if not os.path.exists(xfill):
        sys.exit(f'xfill binary not found: {xfill} (build the worktree binary first)')

    rules = construct_rules('dutch', a.board)
    W, H = rules.W, rules.H
    cc, cr = W // 2, H // 2

    rank_path = a.rank if os.path.isabs(a.rank) else os.path.join(ROOT, a.rank)
    cands = parse_rank(rank_path)[:a.max_words]

    # explicit extras (correctness gate): (word, turn, lvec_tuple)
    extras = []
    for tok in a.extra.split(',') if a.extra else []:
        tok = tok.strip()
        if not tok:
            continue
        word, turn, lv = tok.split(':')
        extras.append((word, turn, tuple(int(x) for x in lv.split('-'))))

    out_pref = a.out_prefix if os.path.isabs(a.out_prefix) else os.path.join(ROOT, a.out_prefix)
    os.makedirs(os.path.dirname(out_pref), exist_ok=True)
    instdir = out_pref + '_inst'
    os.makedirs(instdir, exist_ok=True)
    log = out_pref + '.log'

    def emit(msg):
        with open(log, 'a') as f:
            f.write(msg + '\n')
        print(msg, flush=True)

    # dict ONCE
    xtest.write_dict(a.board)

    best_total = a.start_total
    best_file = None
    t_all = time.time()
    total_instances = 0
    total_verified_boards = 0

    emit(f"# N=13 BATCHED scan: {len(cands)} ranked cands + {len(extras)} extras, "
         f"start_total={best_total}, wall={a.wall}, lvecs={LVECS}, round_size={a.round_size}, "
         f"xfill={os.path.basename(xfill)}")

    # build the worklist: ranked cands, best-opt-first; extras prepended (processed round 0).
    # each work item: (opt, main, word, turn, lvec_tuple)
    work = []
    for word, turn, lv in extras:
        mt = rules.alphabet.to_tup(word)
        # optimistic-total isn't meaningful for arbitrary extras; mark opt very high so they always run.
        main_proxy = 10 ** 9
        work.append((10 ** 9, main_proxy, word, turn, lv))
    for opt, main, word in cands:
        turn = left_block_turn(word)
        for lv in LVECS:
            work.append((opt, main, word, turn, lv))

    # process in rounds; recompute floors per round from current best.
    nrounds = 0
    i = 0
    while i < len(work):
        chunk = work[i:i + a.round_size]
        i += a.round_size
        nrounds += 1
        # build listfile + instances for this chunk
        listpath = out_pref + f'_round{nrounds}.list'
        items = []          # (key, word, turn, lvec, floor)
        with open(listpath, 'w') as lf:
            for j, (opt, main, word, turn, lv) in enumerate(chunk):
                if main < 10 ** 9 and opt <= best_total:
                    continue                                  # can't beat current best -> skip
                # main score: prefer the rank-table main; for extras recompute via build_instance meta later.
                floor = max(0, (best_total - main)) if main < 10 ** 9 else 0
                Lvec = {c: lv[c] for c in range(7)}
                # center precondition (mirror n13_witness): col cc must be scoring with len>=cr+1.
                if cc not in Lvec or Lvec[cc] < cr + 1:
                    continue
                inst, meta = xtest.build_instance(a.board, word, turn, Lvec, scale=True, reserve=a.reserve)
                if inst is None:
                    continue                                  # no candidate vertical of some length -> skip
                key = f"{word}__{'-'.join(map(str, lv))}"
                instpath = os.path.join(instdir, key + '.txt')
                xtest.dump_simple(inst, None, instpath)
                lf.write(f"{key} {instpath} {floor}\n")
                items.append((key, word, turn, lv, floor))
        if not items:
            continue
        total_instances += len(items)
        keymap = {it[0]: it for it in items}

        env = dict(os.environ); env.pop('MAXNODES', None)
        env['BATCHWALL'] = str(a.wall)
        t0 = time.time()
        p = subprocess.run([xfill, '--batch', listpath, '--emit'],
                           cwd=ROOT, capture_output=True, text=True, env=env)
        dt = time.time() - t0
        lines = (p.stdout or '').splitlines()
        boards = {}
        results = {}
        for ln in lines:
            if ln.startswith('BOARD '):
                toks = ln.split()
                key = toks[1]
                boards[key] = [int(x) for x in toks[2:]]
            elif ln.startswith('RES '):
                toks = ln.split(maxsplit=2)
                results[toks[1]] = toks[2] if len(toks) > 2 else ''
        emit(f"# round {nrounds}: {len(items)} instances in {dt:.1f}s "
             f"({len(items)/dt:.1f} inst/s), {len(boards)} emitted boards; best_total={best_total}")

        # verify every emitted board independently
        for key, codes in boards.items():
            if key not in keymap:
                continue
            word, turn, lv = keymap[key][1], keymap[key][2], keymap[key][3]
            if len(codes) != W * H:
                emit(f"  WARN {key}: BOARD has {len(codes)} cells != {W*H}")
                continue
            grid = [[int(codes[y * W + x]) for x in range(W)] for y in range(H)]
            mt = rules.alphabet.to_tup(word)
            for x in range(W):
                grid[0][x] = int(mt[x])                       # row 0 = the main word
            # recompute via witness_check with the scaled bag (exactly as n13_witness)
            rules2 = construct_rules('dutch', a.board)
            f = (W * W) / (15 * 15); mc = Counter(mt)
            rules2.counts = Counter({c: max(round(n * f), mc[c], 1) for c, n in rules2.counts.items()})
            rules2.blank_count = round(rules2.blank_count * f)
            mask = [turn[x].isupper() for x in range(W)]
            blank, info = wc.derive_blanks(rules2, grid, mask, W, H)
            if blank is None:
                emit(f"  REJECT {key}: no valid blank assignment: {info}")
                continue
            ok, rep = wc.check_witness(rules2, W, H, grid, blank, mask,
                                       claimed_total=None, require_center=True)
            if not ok:
                emit(f"  REJECT {key}: witness_check fail={rep.get('fail')}")
                continue
            total_verified_boards += 1
            total = int(rep['total'])
            if total > best_total:
                best_total = total
                spec = {'board': a.board, 'main_word': word, 'turn_str': turn,
                        'scale': True, 'blanks': True, 'require_center': True,
                        'grid': grid, 'claimed_total': total}
                keep = out_pref + f'_best_{total}.json'
                json.dump(spec, open(keep, 'w'), indent=1)
                best_file = keep
                emit(f"NEWBEST round {nrounds} word={word} lvec={'-'.join(map(str,lv))} "
                     f"-> TOTAL={total} (main {rep['main_score']} + vert {rep['vertical_score']}) "
                     f"saved {keep}")

    dt_all = time.time() - t_all
    emit(f"# DONE rounds={nrounds} instances={total_instances} verified_boards={total_verified_boards} "
         f"best_total={best_total} file={best_file} wall={dt_all:.1f}s "
         f"({total_instances/max(dt_all,1e-9):.1f} inst/s overall)")


if __name__ == '__main__':
    main()
