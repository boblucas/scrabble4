"""
Test harness for the custom crossword-fill connectivity solver.

Builds DECISION instances ("does a legal connected setup board exist for this length-vector?"),
gets CP-SAT ground truth (small boards decide fast), dumps JSON the Rust solver reads, and compares.

Instance facts baked in (see the long analysis): bridges can live ONLY in non-scoring (pre-placed)
columns at rows 1..H-1 (scoring columns are exactly their stub word, empty below). Scoring vertical
runs are validated by the per-column word-domain; only <=HMAX cross-words are checked against `dict`.

Usage:
  python experiments/xtest.py gen           # generate small test instances + ground truth -> tests/*.json
  python experiments/xtest.py truth FILE    # print CP-SAT ground truth for an instance json
"""
import sys, os, json, time
from collections import Counter
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, 'experiments')
from scrabble import construct_rules, get_word_score
from dawg import position_independent_row_automaton
from solve import create_board, single_component, limit_letter_count
from ortools.sat.python import cp_model

HMAX = 8
TESTDIR = 'experiments/xtests'


def build_instance(board, main, turn, Lvec, scale=True):
    """Return (instance_dict, meta). instance_dict is JSON-serializable for the Rust solver."""
    rules = construct_rules('dutch', board)
    W, H = rules.W, rules.H
    mt = rules.alphabet.to_tup(main)
    assert len(main) == W == len(turn)
    counts = Counter(rules.counts); blanks = rules.blank_count
    if scale:
        f = (W * W) / (15 * 15); mc = Counter(mt)
        counts = Counter({c: max(round(n * f), mc[c], 1) for c, n in rules.counts.items()})
        blanks = round(rules.blank_count * f)
    scoring = [x for x in range(W) if turn[x].isupper()]
    pre = [x for x in range(W) if not turn[x].isupper()]
    # candidate stub words (w[1:]) per scoring column, of the fixed length.
    # Each candidate also carries grossV = the word's VERTICAL score (only the row-0 tile gets the
    # board multipliers, matching 31_length_level.inner_best_legal: placed=[i==0...]). All candidates
    # of a column share the same row-0 letter (mt[c]), so dedup by stub is safe (same stub => same word
    # => same grossV).
    doms = {}
    for c in scoring:
        L = mt[c]; seen = set(); out = []
        for w in rules.words:
            if w and w[0] == L and len(w) == Lvec[c] and (len(w) == 1 or w[1:] in rules.words_lookup):
                stub = tuple(w[1:])
                if stub in seen:
                    continue
                seen.add(stub)
                # SCORING FIX: a length-1 "word" is the bare placed tile (construct_rules injects all
                # single letters into rules.words).  It forms NO vertical word and its value already
                # counts in the MAIN word; get_word_score on it would double-count value*lm*wm.  This
                # gross feeds the Rust inner's MAX values, so a phantom here INFLATES witnessed lower
                # bounds for any vector using an l=1 column.  l=1 stays available, contributing 0.
                sc = 0 if len(w) == 1 else int(get_word_score(rules, w, c, 0, 0,
                                                              [i == 0 for i in range(len(w))])[0])
                out.append((stub, sc))
        doms[c] = out
        if not out:
            return None, None                          # no candidate of this length -> skip
    inst = {
        'W': W, 'H': H, 'hmax': HMAX,
        'preplaced': [[x, 0, mt[x]] for x in pre],
        # 'wm' = the column's row-0 WORD multiplier: the vertical word's multiplier (it comes from
        # the newly placed row-0 tile) applies to ALL its cells, so blanking a stub cell costs
        # value*wm, not bare value.  The solver needs wm for a sound blank penalty.
        'scoring': [{'col': c, 'len': Lvec[c], 'wm': int(rules.word_multiplier[0][c]),
                     'words': [list(s) for s, _ in doms[c]],
                     'gross': [g for _, g in doms[c]]} for c in scoring],
        'nonscoring_cols': pre,
        'alphabet_size': len(rules.abc),
        # available for SETUP cells = bag minus the main tiles newly placed at scoring columns
        'counts': {str(code): counts[code] - Counter(mt[c] for c in scoring)[code] for code in counts},
        # face value per letter code (for the blank penalty: a blanked stub tile scores 0)
        'scores': {str(code): rules.scores[code] for code in rules.scores},
        'blanks': blanks,
        'dict_path': f'experiments/xtests/dict_{board}.txt',     # shared <=HMAX word list (codes)
    }
    meta = dict(board=board, main=main, turn=turn, Lvec=Lvec, rules=rules,
                scoring=scoring, pre=pre, counts=counts, blanks=blanks, mt=mt)
    return inst, meta


