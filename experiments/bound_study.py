#!/usr/bin/env python3
"""
EMPIRICAL STUDY (analysis only -- no solver edits, no soundness risk).

QUESTION: the max-turn N=11 certification cost is dominated by a "hard 6.2% slice" of
length-vectors whose CHEAP ROOT BOUND (AC-3 + greedy joint tile-knapsack, counting ONLY
stub letters) sits ABOVE the floor (226 for bouwfysicus N=11) while the TRUE max sits at/
below the floor.  Each such vector must be killed by full xfill search (82% of all time).

HYPOTHESIS: a TIGHTER root bound that COUPLES tile-reservation with the connectivity
requirement would drop many of these vectors below the floor at the root.  To form ONE
4-connected component containing the center you MUST place a minimum number of BRIDGE
tiles (which score zero but CONSUME tiles from the scaled bag).  The current knapsack
bound ignores that bridges consume tiles, so reserving them should shrink the tile budget
available for high-value stubs and tighten the UB.

WHAT THIS SCRIPT DOES
  1. Reconstructs the CURRENT root bound in pure Python (two flavors xfill actually uses):
       - sum-UB  : sum over scoring cols of best gross at that col-length (ignores ALL budget)
       - knapUB  : multiple-choice knapsack over per-col candidate words under the per-LETTER
                   bag budget + blank overflow (xfill's knap_ub / exp32 _knap_ub_cached).
                   This is what gates pruning. It counts ONLY stub letters; bridges = free.
  2. Computes the Steiner bridge lower bound B = min_bridge_cells(stub cells + preplaced),
     i.e. the minimum number of bridge tiles forced by connectivity for that length-vector.
  3. Implements the PROPOSED coupled bound: reserve B tiles from the bag, then recompute the
     knapsack on the reduced budget.  Two sound reservation models (both are valid UBs):
       (a) TOTAL-count coupling: add the constraint  sum(stub tiles) <= total_bag - W - B
           (bridges consume B generic tiles; adversary picks bridge letters freely, so only
            the aggregate tile pool is provably reduced).
       (b) WORST-FOR-ADVERSARY per-letter coupling: the B bridge tiles must come from the
           bag; the adversary places them on the letters with the most slack, but we charge
           the knapsack for B tiles drawn from the pool that the stubs would otherwise want.
           Implemented as: lower the per-letter availability of the B cheapest-to-the-stubs
           letters is UNSOUND (bridges need not use those) -- so (b) is NOT generally sound;
           we only report (a), which is rigorously sound, plus a diagnostic "ideal" coupling
           that assumes bridges steal the highest-value still-available stub letters (an
           OPTIMISTIC, generally-UNSOUND lower estimate of the tightening ceiling).
  4. MEASURES across a sample of the hard slice:
       (a) how many vectors does the proposed sound bound drop to <= floor (root-prunable)?
       (b) average tightening of UB.
       (c) rough core-hour savings.

NOTE on soundness of (a): bridges consume real tiles from the *same* finite bag the stubs
draw from. The aggregate constraint sum(all newly-placed tiles) <= total_bag is a hard
physical constraint of the model (W main + stubs + bridges + blanks all come from one bag).
xfill's leaf budget enforces it per-leaf; the *root knapsack* relaxes bridges to free. So
adding "stub tiles <= total_bag - W - B" to the root knapsack is a sound tightening: every
legal board uses >= B bridge tiles, hence <= total_bag - W - B stub tiles.
"""
import sys, os, json, pickle, time, math, argparse
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'experiments'))

from scrabble import construct_rules, get_word_score
from connectivity import min_bridge_cells, setup_fixed_cells

CERT = os.path.join(ROOT, 'experiments/results/certs/n11_fixed_221')
VERD = os.path.join(CERT, 'verdicts.jsonl')
FLOOR = 226
BOARD, MAIN, TURN = '11', 'bouwfysicus', 'BOUWfYsiCuS'


