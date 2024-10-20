import argparse

from solve import *
from scrabble import *

import numpy as np

parser = argparse.ArgumentParser(description='Find maximum scoring scrabble turns')
parser.add_argument('--language', dest='language', default='english', help='language to use (english, dutch, etc) will use data/words/<language> as a wordlist and loads the appropriate rules from languages.toml')
parser.add_argument('--board', dest='board', default='15', help='scrabble board to use, is language independent usually an integer eg: 7..21 but any string that is defined in boards.toml is valid')
parser.add_argument('--racksize', dest='racksize', type=int, default=7, help='maximum tiles a player can play per turn')
parser.add_argument('--bingo', dest='bingo', type=int, default=50, help='amount of points for a bingo (a bingo is using `racksize` amount of tiles in a turn)')
parser.add_argument('--log', dest='log', action='store_true', default=False, help='enable logging of the SAT solver for feedback on progress')
parser.add_argument('--wordlist', dest='wordlist', default=None, help='will load data/words/<language> by default, but this override that behaviour')
parser.add_argument('--cores', dest='cores', type=int, default=4, help='cores used in solving procedure, beyond 8 is not useful, even 4 works fine really')

args = parser.parse_args()

rules = construct_rules(args.language, args.board, args.wordlist, args.racksize, args.bingo)

# since the problem is too big too solve in one instance the optimization is done in 3 stages:
# 1: find the maximum scoring word, and which tiles we put down to create it
#	- checks tile limits
#	- checks bingo-ability
#	- checks theoratically valid initial state
# 2: find the maximum scoring vertical (pre/post)fixable words given a main word
#   - no invalid words in any direct
#   - check tile limits
# 3: find out if there is a board configuration 
#   - guarantee that there is a single component that touches (W//2, H//2)

# this also means you could run step 2 in parallel

def create_horizontal_word_solver():
	# encode state of the board before the turn
	# ----
	model = cp_model.CpModel()
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
	model.maximize(score)

	return model, cells, cells2

def make_vertical_word_solver(main_word, scoring_positions):
	# encode the state of the board including the vertical words
	# ----- 
	# we can place vertical (prefixable) words for extra points at all newly placed tiles their positions
	model = cp_model.CpModel()
	model.prefix = 'ver'
	prefixable = {w for w in rules.words if w[1:] in rules.words or len(w) <= 1}|{tuple()}
	
	#main_word_automaton = automaton_words_from_list([rules.alphabet.to_tup(main_word)], rules.W)
	full_automaton = automaton_words_from_list(rules.words + [tuple()], rules.W)
	prefixable_automaton = automaton_words_from_dict({0:prefixable}, [{T_ANY}]*rules.H)

	cells3 = create_board(model, [full_automaton]*(rules.H), [prefixable_automaton]*rules.W, alphabet_size=len(rules.abc))
	limit_letter_count(model, cells3, rules.counts)
	model.add(sum(c.blank for c in cells3.values()) <= rules.blank_count)

	y = scoring_positions[0][0]
	_main_word = rules.alphabet.to_tup(main_word)
	for x in range(len(main_word)):
		model.add(cells3[(x, y)].letter[_main_word[x]] == 1)

	# only the non-active columns of the pre-turn can be used for scoring
	for x in range(len(main_word)):
		if not (x,y) in scoring_positions:
			model.add(cells3[(x, y+1)].active == 0)
	
	multiplier_active = {}
	y = scoring_positions[0][0]
	for x in range(rules.W):
		if rules.word_multiplier[y][x] > 1 or rules.letter_multiplier[y][x] > 1:
			v = model.new_bool_var(f'mult_active_{x}_{y}')
			model.add(v == ((x,y) in scoring_positions))
			multiplier_active[(x,y)] = v

	# and we score only those verticals
	_wm = np.ones_like(rules.word_multiplier)
	_lm = np.ones_like(rules.letter_multiplier)
	_wm[0,:] = rules.word_multiplier[0,:]
	_lm[0,:] = rules.letter_multiplier[0,:]
	score_verticals,_ = estimate_score(model, cells3, _wm, _lm, multiplier_active, rules.scores, {(i,0,0) for i in range(rules.W)}, bingo=False)
	model.maximize(score_verticals)
	return model, cells3

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


