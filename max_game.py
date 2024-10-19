import argparse

from solve import *
from scrabble import *

parser = argparse.ArgumentParser(description='Find maximum scoring scrabble turns')
parser.add_argument('--language', dest='language', default='english', help='language to use (english, dutch, etc) will use data/words/<language> as a wordlist and loads the appropriate rules from languages.toml')
parser.add_argument('--board', dest='board', default='15', help='scrabble board to use, is language independed usually an integer eg: 7..21 but any string that defined in boards.toml is valid')
parser.add_argument('--racksize', dest='racksize', type=int, default=7, help='maximum tiles player per turn')
parser.add_argument('--bingo', dest='bingo', type=int, default=50, help='amount of points for a bingo (rack size tiles in a turn)')
parser.add_argument('--log', dest='log', action='store_true', default=False, help='enable logging of the SAT solver for feedback on progress')
parser.add_argument('--wordlist', dest='wordlist', default=None, help='will load data/words/<language> by default, but this override that behaviour')
args = parser.parse_args()

rules = construct_rules(args.language, args.board, args.wordlist, args.racksize, args.bingo)
model = cp_model.CpModel()

# we have 3 pre-states and 3-post states, for the 3 main N-letter words
score = 0
main_words = []
alphabet_automaton = automaton_words_from_list([(i,) for i in range(len(rules.alphabet))], 1)
full_automaton = automaton_words_from_list(rules.words, rules.W)
fill_automaton = automaton_words_from_list([w for w in rules.words if len(w) == rules.W], rules.W)
for y in [0, rules.H//2, rules.H-1]:
	# encode state of the board before the turn
	model.prefix = f'pre{y}'
	cells = create_board(model, [full_automaton], [alphabet_automaton]*rules.W, (0, y))

	# note which multipliers are deactivated as a result
	multiplier_active = {}
	for (x,y), cell in cells.items():
		if rules.word_multiplier[y][x] > 1 or rules.letter_multiplier[y][x] > 1:
			multiplier_active[(x,y)] = ~cell.active

	# encode state of the board after the turn
	model.prefix = f'suf{y}'
	cells2 = create_board(model, [fill_automaton], [alphabet_automaton]*rules.W, (0, y))

	# cells2 is a superset of cells to signify a turn
	for p, a in cells.items():
		model.add(cells2[p].active == 1).only_enforce_if(a.active)
		for c in a.letter:
			model.add(a.letter[c] == cells2[p].letter[c]).only_enforce_if(a.active)

	# maximize score of turn
	_score,_ = estimate_score(model, cells2, rules.word_multiplier, rules.letter_multiplier, multiplier_active, rules.scores, {(0,y,1)}, bingo=False)
	score += _score

	# you get bingo when you place 'rack' additional tiles
	is_bingo = model.new_bool_var('is_bingo')
	tiles_placed = rules.W-sum(c.active for c in cells.values())
	model.add(tiles_placed == rules.hand_size).only_enforce_if(is_bingo)
	model.add(tiles_placed <= rules.hand_size)
	score += is_bingo*50

	main_words.append((cells, cells2))

# all final words together must fit within tile limit
model.prefix = 'total'
all_cells = {(x,y):c for i, (_, cells2) in enumerate(main_words) for (x,y), c in cells2.items()}
limit_letter_count(model, all_cells, rules.counts)
model.add(sum(c.blank for c in all_cells.values()) <= rules.blank_count)

model.maximize(score)


def make_connectivity_solver(rules, partial):
	model = cp_model.CpModel()
	model.prefix = "connect"

	rows = [automaton_words_from_list(rules.words + [tuple()], rules.W, partial[y]) for y in range(rules.H)]
	columns = [automaton_words_from_list(rules.words + [tuple()], rules.H, list(zip(*partial))[x]) for x in range(rules.W)]
	cells = create_board(model, rows, columns)
	limit_letter_count(model, cells, rules.counts)
	model.add(sum(c.blank for c in cells.values()) <= rules.blank_count)
	single_component(model, cells, (rules.W//2, rules.H//2))
	_score,_ = estimate_score(model, cells, rules.word_multiplier, rules.letter_multiplier, multiplier_active, rules.scores, bingo=False)
	model.maximize(_score)
	return model, cells

for solver in do_solve(model, log=args.log, cores = 4):
	board_str = read_board_state(solver, all_cells, rules.alphabet)
	for row in board_str:
		print(''.join([x if x else ' ' for x in row]))
	print()
	model.add_bool_or([~[v for v in cell.letter.values() if solver.Value(v)][0] for (x,y), cell in all_cells.items()])

	# now we create a new model that just checks whether you can create a connected whole
	board = [[(-1,)]*rules.W for i in range(rules.H)]
	for (x,y), cell in all_cells.items():
		active_letter = [c for c,v in cell.letter.items() if (b if isinstance(v, bool) else solver.Value(v))]
		board[y][x] = (active_letter[0] if active_letter else -1,)		

	connect_model, connect_cells = make_connectivity_solver(rules, board)
	for connect_solver in do_solve(connect_model, log=args.log, cores = 4):
		print('Can connect, final solution:')
		connect_board = read_board_state(connect_solver, connect_cells, rules.alphabet)
		for row in connect_board:
			print(''.join([x if x else ' ' for x in row]))
		print()
		exit()