def make_rules():
    rules = construct_rules('dutch', BOARD)
    f = (rules.W * rules.W) / (15 * 15)
    mt = rules.alphabet.to_tup(MAIN)
    mc = Counter(mt)
    rules.counts = Counter({c: max(round(n * f), mc[c], 1) for c, n in rules.counts.items()})
    rules.blank_count = round(rules.blank_count * f)
    return rules


def derive_knap_lists(rules):
    """Per-(col,len) Pareto-pruned candidate lists [(gross, Counter(stub letters))], + best_at,
    + avail (bag minus newly-placed main tiles).  Same semantics as 35_certify.derive_knap_lists
    and derive_columns."""
    W, H = rules.W, rules.H
    mt = rules.alphabet.to_tup(MAIN)
    scoring = [x for x in range(W) if TURN[x].isupper()]
    lists = {c: {} for c in scoring}
    best_at = {c: {} for c in scoring}
    for c in scoring:
        L = mt[c]
        byl = {}
        for w in rules.words:
            if not w or w[0] != L or len(w) > H:
                continue
            if len(w) > 1 and w[1:] not in rules.words_lookup:
                continue
            g = 0 if len(w) == 1 else int(get_word_score(rules, w, c, 0, 0,
                                          [i == 0 for i in range(len(w))])[0])
            byl.setdefault(len(w), []).append((g, Counter(w[1:])))
            if g > best_at[c].get(len(w), -1):
                best_at[c][len(w)] = g
        for l, items in byl.items():
            items.sort(key=lambda t: (-t[0], sum(t[1].values())))
            kept = []
            for g, rq in items:
                if not any(g2 >= g and all(rq2[k] <= rq.get(k, 0) for k in rq2)
                           for g2, rq2 in kept):
                    kept.append((g, rq))
            lists[c][l] = kept
    newly = Counter(mt[c] for c in scoring)
    avail = {code: rules.counts[code] - newly[code] for code in rules.counts}
    return scoring, lists, best_at, avail, mt


