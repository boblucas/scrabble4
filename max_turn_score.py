import argparse

from solve import *
from scrabble import *

parser = argparse.ArgumentParser(description='Find maximum scoring scrabble turns')
parser.add_argument('--language', dest='language', default='english', help='language to use (english, dutch, etc) will use data/words/<language> as a wordlist and loads the appropriate rules from languages.toml')
parser.add_argument('--board', dest='board', default='15', help='scrabble board to use, is language independent usually an integer eg: 7..21 but any string that is defined in boards.toml is valid')
parser.add_argument('--racksize', dest='racksize', type=int, default=7, help='maximum tiles a player can play per turn')
parser.add_argument('--bingo', dest='bingo', type=int, default=50, help='amount of points for a bingo (a bingo is using `racksize` amount of tiles in a turn)')
parser.add_argument('--log', dest='log', action='store_true', default=False, help='enable logging of the SAT solver for feedback on progress')
parser.add_argument('--wordlist', dest='wordlist', default=None, help='will load data/words/<language> by default, but this override that behaviour')
parser.add_argument('--connect', dest='connect', action='store_true', default=False, help='will solve connectivity within model directly when true. This is more efficient in time, but will use much more memory.')
parser.add_argument('--cores', dest='cores', type=int, default=8, help='cores used in solving procedure, beyond 8 is not useful, even 4 works fine really')

args = parser.parse_args()

rules = construct_rules(args.language, args.board, args.wordlist, args.racksize, args.bingo)
model = cp_model.CpModel()


# encode state of the board before the turn
# ----
model.prefix = 'pre'
vertical = automaton_words_from_list([(i,) for i in range(len(rules.alphabet))], 1)
horizontal = automaton_words_from_list(rules.words, rules.W)
cells = create_board(model, [horizontal], [vertical]*rules.W, alphabet_size=len(rules.abc))

# note which multipliers are deactivated as a result
multiplier_active = {}
for (x,y), cell in cells.items():
	if rules.word_multiplier[y][x] > 1 or rules.letter_multiplier[y][x] > 1:
		multiplier_active[(x,y)] = ~cell.active


# encode state of the board after the turn
# -----
model.prefix = 'suf'
vertical = automaton_words_from_list([(i,) for i in range(len(rules.alphabet))], 1)
horizontal = automaton_words_from_list([w for w in rules.words if len(w) == rules.W], rules.W)
cells2 = create_board(model, [horizontal], [vertical]*rules.W, alphabet_size=len(rules.abc))
limit_letter_count(model, cells2, rules.counts)
model.add(sum(c.blank for c in cells2.values()) <= rules.blank_count)

# cells2 is a superset of cells to signify a turn
for p, a in cells.items():
	model.add(cells2[p].active == 1).only_enforce_if(a.active)
	for c in a.letter:
		model.add(a.letter[c] == cells2[p].letter[c]).only_enforce_if(a.active)

# maximize score of turn
score,_ = estimate_score(model, cells2, rules.word_multiplier, rules.letter_multiplier, multiplier_active, rules.scores, {(0,0,1)}, bingo=False)

# you get bingo when you place 'rack' additional tiles
is_bingo = model.new_bool_var('is_bingo')
tiles_placed = rules.W-sum(c.active for c in cells.values())
model.add(tiles_placed == rules.hand_size).only_enforce_if(is_bingo)
model.add(tiles_placed <= rules.hand_size)
score += is_bingo*50


# encode the state of the board including the vertical words
# ----- 
# we can place vertical (prefixable) words for extra points at all newly placed tiles their positions
model.prefix = 'ver'
prefixable = {w for w in rules.words if w[1:] in rules.words or len(w) <= 1}|{tuple()}
full_automaton = automaton_words_from_list(rules.words + [tuple()], rules.W)
prefixable_automaton = automaton_words_from_dict({0:prefixable}, [{T_ANY}]*rules.H)

cells3 = create_board(model, [full_automaton]*rules.H, [prefixable_automaton]*rules.W, alphabet_size=len(rules.abc))
limit_letter_count(model, cells3, rules.counts)
model.add(sum(c.blank for c in cells3.values()) <= rules.blank_count)

# the first row is the placed word
for p, a in cells2.items():
	for c in a.letter:
		model.add(a.letter[c] == cells3[p].letter[c])

# only the non-active columns of the pre-turn can be used for scoring
for (x,y), a in cells.items():
	model.add(cells3[(x, y+1)].active == 0).only_enforce_if(a.active)

# and we score only those verticals
score_verticals,_ = estimate_score(model, cells3, rules.word_multiplier, rules.letter_multiplier, multiplier_active, rules.scores, {(i,0,0) for i in range(rules.W)}, bingo=False)
score += score_verticals
model.maximize(score)


