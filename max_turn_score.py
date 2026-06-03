import argparse

from solve import *
from scrabble import *

import numpy as np
import time
import sys

parser = argparse.ArgumentParser(description='Find maximum scoring scrabble turns')
parser.add_argument('--language', dest='language', default='english', help='language to use (english, dutch, etc) will use data/words/<language> as a wordlist and loads the appropriate rules from languages.toml')
parser.add_argument('--board', dest='board', default='15', help='scrabble board to use, is language independent usually an integer eg: 7..21 but any string that is defined in boards.toml is valid')
parser.add_argument('--racksize', dest='racksize', type=int, default=7, help='maximum tiles a player can play per turn')
parser.add_argument('--bingo', dest='bingo', type=int, default=50, help='amount of points for a bingo (a bingo is using `racksize` amount of tiles in a turn)')
parser.add_argument('--log', dest='log', action='store_true', default=False, help='enable logging of the SAT solver for feedback on progress on stdin')
parser.add_argument('--wordlist', dest='wordlist', default=None, help='will load data/words/<language> by default, but this override that behaviour')
parser.add_argument('--cores', dest='cores', type=int, default=16, help='cores used in solving procedure, 16 is recommended to get lb_tree_search')
parser.add_argument('--output', dest='output', default='', help='where to dump results')
parser.add_argument('--main', dest='main', default=None, help='solve for a specific main word')
parser.add_argument('--no-main-blanks', dest='no_main_blanks', action='store_true', default=False, help='forbid blank tiles anywhere in the main word (dedups blank-variants of the same word)')
parser.add_argument('--extra-probing', dest='extra_probing', type=int, default=0, help='add N diversified probing_max_lp subsolvers (the objective lower-bound prover) to the portfolio')

args = parser.parse_args()
#args.output = f'max_turn_score_{args.board}_{args.language}.log'

if args.output == '':
	print_file = None
else:
	print_file = open(args.output, 'w')

print("Loading rules and wordlist")
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

# solving the whole problem, or at least 2 & 3 at once runs out of memory (and reasonably also time) on even
# my 512GB machine. Problem 1 & 2 are actually ok, in the sense that we can keep the model open and just generate
# optimal solutions in order 

# problem 3 is not ideal, it solves well as there is no optimization anymore, but the creation takes 30m because of
# all the automatons while not being reuseable. So any candidate from 2 must have a quite a high hit rate. Which by default it will not.

# to mitigate this you can put extra restrictions on 2 that are much easier than the whole problem, but restrict the space a lot
# If we look at a vertical solution like:
# 
# CitYtriPCheQUeS
# ┌─────────────────────────────┐
# │_ i t _ t r i _ _ h e _ _ e _│
# │h # # e $ $ $ l a % % u w @ p│
# │e     n       a m     i e   r│
# │f     t       a b     l n   e│
# │f     e       g r     t t   e│
# │e     k       v e     j     k│
# │n     e       o r     e     v│
# │d     n       r e     s     e│
# │e     s       m n           r│
# │n             i d           b│
# │              n e           o│
# │              k n           d│
# │              j             j│
# │              e             e│
# │              s             s│
# └─────────────────────────────┘
# 
# Then it is important that for each of the symbol groups, one must be present to connect the layout.
# This means in turn that the 2nd row, and the vertical words intersecting with that row (with fixed staring letters) are very restrictive.
# so we create a single massive automaton for the 2nd row, and we demand good vertical words from row 1 down.
# this will mean that a much larger percentage of solutions will actual be connectable


# this also means you could run step 2 in parallel
def create_horizontal_word_solver(main = None, assume_short_pre_words = True):
	'''
	assume_short_pre_words: In most cases you need to the mult-tiles to remain free creating a max word length of 3
		assuming this greatly speeds up this solve as you don't have to encode a giant dictionary for nothing
	'''

	# encode state of the board before the turn
	# ----
	# main may be None (search over all main words, line 105 handles `not main`)
	main = rules.alphabet.to_tup(main) if main else None
	model = cp_model.CpModel()
	model.prefix = 'pre'
	vertical = automaton_words_from_list([(i,) for i in range(len(rules.alphabet))], 1)
	horizontal = automaton_words_from_list([w for w in rules.words_lookup if len(w) <= 3] if assume_short_pre_words else rules.words, rules.W)
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
	horizontal = automaton_words_from_list([w for w in rules.words_lookup if len(w) == rules.W] if not main else [main], rules.W)
	cells2 = create_board(model, [horizontal], [vertical]*rules.W, alphabet_size=len(rules.abc))
	limit_letter_count(model, cells2, rules.counts)
	model.add(sum(c.blank for c in cells2.values()) <= rules.blank_count)
	if args.no_main_blanks:
		for x in range(rules.W):
			model.add(cells2[(x,0)].blank == 0)

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