def knap_ub(rules, items_per_col, avail, blanks, floor, total_cap=None, step_cap=300_000):
    """Multiple-choice knapsack UPPER bound (pure python, matches xfill knap_ub / exp32 semantics).
    items_per_col: list over columns of [(gross, Counter(stub usage)), ...] (sorted desc by gross).
    avail: dict code->available count in bag (after main tiles).
    blanks: number of blank tiles (overflow allowance, charged at face value -- an UNDER-charge,
            so sound).
    total_cap: if set, ALSO require sum(all stub tiles placed) <= total_cap (the proposed coupling).
    Returns the max achievable (gross - blank_penalty) over one-word-per-column choices that fit
    the per-letter budget (overflow<=blanks) and the optional total cap.  We compute the true
    optimum of this relaxation via branch-and-bound (small: <=7 cols, Pareto lists are short)."""
    m = len(items_per_col)
    # order columns by ascending domain size (branch most-constrained first)
    order = sorted(range(m), key=lambda k: len(items_per_col[k]))
    cols = [items_per_col[k] for k in order]
    # suffix best gross for bound
    suf = [0] * (m + 1)
    for k in range(m - 1, -1, -1):
        suf[k] = suf[k + 1] + (cols[k][0][0] if cols[k] else 0)
    a = max(rules.counts) if rules.counts else 0
    base_avail = [avail.get(c, 0) for c in range(a + 1)]
    best = [floor]   # we only care whether/how far it beats floor; track true max though

    # We must MAXIMIZE gross - penalty. penalty = scores charged for blanked over-uses.
    # For an UPPER bound matching xfill: penalty under-charge = face value of overflow tiles.
    # To keep it a faithful knapsack we track per-code usage and compute penalty at the leaf.
    scores = rules.scores

    sys.setrecursionlimit(10000)
    extra = [0] * (a + 1)
    # GREEDY feasible incumbent: take each column's lowest-tile-usage candidate (last in the
    # Pareto list is fewest tiles for its gross); compute its feasible value to seed best_val so
    # the suffix prune bites from the start.  Any feasible value is a valid lower seed.
    def feasible_value(choice):
        ex = [0] * (a + 1); g = 0
        for c in choice:
            g += c[0]
            for code, cnt in c[1].items():
                ex[code] += cnt
        ot = 0; pen = 0
        for code in range(1, a + 1):
            ov = ex[code] - base_avail[code]
            if ov > 0:
                ot += ov; pen += ov * scores.get(code, 0)
        if ot > blanks:
            return None
        if total_cap is not None and sum(sum(c[1].values()) for c in choice) > total_cap:
            return None
        return g - pen
    seed = None
    # try the fewest-tile word per column (Pareto list sorted by -gross then +tiles, so min tiles
    # is at the tail of equal-gross groups; scan all to find a cheap feasible combo greedily)
    greedy = []
    for col in cols:
        # pick the candidate minimizing tile usage (most budget-friendly)
        greedy.append(min(col, key=lambda e: sum(e[1].values())))
    fv = feasible_value(greedy)
    best_val = [fv if fv is not None else -10**9]
    steps = [step_cap]             # sound step cap: on exhaustion return the optimistic suffix UB
    exhausted = [False]

    def rec(ki, cur_g, cur_total):
        steps[0] -= 1
        if steps[0] < 0:
            exhausted[0] = True
            return
        # optimistic: cur_g + suffix best, minus 0 penalty
        if cur_g + suf[ki] <= best_val[0]:
            return
        if ki == m:
            # compute overflow penalty
            over_total = 0
            pen = 0
            for code in range(1, a + 1):
                ov = extra[code] - base_avail[code]
                if ov > 0:
                    over_total += ov
                    pen += ov * scores.get(code, 0)
            if over_total > blanks:
                return
            val = cur_g - pen
            if val > best_val[0]:
                best_val[0] = val
            return
        for (g, rq) in cols[ki]:
            nt = cur_total + sum(rq.values())
            if total_cap is not None and nt > total_cap:
                continue
            if cur_g + g + suf[ki + 1] <= best_val[0]:
                break
            for code, cnt in rq.items():
                extra[code] += cnt
            rec(ki + 1, cur_g + g, nt)
            for code, cnt in rq.items():
                extra[code] -= cnt

    rec(0, 0, 0)
    if exhausted[0]:
        # sound fallback: the optimistic gross-only suffix sum bounds the true knapsack max.
        return suf[0], True
    return best_val[0], False