def cpsat_decide(meta, cap=120.0):
    """Ground truth: does a legal connected setup board exist for these fixed lengths? (no objective)"""
    rules, W, H = meta['rules'], meta['rules'].W, meta['rules'].H
    mt, scoring, pre, Lvec = meta['mt'], meta['scoring'], meta['pre'], meta['Lvec']
    counts, blanks = meta['counts'], meta['blanks']
    m = cp_model.CpModel(); m.prefix = 'g'
    row_aut = position_independent_row_automaton([w for w in rules.words if len(w) <= HMAX])
    cols = [row_aut if x not in scoring else None for x in range(W)]
    cells = create_board(m, [row_aut] * H, cols, alphabet_size=len(rules.abc))
    for x in pre:
        m.add(cells[(x, 0)].letter[mt[x]] == 1)
    for x in scoring:
        m.add(cells[(x, 0)].active == 0)
    for c in scoring:
        words = [tuple(w[1:]) for w in rules.words
                 if w and w[0] == mt[c] and len(w) == Lvec[c] and (len(w) == 1 or w[1:] in rules.words_lookup)]
        words = list(dict.fromkeys(words))
        xs = []
        for i, stub in enumerate(words):
            v = m.new_bool_var(f'x_{c}_{i}'); xs.append(v)
            for r in range(1, Lvec[c]):
                m.add(cells[(c, r)].letter[stub[r - 1]] == 1).only_enforce_if(v)
            for r in range(Lvec[c], H):
                m.add(cells[(c, r)].active == 0).only_enforce_if(v)
        m.add(sum(xs) == 1)
    newly = Counter(mt[c] for c in scoring)
    limit_letter_count(m, cells, Counter({code: counts[code] - newly[code] for code in counts}))
    m.add(sum(cell.blank for cell in cells.values()) <= blanks)   # ALWAYS (blanks==0 forbids all blanks)
    if pre:
        single_component(m, cells, (pre[0], 0))
    s = cp_model.CpSolver(); s.parameters.num_search_workers = 24; s.parameters.max_presolve_iterations = 1
    s.parameters.max_time_in_seconds = cap
    r = s.Solve(m)
    return {cp_model.OPTIMAL: 'SAT', cp_model.FEASIBLE: 'SAT', cp_model.INFEASIBLE: 'UNSAT'}.get(r, 'UNKNOWN')


