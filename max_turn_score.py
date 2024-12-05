import argparse

from solve import *
from scrabble import *

import numpy as np
import time
parser = argparse.ArgumentParser(description='Find maximum scoring scrabble turns')
parser.add_argument('--language', dest='language', default='english', help='language to use (english, dutch, etc) will use data/words/<language> as a wordlist and loads the appropriate rules from languages.toml')
parser.add_argument('--board', dest='board', default='15', help='scrabble board to use, is language independent usually an integer eg: 7..21 but any string that is defined in boards.toml is valid')
parser.add_argument('--racksize', dest='racksize', type=int, default=7, help='maximum tiles a player can play per turn')
parser.add_argument('--bingo', dest='bingo', type=int, default=50, help='amount of points for a bingo (a bingo is using `racksize` amount of tiles in a turn)')
parser.add_argument('--log', dest='log', action='store_true', default=False, help='enable logging of the SAT solver for feedback on progress on stdin')
parser.add_argument('--wordlist', dest='wordlist', default=None, help='will load data/words/<language> by default, but this override that behaviour')
parser.add_argument('--cores', dest='cores', type=int, default=16, help='cores used in solving procedure, 16 is recommended to get lb_tree_search')
parser.add_argument('--output', dest='output', default='', help='where to dump results')

args = parser.parse_args()
if args.output == '':
	args.output = f'max_turn_score_{args.board}_{args.language}.log'

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

print_file = open(args.output, 'w')

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
	slots = create_word_mapping(model, cells2, None, alphabet_size=len(rules.abc))
	score = estimate_score(model, slots, rules.word_multiplier, rules.letter_multiplier, multiplier_active, rules.scores, {(0,0,1)}, bingo=False)

	# you get bingo when you place 'rack' additional tiles
	is_bingo = model.new_bool_var('is_bingo')
	tiles_placed = rules.W-sum(c.active for c in cells.values())
	model.add(tiles_placed == rules.hand_size).only_enforce_if(is_bingo)
	model.add(tiles_placed <= rules.hand_size)
	score += is_bingo*50
	model.maximize(score)

	return model, cells, cells2

def make_vertical_word_solver(main_word, scoring_positions):
	'''
	encode the state of the board including the vertical words
	we can place vertical (prefixable) words for extra points at all newly placed tiles their positions

	this problem can only be solved to optimality by lb_tree_search, if lb_tree_search is not active
	most of the solving will be done by core, which will run out of memory before finishing
	'''
	model = cp_model.CpModel()
	model.prefix = 'ver'
	prefixable = {w for w in rules.words if w[1:] in rules.words or len(w) <= 1}|{tuple()}
	y = scoring_positions[0][0]
	
	#main_word_automaton = automaton_words_from_list([rules.alphabet.to_tup(main_word)], rules.W)

	# TODO:
	# - we can also place the main word on the bottom which requires a new version of automaton_words_from_dict
	full_automaton = automaton_words_from_list(rules.words + [tuple()], rules.W)
	prefixable_automaton = automaton_words_from_dict({0:prefixable}|{i:rules.words + [tuple()] for i in range(2,rules.H)}, [{T_ANY}]*rules.H)

	cells3 = create_board(model, [full_automaton]*(rules.H), [prefixable_automaton if (i,y) in scoring_positions else full_automaton for i in range(rules.W)], alphabet_size=len(rules.abc), n_gram_rows=True)
	limit_letter_count(model, cells3, rules.counts)
	model.add(sum(c.blank for c in cells3.values()) <= rules.blank_count)

	_main_word = rules.alphabet.to_tup(main_word)
	for x in range(len(main_word)):
		model.add(cells3[(x, y)].letter[_main_word[x]] == 1)

	# only the non-active columns of the pre-turn can be used for scoring
	for x in range(len(main_word)):
		if not (x,y) in scoring_positions:
			model.add(cells3[(x, y+1)].active == 0)
	
	# and we score only those verticals
	_wm = np.ones_like(rules.word_multiplier)
	_lm = np.ones_like(rules.letter_multiplier)
	_wm[0,:] = rules.word_multiplier[0,:]
	_lm[0,:] = rules.letter_multiplier[0,:]

	slots = create_word_mapping(model, cells3, None, alphabet_size=len(rules.abc))
	score_verticals = estimate_score(model, slots, _wm, _lm, {}, rules.scores, {(i,0,0) for i in range(rules.W)}, bingo=False)
	model.maximize(score_verticals)
	return model, cells3