def cpsat_bounds(rules, items, avail, blanks, B, cap=20.0):
    """Exact tile-knapsack UPPER bounds via CP-SAT (the VALIDATED model from 35_certify.knap_verdict).
    Returns (cur, agg, ideal):
      cur   = current root knapsack: per-letter bag budget `avail`, blank overflow penalized. IGNORES
              bridges (== xfill's knap_ub relaxation == the certifier's Pass B).  SOUND UB.
      agg   = + AGGREGATE coupling: reserve B generic tiles -> sum(all stub tiles) <= sum(avail)-B.
              SOUND UB (every legal board places >= B bridge tiles from the same bag).
      ideal = OPTIMISTIC per-letter coupling = an aggressive, generally-UNSOUND estimate of the BEST
              POSSIBLE tightening any connectivity-coupled tile bound could achieve: take cur's
              optimal stub solution, then pretend the B forced bridge tiles are stolen from the
              HIGHEST-VALUE letters that solution uses (reduce those letters' availability by B units,
              most-valuable first) and re-solve.  This over-states the coupling's power (bridges need
              NOT use those letters); if even `ideal` rarely drops below floor, no sound coupling can."""
    from ortools.sat.python import cp_model
    scoring_codes = list(rules.counts)
    ncols = len(items)

    def build(avail_eff, agg_reserve):
        m = cp_model.CpModel()
        xv = {}
        for ci in range(ncols):
            vs = [m.new_bool_var(f'x{ci}_{i}') for i in range(len(items[ci]))]
            for i, v in enumerate(vs):
                xv[(ci, i)] = v
            m.add(sum(vs) == 1)
        over = {c: m.new_int_var(0, blanks, f'o{c}') for c in scoring_codes} if blanks else {}
        if over:
            m.add(sum(over.values()) <= blanks)
        pen = 0
        all_usage = []
        for code in scoring_codes:
            usage = [xv[(ci, i)] * rq[code]
                     for ci in range(ncols) for i, (g, rq) in enumerate(items[ci]) if rq.get(code, 0)]
            all_usage += usage
            if usage:
                m.add(sum(usage) - over.get(code, 0) <= avail_eff[code])
            if code in over:
                pen = pen + over[code] * rules.scores[code]
        if agg_reserve is not None:
            m.add(sum(all_usage) <= agg_reserve)
        m.maximize(sum(xv[(ci, i)] * g for ci in range(ncols)
                       for i, (g, rq) in enumerate(items[ci])) - pen)
        return m, xv

    def solve(m):
        s = cp_model.CpSolver()
        s.parameters.num_search_workers = 1
        s.parameters.max_time_in_seconds = cap
        st = s.solve(m)
        return int(math.floor(s.best_objective_bound + 1e-6)), s, st   # sound UB even on cap-hit

    total_avail = sum(avail[c] for c in scoring_codes)
    m_cur, xv_cur = build(avail, None)
    cur, s_cur, st_cur = solve(m_cur)
    m_agg, _ = build(avail, total_avail - B)
    agg, _, _ = solve(m_agg)

    # ideal: read cur's chosen words -> letter usage; steal B tiles from highest-value used letters.
    avail_eff = dict(avail)
    if st_cur in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        used = {c: 0 for c in scoring_codes}
        for ci in range(ncols):
            for i, (g, rq) in enumerate(items[ci]):
                if s_cur.value(xv_cur[(ci, i)]):
                    for code, cnt in rq.items():
                        used[code] = used.get(code, 0) + cnt
        # steal B units from the highest-scoring letters actually used (most damaging to objective)
        remaining = B
        for code in sorted(scoring_codes, key=lambda c: -rules.scores[c]):
            if remaining <= 0:
                break
            take = min(remaining, used.get(code, 0))
            avail_eff[code] = avail[code] - take
            remaining -= take
    m_id, _ = build(avail_eff, None)
    ideal, _, _ = solve(m_id)
    return cur, agg, ideal


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sample', type=int, default=600, help='hard vectors to sample')
    ap.add_argument('--top', type=int, default=20, help='of those, take the N hardest (may exhaust)')
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--hard-pkl', default='/tmp/hard.pkl')
    args = ap.parse_args()

    rules = make_rules()
    W, H = rules.W, rules.H
    total_bag = sum(rules.counts.values()) + rules.blank_count
    scoring, lists, best_at, avail, mt = derive_knap_lists(rules)
    print(f'[setup] W={W} H={H} total_bag={total_bag} blanks={rules.blank_count} '
          f'scoring_cols={scoring} floor={FLOOR}')

    hard = pickle.load(open(args.hard_pkl, 'rb'))   # [(time, nodes, key), ...] desc
    # stratified sample: a few of the very hardest (cost-bearing tail; these may exhaust the
    # python knapsack -> flagged) + a UNIFORM sample of the >1s slice (where the knapsack
    # completes fast, giving the meaningful tightening measurement).
    import random
    random.seed(args.seed)
    n = min(args.sample, len(hard))
    ntop = min(args.top, n)
    top = hard[:ntop]
    rest = random.sample(hard[ntop:], min(n - ntop, len(hard) - ntop))
    samp = top + rest
    print(f'[sample] {len(samp)} hard vectors (top {len(top)} hardest + {len(rest)} uniform); '
          f'hard slice total = {len(hard)}', flush=True)

    # blank/center note: floor 226 was certified UNCONSTRAINED (n11_fixed_221). Connectivity
    # bridge LB does NOT require center here (center is the n11_center variant). We still get a
    # legitimate connectivity reserve from the multi-component Steiner bound.

    rows = []
    t0 = time.time()
    for vi, (tm, nd, key) in enumerate(samp):
        if vi % 25 == 0:
            print(f'  [compute] {vi}/{len(samp)} ({time.time()-t0:.0f}s)', flush=True)
        lvec = list(map(int, key.split('-')))
        Lvec = {c: lvec[i] for i, c in enumerate(scoring)}
        items = [lists[c].get(Lvec[c], []) for c in scoring]
        if any(not it for it in items):
            continue  # NOCAND (shouldn't happen for LE vectors)
        stub_tiles = sum(l - 1 for l in lvec)
        budget_bridge = total_bag - W - stub_tiles    # tiles available for bridges (>=0 for LE vecs)

        # cheap sum UB (xfill's loosest bound: per-col best gross, no budget at all)
        sum_ub = sum(best_at[c][Lvec[c]] for c in scoring)

        # Steiner bridge lower bound (connectivity-forced bridge tiles)
        fx = setup_fixed_cells(W, H, TURN, mt, {c: tuple([0] * Lvec[c]) for c in scoring})
        B, exact = min_bridge_cells(fx, W, H)

        # exact tile-knapsack UBs (CP-SAT, validated model): current / aggregate-coupled / ideal-coupled
        knap_cur, knap_agg, knap_ideal = cpsat_bounds(
            rules, items, avail, rules.blank_count, B)

        rows.append({
            'key': key, 'xfill_time': tm, 'xfill_nodes': nd,
            'stub_tiles': stub_tiles, 'budget_bridge': budget_bridge,
            'steiner_B': B, 'steiner_exact': exact,
            'sum_ub': sum_ub, 'knap_cur': knap_cur,
            'knap_agg': knap_agg, 'knap_ideal': knap_ideal,
            'cap_slack': budget_bridge - B,   # >=0 for any GEOM-surviving (hence LE) vector
        })
    el = time.time() - t0
    print(f'[compute] {len(rows)} vectors in {el:.1f}s ({el/max(len(rows),1)*1000:.1f}ms/vec)')

    report(rows, total_bag, W, hard, len(samp))