def cpsat_maxscore(meta, cap=180.0):
    """Ground truth for --maxscore: the MAXIMUM vertical score (grossV - blank penalty) over all legal
    connected boards for these fixed lengths. Mirrors 31_length_level.inner_best_legal with floor=-1
    (full maximize). Returns (status, score) where status in OPTIMAL/INFEASIBLE/UNKNOWN; score is the
    optimal int objective (None if not OPTIMAL)."""
    rules, W, H = meta['rules'], meta['rules'].W, meta['rules'].H
    mt, scoring, pre, Lvec = meta['mt'], meta['scoring'], meta['pre'], meta['Lvec']
    counts, blanks = meta['counts'], meta['blanks']
    m = cp_model.CpModel(); m.prefix = 'i'
    row_aut = position_independent_row_automaton([w for w in rules.words if len(w) <= HMAX])
    cols = [row_aut if x not in scoring else None for x in range(W)]
    cells = create_board(m, [row_aut] * H, cols, alphabet_size=len(rules.abc))
    for x in pre:
        m.add(cells[(x, 0)].letter[mt[x]] == 1)
    for x in scoring:
        m.add(cells[(x, 0)].active == 0)
    xv = {}; items = {}
    for c in scoring:
        words = []
        for w in rules.words:
            if w and w[0] == mt[c] and len(w) == Lvec[c] and (len(w) == 1 or w[1:] in rules.words_lookup):
                words.append(w)
        # dedup identical stubs (same stub => same full word => same gross); keep full word for score
        seen = set(); uniq = []
        for w in words:
            stub = tuple(w[1:])
            if stub in seen: continue
            seen.add(stub); uniq.append(w)
        its = []
        for w in uniq:
            # SCORING FIX (same as build_instance): a length-1 "word" is the bare placed tile --
            # no vertical word exists, value already counted in the main word -> gross 0.
            sc = 0 if len(w) == 1 else int(get_word_score(rules, w, c, 0, 0,
                                                          [i == 0 for i in range(len(w))])[0])
            its.append((tuple(w[1:]), sc))
        items[c] = its
        vs = []
        for i, (stub, sc) in enumerate(its):
            v = m.new_bool_var(f'x_{c}_{i}'); xv[(c, i)] = v; vs.append(v)
            for r in range(1, Lvec[c]):
                m.add(cells[(c, r)].letter[stub[r - 1]] == 1).only_enforce_if(v)
            for r in range(Lvec[c], H):
                m.add(cells[(c, r)].active == 0).only_enforce_if(v)
        m.add(sum(vs) == 1)
    newly = Counter(mt[c] for c in scoring)
    limit_letter_count(m, cells, Counter({code: counts[code] - newly[code] for code in counts}))
    penalty = 0
    if blanks:
        m.add(sum(cell.blank for cell in cells.values()) <= blanks)
        # PENALTY FIX: the vertical word's WORD multiplier (from its newly placed row-0 tile)
        # applies to every cell of the word, so blanking a stub cell at (c,r) loses
        # value * word_multiplier[0][c] from the turn -- not bare value.  (The old face-value
        # penalty UNDERSTATED the loss in wm>1 columns: the bouwfysicus "224" board really
        # scores 216 -- blanking the struggelden 'u' under col10's x3 costs 12, not 4.)
        for code in counts:
            for c in scoring:
                wm = int(rules.word_multiplier[0][c])
                for r in range(1, H):
                    cell = cells[(c, r)]
                    b = m.new_bool_var(f'blk_{c}_{r}_{code}')
                    m.add(b <= cell.blank); m.add(b <= cell.letter[code]); m.add(b >= cell.blank + cell.letter[code] - 1)
                    penalty = penalty + b * (rules.scores[code] * wm)
    else:
        m.add(sum(cell.blank for cell in cells.values()) <= 0)
    if pre:
        single_component(m, cells, (pre[0], 0))
    obj = sum(xv[(c, i)] * sc for c in scoring for i, (stub, sc) in enumerate(items[c])) - penalty
    m.maximize(obj)
    s = cp_model.CpSolver(); s.parameters.num_search_workers = 24; s.parameters.max_presolve_iterations = 1
    s.parameters.max_time_in_seconds = cap
    r = s.Solve(m)
    if r == cp_model.OPTIMAL:
        return 'OPTIMAL', int(s.objective_value)
    if r == cp_model.INFEASIBLE:
        return 'INFEASIBLE', None
    if r == cp_model.FEASIBLE:
        return 'FEASIBLE', int(s.objective_value)
    return 'UNKNOWN', None


