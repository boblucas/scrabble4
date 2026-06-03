import argparse

from solve import *
from scrabble import *

import time

# Solitaire-game TRIPLET search (per the "optimum is in a top playable triplet" reduction):
# we play three full-width words on the top / middle / bottom rows (the high word-multiplier
# lines). Each word is a "cash-in" turn: some tiles are pre-existing setup, the rest (<= rack)
# are newly placed and earn the multipliers. We maximise the combined triplet score subject to
# the global tile budget, then check the triplet can be wired into one legal connected board.
# (Setup-turn scores / bingos during setup are a ~constant baseline and are intentionally omitted
#  from the triplet objective.)

parser = argparse.ArgumentParser(description='Find the maximum-scoring solitaire triplet (top/middle/bottom words)')
parser.add_argument('--language', dest='language', default='english')
parser.add_argument('--board', dest='board', default='15')
parser.add_argument('--racksize', dest='racksize', type=int, default=7)
parser.add_argument('--bingo', dest='bingo', type=int, default=50)
parser.add_argument('--log', dest='log', action='store_true', default=False)
parser.add_argument('--wordlist', dest='wordlist', default=None)
parser.add_argument('--cores', dest='cores', type=int, default=24)
parser.add_argument('--extra-probing', dest='extra_probing', type=int, default=0,
                    help='add N diversified probing_max_lp subsolvers (bound-prover) to the triplet solve')
parser.add_argument('--output', dest='output', default='')
parser.add_argument('--time-limit', dest='time_limit', type=float, default=300.0,
                    help='per-solve time budget (s); the triplet optimise yields its best feasible solution at this limit')
args = parser.parse_args()
print_file = open(args.output, 'w') if args.output else None

print("Loading rules and wordlist")
rules = construct_rules(args.language, args.board, args.wordlist, args.racksize, args.bingo)
W, H = rules.W, rules.H
WORD_ROWS = [0, H // 2, H - 1]

# ---- triplet model -----------------------------------------------------------
model = cp_model.CpModel()
single_letters = automaton_words_from_list([(i,) for i in range(len(rules.alphabet))], 1)
setup_row = position_independent_row_automaton(rules.words)                       # any valid words (pre-state)
fill_row = automaton_words_from_list([w for w in rules.words if len(w) == W], W)   # one full-width word (post-state)

score = 0
triplet = []
for y in WORD_ROWS:
    model.prefix = f'pre{y}'
    pre = create_board(model, [setup_row], [single_letters] * W, (0, y), alphabet_size=len(rules.abc))
    # a board multiplier is "live" for this word only if the tile is newly placed (not in the setup)
    multiplier_active = {(x, yy): ~cell.active for (x, yy), cell in pre.items()
                         if rules.word_multiplier[yy][x] > 1 or rules.letter_multiplier[yy][x] > 1}

    model.prefix = f'suf{y}'
    post = create_board(model, [fill_row], [single_letters] * W, (0, y), alphabet_size=len(rules.abc))
    for p, a in pre.items():                       # post is a superset of pre (setup tiles unchanged)
        model.add(post[p].active == 1).only_enforce_if(a.active)
        for c in a.letter:
            model.add(a.letter[c] == post[p].letter[c]).only_enforce_if(a.active)

    # score the full-width word; multipliers apply to newly-placed tiles
    v = model.new_bool_var(f'w{y}_active'); model.add(v == 1)
    wcells = [post[(x, y)] for x in range(W)]
    slot = {(0, y, 1, W): Slot(v, 0, y, 1, W, wcells, [c.letter_int for c in wcells])}
    score += estimate_score(model, slot, rules.word_multiplier, rules.letter_multiplier,
                            multiplier_active, rules.scores, {(0, y, 1)}, bingo=False)

    # bingo: exactly rack-size tiles newly placed this turn
    is_bingo = model.new_bool_var(f'bingo{y}')
    tiles_placed = W - sum(c.active for c in pre.values())
    model.add(tiles_placed == rules.hand_size).only_enforce_if(is_bingo)
    model.add(tiles_placed <= rules.hand_size)
    score += is_bingo * rules.emptyhand_bonus
    triplet.append((pre, post))

# global tile budget across the three words (the connecting verticals are checked separately)
all_cells = {(x, y): c for (_, post) in triplet for (x, y), c in post.items()}
limit_letter_count(model, all_cells, rules.counts)
model.add(sum(c.blank for c in all_cells.values()) <= rules.blank_count)
model.maximize(score)


# ---- playability: can the three words be wired into one legal connected board? ----
def make_connectivity_solver(rules, word_rows):
    m = cp_model.CpModel(); m.prefix = 'connect'
    line = position_independent_row_automaton(rules.words)     # every row AND column must be valid words
    cells = create_board(m, [line] * rules.H, [line] * rules.W, alphabet_size=len(rules.abc))
    for y, letters in word_rows.items():
        for x, c in enumerate(letters):
            m.add(cells[(x, y)].letter[c] == 1)
    limit_letter_count(m, cells, rules.counts)
    m.add(sum(c.blank for c in cells.values()) <= rules.blank_count)
    single_component(m, cells, (rules.W // 2, rules.H // 2))
    return m, cells


print("Solving triplet")
for solver in do_solve(model, log=args.log, cores=args.cores, time_limit=args.time_limit, extra_probing=args.extra_probing):
    print(time.time())
    # exclude this triplet from future solves
    model.add_bool_or([~[v for v in list(c.letter.values()) + [~c.active] if solver.Value(v)][0]
                       for (_, post) in triplet for c in post.values()])

    word_rows, total_recompute = {}, 0
    for (pre, post), y in zip(triplet, WORD_ROWS):
        letters = [[c for c, vv in post[(x, y)].letter.items() if solver.Value(vv)][0] for x in range(W)]
        word_rows[y] = letters
        placed = [not solver.Value(pre[(x, y)].active) for x in range(W)]
        blanks = [bool(solver.Value(post[(x, y)].blank)) for x in range(W)]
        wscore, wm = get_word_score(rules, tuple(letters), 0, y, 1, placed, blanks)
        total_recompute += wscore
        word = rules.alphabet.to_str(letters)
        print(f'  row {y}: {word.upper()}  {wscore}  (x{wm}, {sum(placed)} placed)', file=print_file, flush=True)

    print(f'triplet score (solver estimate): {int(solver.objective_value)}  | recompute (blank-aware): {total_recompute}',
          file=print_file, flush=True)

    print('Checking connectivity...')
    connect_model, connect_cells = make_connectivity_solver(rules, word_rows)
    connected = False
    for connect_solver in do_solve(connect_model, log=args.log, cores=args.cores):
        connected = True
        print(f'PLAYABLE triplet, full connected board:', file=print_file, flush=True)
        board = read_board_state(connect_solver, connect_cells, rules.alphabet)
        print(f"┌{'─' * (W * 2 - 1)}┐", file=print_file, flush=True)
        for row in board:
            print(f"│{' '.join(x if x else ' ' for x in row)}│", file=print_file, flush=True)
        print(f"└{'─' * (W * 2 - 1)}┘", file=print_file, flush=True)
        print(f'triplet recompute total: {total_recompute}', file=print_file, flush=True)
        break
    del connect_model, connect_cells
    if connected:
        break
    print('  (not connectable, trying next triplet)', file=print_file, flush=True)