def report(rows, total_bag, W, hard, nsamp):
    import statistics as st
    lines = []
    def p(s=''):
        print(s); lines.append(s)

    p('# Bound study: connectivity/Steiner-coupled tile reservation on the hard N=11 slice')
    p()
    p(f'Claim: bouwfysicus N=11, floor={FLOOR}, total scaled bag={total_bag}, main W={W}.')
    p(f'Hard slice (xfill LE with time>1s) = {len(hard)} vectors; sampled {nsamp}, '
      f'computed {len(rows)}.')
    p()
    p('Three EXACT tile-knapsack upper bounds per vector (CP-SAT, the validated 35_certify model):')
    p('  knap_cur   = current root bound (per-letter bag budget, blank-penalized). IGNORES bridges')
    p('               -- identical relaxation to xfill knap_ub and the certifier\'s Pass B.')
    p('  knap_agg   = + AGGREGATE coupling: reserve B generic tiles (sum stub tiles <= sum_avail-B).')
    p('  knap_ideal = + OPTIMISTIC per-letter coupling: the solver may subtract B tile-units from')
    p('               whichever letters hurt the objective MOST (an UNSOUND over-estimate that')
    p('               upper-bounds the BEST POSSIBLE tightening any connectivity-coupled tile bound')
    p('               could ever achieve). If even knap_ideal seldom drops below floor, no SOUND')
    p('               connectivity-tile bound can help this slice.')
    p()

    cur_le = sum(1 for r in rows if r['knap_cur'] <= FLOOR)
    agg_le = sum(1 for r in rows if r['knap_agg'] <= FLOOR)
    ideal_le = sum(1 for r in rows if r['knap_ideal'] <= FLOOR)
    newly_agg = sum(1 for r in rows if r['knap_cur'] > FLOOR and r['knap_agg'] <= FLOOR)
    newly_ideal = sum(1 for r in rows if r['knap_cur'] > FLOOR and r['knap_ideal'] <= FLOOR)
    nr = len(rows)
    p('## Pruning at the root (fraction with UB <= floor)')
    p(f'- knap_cur  <= floor: {cur_le}/{nr} = {100*cur_le/nr:.1f}%   '
      f'(== certifier Pass B; memory: "knap pass B cut 0 on N=11")')
    p(f'- knap_agg  <= floor: {agg_le}/{nr} = {100*agg_le/nr:.1f}%   '
      f'(NEWLY pruned vs cur: {newly_agg} = {100*newly_agg/nr:.1f}%)')
    p(f'- knap_ideal<= floor: {ideal_le}/{nr} = {100*ideal_le/nr:.1f}%   '
      f'(NEWLY pruned vs cur: {newly_ideal} = {100*newly_ideal/nr:.1f}%)  [OPTIMISTIC ceiling]')
    p()
    p(f'SIDE FINDING (not the bridge coupling): {cur_le}/{nr} = {100*cur_le/nr:.1f}% of these hard '
      f'LE vectors have an EXACT per-letter knapsack UB already <= floor. xfill spent >1s on each '
      f'anyway, so its ROOT knapsack (bounded-greedy KNAPSTEPS, run before the deep search) is '
      f'LOOSER than the exact one and missed these. Running the exact CP-SAT knapsack (the '
      f'certifier\'s Pass B model) at the ROOT -- not the bridge coupling -- is the real cheap win '
      f'this sample reveals. (Pass B "cut 0" because it only sees pass-A 2s-wall TO survivors, a '
      f'DIFFERENT/harder population than these 1-2s LE vectors.)')
    p()

    da = [r['knap_cur'] - r['knap_agg'] for r in rows]
    di = [r['knap_cur'] - r['knap_ideal'] for r in rows]
    p('## Tightening of the UB (knap_cur - coupled)')
    p(f'- AGGREGATE coupling: tightened {sum(1 for d in da if d>0)}/{nr} vectors; '
      f'mean {st.mean(da):.2f} pts (max {max(da)}).')
    p(f'- IDEAL coupling:     tightened {sum(1 for d in di if d>0)}/{nr} vectors; '
      f'mean {st.mean(di):.2f} pts (max {max(di)}).  [optimistic ceiling]')
    p(f'- gap of cur above floor: mean {st.mean([r["knap_cur"]-FLOOR for r in rows]):.1f} pts, '
      f'min {min(r["knap_cur"]-FLOOR for r in rows)} '
      f'(how far each vector\'s UB sits ABOVE the floor -- the coupling must close this).')
    p()

    cs = [r['cap_slack'] for r in rows]
    p('## Why: the aggregate cap is provably vacuous on the hard slice')
    p(f'- cap_slack = budget_bridge - B = (tiles available for bridges) - (Steiner min bridges).')
    p(f'- For ANY vector that survived GEOM (a precondition to becoming a hard LE vector), '
      f'budget_bridge >= B, so cap_slack >= 0 ALWAYS. The aggregate reserve sum(stub)<=sum_avail-B '
      f'is then already implied by GEOM + the bag identity, hence adds nothing.')
    p(f'- measured cap_slack on sample: min={min(cs)} median={int(st.median(cs))} max={max(cs)} '
      f'mean={st.mean(cs):.1f}; vectors with cap_slack<0: {sum(1 for c in cs if c<0)}.')
    p()
    p('  KEY INSIGHT: the knapsack is gated by PER-LETTER scarcity, not the aggregate tile count. '
      'A Steiner bound yields only a COUNT B of forced bridge tiles, not WHICH letters they use; '
      'bridges may legally use the most abundant letters (scaled Dutch bag has slack -- E=10, plus '
      'a blank), so no specific letter\'s availability provably drops. The only sound count-based '
      'coupling is the aggregate one, and that is implied by GEOM. The IDEAL column above shows '
      'the absolute CEILING even if (unsoundly) bridges could be forced onto the worst letters.')
    p()

    Bs = [r['steiner_B'] for r in rows]
    p('## Steiner bridge lower bound B on the sample')
    p(f'- B: min={min(Bs)} median={int(st.median(Bs))} max={max(Bs)} mean={st.mean(Bs):.1f}; '
      f'exact={sum(1 for r in rows if r["steiner_exact"])}/{nr}')
    p(f'- budget_bridge: min={min(r["budget_bridge"] for r in rows)} '
      f'max={max(r["budget_bridge"] for r in rows)}')
    p()

    samp_time = sum(r['xfill_time'] for r in rows)
    saved_agg = sum(r['xfill_time'] for r in rows
                    if r['knap_cur'] > FLOOR and r['knap_agg'] <= FLOOR)
    saved_ideal = sum(r['xfill_time'] for r in rows
                      if r['knap_cur'] > FLOOR and r['knap_ideal'] <= FLOOR)
    p('## Estimated core-hour impact (hard slice ~= 457 core-h = 82% of the 557 core-h N=11 run)')
    p(f'- sampled xfill time = {samp_time:.0f}s.')
    p(f'- SOUND aggregate coupling would save ~{100*saved_agg/max(samp_time,1):.1f}% of slice time '
      f'= ~{457*saved_agg/max(samp_time,1):.0f} core-h.')
    p(f'- OPTIMISTIC ideal coupling ceiling: ~{100*saved_ideal/max(samp_time,1):.1f}% '
      f'= ~{457*saved_ideal/max(samp_time,1):.0f} core-h (UNSOUND upper estimate).')
    p()

    p('## RECOMMENDATION')
    frac_agg = saved_agg / max(samp_time, 1)
    if newly_agg >= 0.10 * nr or frac_agg >= 0.10:
        p(f'GREENLIGHT (conditional): the SOUND coupling prunes {100*newly_agg/nr:.1f}% of the hard '
          f'slice / {100*frac_agg:.1f}% of its time. Worth prototyping in Rust as a root-only bound '
          f'(Lever 4/7), behind a flag with byte-identical verdicts A/B.')
    else:
        p(f'DO NOT BUILD (negative result). The SOUND Steiner-coupled tile reservation prunes '
          f'{100*newly_agg/nr:.1f}% of the hard slice (0 expected: the aggregate reserve is implied '
          f'by GEOM, cap_slack>=0 always). Even the OPTIMISTIC ceiling (knap_ideal, an UNSOUND '
          f'over-estimate that lets bridges steal the worst letters) prunes only '
          f'{100*newly_ideal/nr:.1f}% -- because the per-letter knapsack UB sits a mean '
          f'{st.mean([r["knap_cur"]-FLOOR for r in rows]):.0f} points ABOVE the floor on this slice, '
          f'far more than B={int(st.mean(Bs))} reserved tiles could ever erase. A Steiner COUNT '
          f'gives no per-letter information, and bridges can draw from abundant letters, so no sound '
          f'connectivity-coupled TILE bound tightens this slice. Lever 4 is correctly DEFERRED; this '
          f'confirms it empirically. The real lever is the TWOLEVEL structural cut (item 6) -- '
          f'word-combo B&B with per-combo bridge feasibility -- which attacks the per-node knapsack '
          f'cost (88.8% of runtime) rather than the root bound value.')
    p()

    outp = os.path.join(ROOT, 'experiments/results/bound_study_report.md')
    with open(outp, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print(f'\n[wrote] {outp}')

    # also dump per-vector rows for inspection
    jp = os.path.join(ROOT, 'experiments/results/bound_study_rows.jsonl')
    with open(jp, 'w') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')
    print(f'[wrote] {jp}')


if __name__ == '__main__':
    main()