def dump_simple(inst, truth, path):
    """Dead-simple line format the Rust solver parses with split_whitespace."""
    L = []
    L.append(f"DIMS {inst['W']} {inst['H']} {inst['hmax']} {inst['alphabet_size']} {inst['blanks']}")
    L.append("COUNTS " + ' '.join(f"{k}:{v}" for k, v in inst['counts'].items()))
    L.append("SCORES " + ' '.join(f"{k}:{v}" for k, v in inst.get('scores', {}).items()))
    L.append("PREPLACED " + ' '.join(f"{x},{y},{c}" for x, y, c in inst['preplaced']))
    L.append("NONSCORING " + ' '.join(map(str, inst['nonscoring_cols'])))
    L.append(f"DICT {inst['dict_path']}")
    L.append(f"NSCORING {len(inst['scoring'])}")
    for blk in inst['scoring']:
        # 4th SCOL token = the column's row-0 word multiplier (blank-penalty weight).  The Rust
        # parser defaults it to 1 when absent, so legacy instance files keep their old semantics.
        L.append(f"SCOL {blk['col']} {blk['len']} {len(blk['words'])} {blk.get('wm', 1)}")
        gross = blk.get('gross', [0] * len(blk['words']))
        for w, g in zip(blk['words'], gross):
            # WORDV carries the vertical score as the first token (for --maxscore); the Rust solver
            # also still accepts the legacy "WORD <codes...>" form (gross defaults to 0, decision-only).
            L.append(f"WORDV {g} " + ' '.join(map(str, w)))
    L.append(f"TRUTH {truth}")
    with open(path, 'w') as fp:
        fp.write('\n'.join(L) + '\n')


def write_dict(board):
    rules = construct_rules('dutch', board)
    path = os.path.join(TESTDIR, f'dict_{board}.txt')
    with open(path, 'w') as fp:
        for w in rules.words:
            if 1 <= len(w) <= HMAX:
                fp.write(' '.join(map(str, w)) + '\n')
    print(f"wrote dict {path}")


def gen():
    os.makedirs(TESTDIR, exist_ok=True)
    write_dict('7')
    rules7 = construct_rules('dutch', '7')
    sevens = [rules7.alphabet.to_str(w) for w in rules7.words if len(w) == 7][:4000]
    # scoring at even cols, pre-placed at odd cols (non-adjacent -> isolated row-0 tiles, clean)
    turn = ''.join('A' if x % 2 == 0 else 'a' for x in range(7))   # placeholder; real letters below
    made = 0; idx = 0
    cases = []
    for word in sevens:
        if made >= 14:
            break
        idx += 1
        if idx % 3 != 0:        # sample
            continue
        ts = ''.join(word[x].upper() if x % 2 == 0 else word[x].lower() for x in range(7))
        scoring = [0, 2, 4, 6]
        # try a couple of length-vectors
        for Lset in [{0: 3, 2: 3, 4: 3, 6: 3}, {0: 4, 2: 2, 4: 5, 6: 3}, {0: 5, 2: 4, 4: 4, 6: 2}]:
            inst, meta = build_instance('7', word, ts, Lset, scale=False)   # full bag: more interesting
            if inst is None:
                continue
            t = time.time(); truth = cpsat_decide(meta, cap=60); dt = time.time() - t
            if truth == 'UNKNOWN':
                continue
            name = f"n7_{word}_{'-'.join(str(Lset[c]) for c in scoring)}"
            path = os.path.join(TESTDIR, name + '.txt')
            dump_simple(inst, truth, path)
            cases.append((name, truth, dt))
            print(f"  {name}: truth={truth} ({dt:.1f}s) -> {path}")
            made += 1
            if made >= 14:
                break
    print(f"\ngenerated {len(cases)} instances: {sum(1 for _,t,_ in cases if t=='SAT')} SAT, "
          f"{sum(1 for _,t,_ in cases if t=='UNSAT')} UNSAT")