# find first connectable maximum scoring solution
# ----
if args.connect:
	model.prefix = 'connect'
	cells4 = create_board(model, [full_automaton]*rules.H, [full_automaton]*rules.W, alphabet_size=len(rules.abc))
	limit_letter_count(model, cells4, rules.counts)
	model.add(sum(c.blank for c in cells4.values()) <= rules.blank_count)
	single_component(model, cells4, (rules.W//2, rules.H//2))

	# we must copy set cells of previous state first
	# except the first row, where we copy pre-turn (eg cells2)
	for p, a in cells3.items():
		if not p in cells2:
			for c in a.letter:
				model.add(a.letter[c] == cells4[p].letter[c]).only_enforce_if(a.active)

	for p, a in cells2.items():
		for c in a.letter:
			model.add(a.letter[c] == cells4[p].letter[c])

	# for each column we are not allowed to modify the first active word.
	# we know for a fact the previous state has a contigious set of tiles from the top, followed by empty tiles
	for x in range(rules.W):
		for y in range(1, rules.H):
			model.add(cells4[(x, y)].active == 0).only_enforce_if([cells3[(x, y-1)].active, ~cells3[(x, y)].active])

	for solver in do_solve(model, log=args.log, cores = args.cores):
		setup = ''.join([x if x else ' ' for x in read_board_state(solver, cells, rules.alphabet)[0]])
		word = ''.join([x if x else ' ' for x in read_board_state(solver, cells2, rules.alphabet)[0]])
		board_str = read_board_state(solver, cells4, rules.alphabet)
		print(f'Highest scoring is {solver.objective_value} points using {word.upper()} given "{setup}", board:')
		for row in board_str:
			print(''.join([x if x else ' ' for x in row]))
		print()
		break
else:
	def make_connectivity_solver(rules, partial):
		model = cp_model.CpModel()
		model.prefix = "connect"

		rows = [automaton_words_from_list(rules.words + [tuple()], rules.W, partial[y]) for y in range(rules.H)]
		columns = [automaton_words_from_list(rules.words + [tuple()], rules.H, list(zip(*partial))[x]) for x in range(rules.W)]
		cells = create_board(model, rows, columns, alphabet_size=len(rules.abc))
		limit_letter_count(model, cells, rules.counts)
		model.add(sum(c.blank for c in cells.values()) <= rules.blank_count)
		single_component(model, cells, (rules.W//2, rules.H//2))
		return model, cells

	for solver in do_solve(model, log=args.log, cores = args.cores):
		setup = ''.join([x if x else ' ' for x in read_board_state(solver, cells, rules.alphabet)[0]])
		word = ''.join([x if x else ' ' for x in read_board_state(solver, cells2, rules.alphabet)[0]])
		board_str = read_board_state(solver, cells3, rules.alphabet)
		print(f'Next highest scoring is {solver.objective_value} points using {word.upper()} given "{setup}", board:')
		for row in board_str:
			print(''.join([x if x else ' ' for x in row]))
		print()

		model.add_bool_or([~[v for v in cell.letter.values() if solver.Value(v)][0] for (x,y), cell in cells2.items()] + [~[v for v in list(cell.letter.values()) + [~cell.active] if solver.Value(v)][0] for (x,y), cell in cells.items()])

		# now we create a new model that just checks whether you can create a connected whole
		board = [[-1]*rules.W for i in range(rules.H)]
		for (x,y), cell in cells3.items():
			active_letter = [c for c,v in cell.letter.items() if (b if isinstance(v, bool) else solver.Value(v))]
			board[y][x] = (active_letter[0] if active_letter else -1,)
		
		# put -2 (must be empty) at all the top row post-first move cells
		for (x,y), cell in cells.items():
			active_letter = [c for c,v in cell.letter.items() if (b if isinstance(v, bool) else solver.Value(v))]
			board[y][x] = (active_letter[0] if active_letter else -2,)

		# put -2 (must be empty) below all the prefixable words
		for (x,y), cell in cells.items():
			if y > 1:
				if board[y-1][x] >= 0 and board[y][x] == -1:
					board[y][x] = -2

		connect_model, connect_cells = make_connectivity_solver(rules, board)
		for connect_solver in do_solve(connect_model, log=args.log, cores = args.cores):
			print('Can connect, final solution:')
			connect_board = read_board_state(connect_solver, connect_cells, rules.alphabet)
			for row in connect_board:
				print(''.join([x if x else ' ' for x in row]))
			print()
			exit()
		del connect_model
		del connect_cells