def make_vertical_word_solver(main_word, scoring_positions, solve_rows = 2):
	'''
	encode the state of the board including the vertical words
	we can place vertical (prefixable) words for extra points at all newly placed tiles their positions

	this problem can only be solved to optimality by lb_tree_search, if lb_tree_search is not active
	most of the solving will be done by core, which will run out of memory before finishing

	when you can actually 'solve' the resulting board state the solution is optimal.
	so there is some trade-off in how much work you want to do in this step to discard problematic boards early.

	The most critical tiles are those of the 2nd row, by putting an automaton there you can generally limit the invalid solution quite aggressively
	'''
	model = cp_model.CpModel()
	model.prefix = 'ver'
	y = scoring_positions[0][1]
	
	# TODO:
	# - we can also place the main word on the bottom which requires a new version of automaton_words_from_dict
	empty = {k:[tuple()] for k in range(2,rules.H)}
	main_tup = rules.alphabet.to_tup(main_word)

	# Full-dictionary, all-positions row automaton -> use the linear-time minimal DFA.
	# (Equivalent to automaton_words_from_list(rules.words+[tuple()], rules.W, [{T_ANY}]*rules.W),
	#  but ~6-8x smaller after CP-SAT expansion and built in <1s even for big dictionaries.)
	general_row_automaton = position_independent_row_automaton(rules.words)
	column_automatons = []

	for x in range(len(main_word)):
		general = {
			0: {w for w in rules.words if w[0] == main_tup[x]}, 
			1: {}, 
			2: [w for w in rules.words if len(w) <= 7] + [tuple()]}
		
		if (x,y) in scoring_positions:
			general[0] = {w for w in general[0] if w[1:] in rules.words_lookup}
		
		column_automatons.append(automaton_words_from_dict(general, [{T_ANY}]*rules.H))


	# Merge connectivity into stage 2: constrain EVERY row to a valid word sequence (using the
	# fast minimal DFA) so the whole board is valid, and demand a single connected component
	# touching the centre (below). The optimal solution is then the optimal *connectable* turn
	# in ONE solve -- no more enumerate-and-test against a separate connectivity stage (which had
	# a ~0.2% hit-rate and re-solved this model ~13s per candidate).
	cells3 = create_board(
		model,
		[general_row_automaton]*rules.H,
		column_automatons,
		alphabet_size=len(rules.abc),
		n_gram_rows=True)
	
	# Each sub-word within main-word much be connected to something at least
	partial = []
	for x in range(len(main_word)):
		if not (x,y) in scoring_positions:
			partial.append(x)
		elif partial:
			print(y, partial)
			model.add(sum(cells3[(x2, y+1)].active for x2 in partial) >= 1)
			partial = []

	limit_letter_count(model, cells3, rules.counts)
	model.add(sum(c.blank for c in cells3.values()) <= rules.blank_count)

	for x in range(len(main_word)):
		model.add(cells3[(x, y)].letter[main_tup[x]] == 1)
		if args.no_main_blanks:
			model.add(cells3[(x, y)].blank == 0)

	# connectivity, merged into stage 2 (single connected component touching the centre)
	single_component(model, cells3, (rules.W//2, rules.H//2))

	# only the non-active columns of the pre-turn can be used for scoring
	#for x in range(len(main_word)):
	#	if not (x,y) in scoring_positions:
	#		model.add(cells3[(x, y+1)].active == 0)
	
	# and we score only those verticals
	_wm = np.ones_like(rules.word_multiplier)
	_lm = np.ones_like(rules.letter_multiplier)
	_wm[0,:] = rules.word_multiplier[0,:]
	_lm[0,:] = rules.letter_multiplier[0,:]

	slots = create_word_mapping(model, cells3, None, alphabet_size=len(rules.abc))
	score_verticals = estimate_score(model, slots, _wm, _lm, {}, rules.scores, {(i,0,0) for i in range(rules.W) if (i,y) in scoring_positions}, bingo=False)
	model.maximize(score_verticals)
	return model, cells3



def has_sufficient_tiles(input_counts, allowed_blanks, counts):
	''' given a N x |abc| matrix of letters counts, will return N sized matrix of booleans
	to signify all inputs where sufficient letters are available '''
	return np.sum(np.clip((counts - input_counts),-(allowed_blanks+1),0), axis=1) >= -allowed_blanks


def make_connectivity_solver(rules, partial, omit_bottom_rows = 3, max_vertical_length = 5):
	'''
	Given a partial board state will create a model such board state is a super-set and a valid scrabble game

	the biggest performance cost is wordcount. The places that are restricted are fine. But the last few horizontal rows
	are particularly expensive, since they are usually not required you can allow any string there to get quick and very tight UB's

	for the columns you at least know that first and Y position are very restricted, as are all the columns that already contain a word
	the open columns may be restricted to short words this means you are not finding a strict UB, but it may be worth it
	'''
	model = cp_model.CpModel()
	model.prefix = "connect"
	print('creating automaton for connectivity solver')
	
	rows = [automaton_words_from_list(rules.words + [tuple()], rules.W, partial[y]) for y in range(rules.H-omit_bottom_rows)] + [None for _ in range(rules.H-omit_bottom_rows, rules.H)]
	#columns = [automaton_words_from_list(rules.words + [tuple()], rules.H, list(zip(*partial))[x]) for x in range(rules.W)]
	columns = []
	for x in range(rules.W):
		# has word
		if partial[1][x][-1] >= 0:
			columns.append(automaton_words_from_list(rules.words + [tuple()], rules.H, list(zip(*partial))[x]))
		else:
			columns.append(automaton_words_from_list([w for w in rules.words if len(w) <= max_vertical_length] + [tuple()], rules.H, list(zip(*partial))[x]))

	#if any(x.shape[0] == 0 for x in rows+columns if x):
	#	return None, None

	print('creating board')
	cells = create_board(model, rows, columns, alphabet_size=len(rules.abc))
	for x in range(rules.W):
		for y in range(rules.H):
			if partial[y][x][0] >= 0:
				model.add(cells[(x, y)].letter[partial[y][x][0]] == 1)

	limit_letter_count(model, cells, rules.counts)
	model.add(sum(c.blank for c in cells.values()) <= rules.blank_count)
	single_component(model, cells, (rules.W//2, rules.H//2))
	return model, cells

print("Creating horizontal solver")
model, pre_turn_cells, horizontal_word_cells = create_horizontal_word_solver(args.main)
for solver in do_solve(model, log=args.log, cores = args.cores, extra_probing = args.extra_probing):
	print('-'*120)
	print(time.time())
	model.add_bool_or([~[v for v in list(cell.letter.values()) + [~cell.active] 						if solver.Value(v)][0] for (x,y), cell in horizontal_word_cells.items()] \
					+ [~[v for v in list(cell.letter.values()) + [~cell.active] if solver.Value(v)][0] for (x,y), cell in pre_turn_cells.items()])

	setup = ''.join([x if x else ' ' for x in read_board_state(solver, pre_turn_cells, rules.alphabet)[0]])
	main_word = ''.join([x if x else ' ' for x in read_board_state(solver, horizontal_word_cells, rules.alphabet)[0]])
	turn_str = "".join(c.upper() if setup[i]  == ' ' else c for i,c in enumerate(main_word))
	print(f'Next highest scoring main word gives {int(solver.objective_value)} points: {turn_str}', file=print_file, flush=True)

	scoring_positions = [(x,y) for (x,y) in pre_turn_cells if setup[x] == ' ']
	vertical_model, board_cells = make_vertical_word_solver(main_word, scoring_positions)
	for vert_solver in do_solve(vertical_model, log=args.log, cores = args.cores, extra_probing = args.extra_probing):
		print(time.time())
		board_str = read_board_state(vert_solver, board_cells, rules.alphabet)
		print(f'Highest scoring verticals given {turn_str} give {int(vert_solver.objective_value)} points:', file=print_file, flush=True)
		
		print(f"┌{'─'*(rules.W*2-1)}┐", file=print_file, flush=True)
		for row in board_str:
			print(f"│{' '.join([x if x else ' ' for x in row])}│", file=print_file, flush=True)
		print(f"└{'─'*(rules.W*2-1)}┘", file=print_file, flush=True)

		# copy all letters that contribute to points for the connectivity solver
		board = [[T_NONE if turn_str[x].isupper() else rules.alphabet.cba[board_str[0][x]] for x in range(rules.W)]] + [[T_ANY]*rules.W for i in range(rules.H-1)]
		for x in range(rules.W):
			for y in range(1,rules.H):
				if board_str[y][x]:
					board[y][x] = rules.alphabet.cba[board_str[y][x]]
				else:
					if y > 1:
						board[y][x] = T_NONE
					break

		print(board)
		#for y,row in list(enumerate(board_str))[1:]:
		#	for x,c in enumerate(row):
		#		spaces = list(zip(*board_str))[x][:y+1].count(0)
		#		board[y][x] = rules.alphabet.cba[c] if turn_str[x].isupper() and spaces == 0 else (T_NONE if (board_str[y][x] == 0 and spaces == 1) else T_ANY)


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