def gen_hard():
    """Hunt UNSAT (and harder SAT) cases: scaled bag (tile-starved) on N=7, plus a few N=9."""
    os.makedirs(TESTDIR, exist_ok=True)
    write_dict('7'); write_dict('9')
    made = 0
    # N=7 scaled bag -> tile-starved; long stubs stress budget AND word legality
    rules7 = construct_rules('dutch', '7')
    sevens = [rules7.alphabet.to_str(w) for w in rules7.words if len(w) == 7]
    for word in sevens[::37]:
        if made >= 12: break
        ts = ''.join(word[x].upper() if x % 2 == 0 else word[x].lower() for x in range(7))
        for Lset in [{0: 6, 2: 6, 4: 6, 6: 6}, {0: 7, 2: 7, 4: 7, 6: 7}, {0: 5, 2: 6, 4: 7, 6: 5}]:
            inst, meta = build_instance('7', word, ts, Lset, scale=True)   # scaled -> tile-starved
            if inst is None: continue
            t = time.time(); truth = cpsat_decide(meta, cap=90); dt = time.time() - t
            if truth == 'UNKNOWN': continue
            name = f"h7_{word}_{'-'.join(str(Lset[c]) for c in [0,2,4,6])}"
            dump_simple(inst, truth, os.path.join(TESTDIR, name + '.txt'))
            print(f"  {name}: truth={truth} ({dt:.1f}s)"); made += 1
            if made >= 12: break
    print(f"generated {made} hard instances")


def gen_score():
    """Generate SCORE ground-truth instances (N=7 full + scaled bag, a few N=9). Each carries per-word
    grossV + SCORES, and a `TRUTH MAXSCORE <s>` (or `MAXSCORE_UNSAT`) line from cpsat_maxscore. These
    validate `xfill --maxscore` (Rust max MUST equal CP-SAT inner max). Files: experiments/xtests/s*.txt"""
    os.makedirs(TESTDIR, exist_ok=True)
    write_dict('7'); write_dict('9')
    made = 0
    rules7 = construct_rules('dutch', '7')
    sevens = [rules7.alphabet.to_str(w) for w in rules7.words if len(w) == 7]
    plan = []
    # full-bag N=7 (rich, mostly SAT): a spread of length-vectors over a sample of main words
    for word in sevens[::29][:8]:
        for Lset in [{0: 3, 2: 3, 4: 3, 6: 3}, {0: 4, 2: 2, 4: 5, 6: 3}, {0: 5, 2: 4, 4: 4, 6: 2}]:
            plan.append(('7', word, False, Lset, 'sf'))
    # scaled-bag N=7 (tile-starved -> blanks/penalty bite): exercises the penalty model
    for word in sevens[::53][:6]:
        for Lset in [{0: 5, 2: 6, 4: 7, 6: 5}, {0: 6, 2: 6, 4: 6, 6: 6}]:
            plan.append(('7', word, True, Lset, 'ss'))
    # a few N=9 (scoring at 0,2,4,6,8)
    rules9 = construct_rules('dutch', '9')
    nines = [rules9.alphabet.to_str(w) for w in rules9.words if len(w) == 9]
    for word in nines[::101][:4]:
        for Lset in [{0: 3, 2: 3, 4: 3, 6: 3, 8: 3}, {0: 4, 2: 3, 4: 5, 6: 3, 8: 4}]:
            plan.append(('9', word, True, Lset, 's9'))
    cases = []
    for board, word, scale, Lset, tag in plan:
        if made >= 40: break
        turn_letters = sorted(Lset.keys())
        ts = ''.join(word[x].upper() if x in turn_letters else word[x].lower() for x in range(len(word)))
        inst, meta = build_instance(board, word, ts, Lset, scale=scale)
        if inst is None: continue
        t = time.time(); status, score = cpsat_maxscore(meta, cap=120); dt = time.time() - t
        if status not in ('OPTIMAL', 'INFEASIBLE'):
            print(f"  skip {word} {Lset}: cpsat {status} ({dt:.1f}s)"); continue
        truth = f"MAXSCORE {score}" if status == 'OPTIMAL' else "MAXSCORE_UNSAT"
        name = f"{tag}_{board}_{word}_{'-'.join(str(Lset[c]) for c in turn_letters)}"
        path = os.path.join(TESTDIR, name + '.txt')
        dump_simple(inst, truth, path)
        cases.append((name, truth, dt))
        print(f"  {name}: {truth} ({dt:.1f}s) -> {path}"); made += 1
    print(f"\ngenerated {made} score instances")


