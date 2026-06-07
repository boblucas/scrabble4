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
    # candidate stub words (w[1:]) per scoring column, of the fixed length
    doms = {}
    for c in scoring:
        L = mt[c]; out = []
        for w in rules.words:
            if w and w[0] == L and len(w) == Lvec[c] and (len(w) == 1 or w[1:] in rules.words_lookup):
                out.append(tuple(w[1:]))
        out = list(dict.fromkeys(out))                 # dedup identical stubs
        doms[c] = out
        if not out:
            return None, None                          # no candidate of this length -> skip
    inst = {
        'W': W, 'H': H, 'hmax': HMAX,
        'preplaced': [[x, 0, mt[x]] for x in pre],
        'scoring': [{'col': c, 'len': Lvec[c], 'words': [list(s) for s in doms[c]]} for c in scoring],
        'nonscoring_cols': pre,
        'alphabet_size': len(rules.abc),
        # available for SETUP cells = bag minus the main tiles newly placed at scoring columns
        'counts': {str(code): counts[code] - Counter(mt[c] for c in scoring)[code] for code in counts},
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
    if blanks:
        m.add(sum(cell.blank for cell in cells.values()) <= blanks)
    if pre:
        single_component(m, cells, (pre[0], 0))
    s = cp_model.CpSolver(); s.parameters.num_search_workers = 24; s.parameters.max_presolve_iterations = 1
    s.parameters.max_time_in_seconds = cap
    r = s.Solve(m)
    return {cp_model.OPTIMAL: 'SAT', cp_model.FEASIBLE: 'SAT', cp_model.INFEASIBLE: 'UNSAT'}.get(r, 'UNKNOWN')


def dump_simple(inst, truth, path):
    """Dead-simple line format the Rust solver parses with split_whitespace."""
    L = []
    L.append(f"DIMS {inst['W']} {inst['H']} {inst['hmax']} {inst['alphabet_size']} {inst['blanks']}")
    L.append("COUNTS " + ' '.join(f"{k}:{v}" for k, v in inst['counts'].items()))
    L.append("PREPLACED " + ' '.join(f"{x},{y},{c}" for x, y, c in inst['preplaced']))
    L.append("NONSCORING " + ' '.join(map(str, inst['nonscoring_cols'])))
    L.append(f"DICT {inst['dict_path']}")
    L.append(f"NSCORING {len(inst['scoring'])}")
    for blk in inst['scoring']:
        L.append(f"SCOL {blk['col']} {blk['len']} {len(blk['words'])}")
        for w in blk['words']:
            L.append("WORD " + ' '.join(map(str, w)))
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


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'gen'
    if cmd == 'gen':
        gen()
    elif cmd == 'genhard':
        gen_hard()
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