model, pre_turn_cells, horizontal_word_cells = create_horizontal_word_solver()
for solver in do_solve(model, log=args.log, cores = args.cores):
	model.add_bool_or([~[v for v in cell.letter.values() 						if solver.Value(v)][0] for (x,y), cell in horizontal_word_cells.items()] \
					+ [~[v for v in list(cell.letter.values()) + [~cell.active] if solver.Value(v)][0] for (x,y), cell in pre_turn_cells.items()])

	setup = ''.join([x if x else ' ' for x in read_board_state(solver, pre_turn_cells, rules.alphabet)[0]])
	main_word = ''.join([x if x else ' ' for x in read_board_state(solver, horizontal_word_cells, rules.alphabet)[0]])
	turn_str = "".join(c.upper() if setup[i]  == ' ' else c for i,c in enumerate(main_word))
	print(f'Next highest scoring main word gives {int(solver.objective_value)} points: {turn_str}')

	scoring_positions = [(x,y) for (x,y) in pre_turn_cells if setup[x] == ' ']
	vertical_model, board_cells = make_vertical_word_solver(main_word, scoring_positions)
	for vert_solver in do_solve(vertical_model, log=args.log, cores = args.cores):
		board_str = read_board_state(vert_solver, board_cells, rules.alphabet)
		print(f'Highest scoring verticals given {turn_str} give {int(vert_solver.objective_value)} points:')
		
		print(f"┌{'─'*rules.W}┐")
		for row in board_str:
			print(f"│{''.join([x if x else ' ' for x in row])}│")
		print(f"└{'─'*rules.W}┘")

		# now we create a new model that just checks whether you can create a connected whole
		board = [[-1]*rules.W for i in range(rules.H)]
		for (x,y), cell in board_cells.items():
			active_letter = [c for c,v in cell.letter.items() if (b if isinstance(v, bool) else vert_solver.Value(v))]
			board[y][x] = (active_letter[0] if active_letter else -1,)
		
		# put -2 (must be empty) at all the top row post-first move cells
		for (x,y) in pre_turn_cells:
			board[y][x] = (-2 if setup[x] == ' ' else rules.alphabet.to_tup(setup)[x],)

		# put -2 (must be empty) below all the prefixable words
		for (x,y) in board_cells:
			if y > 1 and board[0][x] == -2 and board[y-1][x] >= 0 and board[y][x] == -1:
				board[y][x] = -2

		connect_model, connect_cells = make_connectivity_solver(rules, board)
		found_solution = False
		for connect_solver in do_solve(connect_model, log=args.log, cores = args.cores):
			print(f'Can connect, final solution given {turn_str}:')
			connect_board = read_board_state(connect_solver, connect_cells, rules.alphabet)
			print(f"┌{'─'*rules.W}┐")
			for row in connect_board:
				print(f"│{''.join([x if x else ' ' for x in row])}│")
			print(f"└{'─'*rules.W}┘")

			print('Points:')
			print(f'Expected point according to solver is {int(solver.objective_value+vert_solver.objective_value)} = {int(solver.objective_value)} for the main word + {int(vert_solver.objective_value)} for the vertical words')
			print('Recalculating usign a different method:')
			
			expected_main_word_score, wm = get_word_score(rules, rules.alphabet.to_tup(main_word), 0, 0, 1, [setup[i] == ' ' for i in range(len(main_word))])
			print(f'{turn_str} {expected_main_word_score} = {expected_main_word_score//wm} x {wm}')
			total = expected_main_word_score
			for (x,y) in scoring_positions:
				w = [main_word[x]]
				for y2 in range(1, rules.H):
					if not board_str[y2][x]:
						break
					w.append(rules.alphabet.abc[board[y2][x][0]])
				
				if len(w) > 1:
					w = ''.join(w)
					w_score, wm = get_word_score(rules, rules.alphabet.to_tup(w), x, y, 0, [i==0 for i in range(len(w))])
					print(f'{w.capitalize()} {w_score} = {w_score//wm} = {w_score} x {wm}')
					total += w_score

			print('-'*12)
			print(total)
			found_solution = True
			break

		del connect_model
		del connect_cells
		if found_solution:
			break

		vert_solver.add_bool_or([~[v for v in list(cell.letter.values()) + [~cell.active] if solver.Value(v)][0] for (x,y), cell in board_cells.items()])