def score_check():
    """Run `xfill --maxscore` on every s*.txt and assert the Rust MAX equals the CP-SAT TRUTH score
    (or both UNSAT). This is the soundness guard for the optimization."""
    import glob, subprocess
    BIN = 'experiments/xfill_rs/target/release/xfill'
    files = sorted(glob.glob(os.path.join(TESTDIR, 's*_*.txt')))
    npass = nfail = 0
    for f in files:
        truth_line = None
        for line in open(f):
            if line.startswith('TRUTH'):
                truth_line = line.strip(); break
        toks = truth_line.split() if truth_line else []
        if len(toks) >= 2 and toks[1] == 'MAXSCORE':
            want = ('MAX', int(toks[2]))
        elif len(toks) >= 2 and toks[1] == 'MAXSCORE_UNSAT':
            want = ('LE', -1)
        else:
            print(f"  {os.path.basename(f)}: no MAXSCORE truth, skip"); continue
        try:
            out = subprocess.run([BIN, f, '--maxscore', '-1'], capture_output=True, text=True,
                                 timeout=float(os.environ.get('XFILL_CAP', '30'))).stdout
        except subprocess.TimeoutExpired:
            out = 'TIMEOUT'
        verdict = out.split()[0] if out.split() else '?'
        if verdict == 'MAX':
            got = ('MAX', int(out.split()[1]))
        elif verdict == 'LE':
            got = ('LE', -1)
        else:
            got = (verdict, None)
        ok = (got == want)
        npass += ok; nfail += (not ok)
        flag = 'ok ' if ok else 'FAIL'
        print(f"  [{flag}] {os.path.basename(f):42s} want={want} got={got}  ({out.strip()})")
    print(f"\nscore-check: {npass}/{npass+nfail} pass" + (" -- ALL GOOD" if nfail == 0 else f" -- {nfail} FAIL"))
    return nfail == 0


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'gen'
    if cmd == 'gen':
        gen()
    elif cmd == 'genhard':
        gen_hard()
    elif cmd == 'genscore':
        gen_score()
    elif cmd == 'scorecheck':
        ok = score_check(); sys.exit(0 if ok else 1)
    elif cmd == 'dumpinst':
        # dumpinst <board> <main> <turn> <len0,len1,...for scoring cols in order> [scale]
        os.makedirs(TESTDIR, exist_ok=True)
        board, main, turn = sys.argv[2], sys.argv[3], sys.argv[4]
        lens = [int(x) for x in sys.argv[5].split(',')]
        scale = (len(sys.argv) > 6 and sys.argv[6] == 'scale')
        write_dict(board)
        scoring = [x for x in range(len(turn)) if turn[x].isupper()]
        Lvec = {c: lens[i] for i, c in enumerate(scoring)}
        inst, meta = build_instance(board, main, turn, Lvec, scale=scale)
        if inst is None:
            print("no candidates for some column at these lengths"); sys.exit(1)
        cap = int(sys.argv[7]) if len(sys.argv) > 7 else 0
        if cap:
            for blk in inst['scoring']:
                blk['words'] = blk['words'][:cap]
        name = f"r{board}_{main}_{'-'.join(map(str, lens))}{'_sc' if scale else ''}{'_cap'+str(cap) if cap else ''}"
        dump_simple(inst, 'UNKNOWN', os.path.join(TESTDIR, name + '.txt'))
        print(f"dumped {name} (scoring cols {scoring}, lens {lens}) -> {TESTDIR}/{name}.txt")
    elif cmd == 'truth':
        inst = json.load(open(sys.argv[2]))
        # rebuild meta from instance is non-trivial; ground truth is stored at gen time as _truth
        print(inst.get('_truth', '?'))