def make_connectivity_solver(rules, partial):
	model = cp_model.CpModel()
	model.prefix = "connect"
	print('creating automaton for connectivity solver')
	rows = [automaton_words_from_list(rules.words + [tuple()], rules.W, partial[y]) for y in range(rules.H)]
	columns = [automaton_words_from_list(rules.words + [tuple()], rules.H, list(zip(*partial))[x]) for x in range(rules.W)]

	if any(x.shape[0] == 0 for x in rows+columns):
		return None, None

	print('creating board')
	cells = create_board(model, rows, columns, alphabet_size=len(rules.abc))
	limit_letter_count(model, cells, rules.counts)
	model.add(sum(c.blank for c in cells.values()) <= rules.blank_count)
	single_component(model, cells, (rules.W//2, rules.H//2))
	return model, cells


model, pre_turn_cells, horizontal_word_cells = create_horizontal_word_solver()
for solver in do_solve(model, log=args.log, cores = args.cores):
	print('-'*120)
	print(time.time())
	model.add_bool_or([~[v for v in cell.letter.values() 						if solver.Value(v)][0] for (x,y), cell in horizontal_word_cells.items()] \
					+ [~[v for v in list(cell.letter.values()) + [~cell.active] if solver.Value(v)][0] for (x,y), cell in pre_turn_cells.items()])

	setup = ''.join([x if x else ' ' for x in read_board_state(solver, pre_turn_cells, rules.alphabet)[0]])
	main_word = ''.join([x if x else ' ' for x in read_board_state(solver, horizontal_word_cells, rules.alphabet)[0]])
	turn_str = "".join(c.upper() if setup[i]  == ' ' else c for i,c in enumerate(main_word))
	print(f'Next highest scoring main word gives {int(solver.objective_value)} points: {turn_str}', file=print_file, flush=True)

	scoring_positions = [(x,y) for (x,y) in pre_turn_cells if setup[x] == ' ']
	vertical_model, board_cells = make_vertical_word_solver(main_word, scoring_positions)
	for vert_solver in do_solve(vertical_model, log=args.log, cores = args.cores):
		print(time.time())
		board_str = read_board_state(vert_solver, board_cells, rules.alphabet)
		print(f'Highest scoring verticals given {turn_str} give {int(vert_solver.objective_value)} points:', file=print_file, flush=True)
		
		print(f"┌{'─'*(rules.W*2-1)}┐", file=print_file, flush=True)
		for row in board_str:
			print(f"│{' '.join([x if x else ' ' for x in row])}│", file=print_file, flush=True)
		print(f"└{'─'*(rules.W*2-1)}┘", file=print_file, flush=True)

		# copy all letters that contribute to points for the connectivity solver
		board = [[T_NONE if turn_str[x].isupper() else rules.alphabet.cba[board_str[0][x]] for x in range(rules.W)]] + [[T_ANY]*rules.W for i in range(rules.H-1)]
		for y,row in list(enumerate(board_str))[1:]:
			for x,c in enumerate(row):
				spaces = list(zip(*board_str))[x][:y+1].count(0)
				board[y][x] = rules.alphabet.cba[c] if turn_str[x].isupper() and spaces == 0 else (T_NONE if (board_str[y][x] == 0 and spaces == 1) else T_ANY)


		print(np.array(board), file=print_file, flush=True)
		board = [[[c] for c in row] for row in board]
		connect_model, connect_cells = make_connectivity_solver(rules, board)
		found_solution = False
		print('Solving connectivity...')
		if connect_model:
			for connect_solver in do_solve(connect_model, log=args.log, cores = args.cores):
				print(time.time())
				print(f'Can connect, final solution given {turn_str}:', file=print_file, flush=True)
				connect_board = read_board_state(connect_solver, connect_cells, rules.alphabet)
				print(f"┌{'─'*(rules.W*2-1)}┐", file=print_file, flush=True)
				for row in [turn_str] + connect_board[1:]:
					print(f"│{' '.join([x if x else ' ' for x in row])}│", file=print_file, flush=True)
				print(f"└{'─'*(rules.W*2-1)}┘", file=print_file, flush=True)

				print('Points:', file=print_file, flush=True)
				print(f'Expected point according to solver is {int(solver.objective_value+vert_solver.objective_value)} = {int(solver.objective_value)} for the main word + {int(vert_solver.objective_value)} for the vertical words', file=print_file, flush=True)
				print('Recalculating usign a different method:', file=print_file, flush=True)
				
				expected_main_word_score, wm = get_word_score(rules, rules.alphabet.to_tup(main_word), 0, 0, 1, [setup[i] == ' ' for i in range(len(main_word))])
				print(f'{turn_str} {expected_main_word_score} = {expected_main_word_score//wm} x {wm}', file=print_file, flush=True)
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
						print(f'{w.capitalize()} {w_score} = {w_score//wm} = {w_score} x {wm}', file=print_file, flush=True)
						total += w_score

				print('-'*12, file=print_file, flush=True)
				print(total, file=print_file, flush=True)
				found_solution = True
				break

			del connect_model
			del connect_cells
			if found_solution:
				break

		vertical_model.add_bool_or([~[v for v in list(cell.letter.values()) + [~cell.active] if vert_solver.Value(v)][0] for (x,y), cell in board_cells.items()])
