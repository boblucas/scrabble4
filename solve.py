from collections import *
from itertools import *
from math import prod
import time

from ortools.sat.python import cp_model

from scrabble import *
from dawg import *

Cell = namedtuple('Cell', ['active', 'letter', 'x', 'y', 'blank', 'letter_int'])
Slot = namedtuple('Slot', ['active', 'x', 'y', 'h', 'n', 'cells', 'word'])

def create_board(model, rows_words:list[np.ndarray], columns_words:list[np.ndarray], offset = (0,0), alphabet_size = 26, n_gram_rows:bool = False):
	'''
	Creates a grid of |columns_words.shape[1]| x |rows_words.shape[1]| that 
	are constrained such that each row and column contains only valid words as 
	per rows_words and columns_words and that the rows and columns intersect correctly
	you can contrain on the letters both in a boolean array, and as an integer.

	rows_words is a list with an item for each row, word_count x columns_words.shape[-1]
	columns_words is simply the same idea but transposed.
	items within are allowed to be None, which will result in no word constraints being applied
	'''

	W,H = len(columns_words), len(rows_words)
	lines = []
	for h in [1,0]:
		for d in range([W,H][h]):
			words = [columns_words, rows_words][h][d]
			lines.append([model.new_int_var(0, alphabet_size+1, f'{model.prefix}_{d}_{h}_letter_{i}') for i in range([H,W][h])])
			if words is not None:
				# `words` may already be a built automaton (start, finals, edges) -- e.g. the
				# linear-time minimal row DFA from position_independent_row_automaton -- in which
				# case use it directly; otherwise it is a 2D word matrix to compile.
				automaton = words if isinstance(words, tuple) else create_scrabble_automaton(words)
				model.add_automaton(lines[-1], *automaton[:3])

	rows, columns = lines[:H], lines[H:]

	# they must be equivalent at their intersections
	for i,row in enumerate(rows):
		for j,v in enumerate(row):
			model.add(columns[j][i] == v)
	
	# channel resulting integers to bitsets
	abc = list(range(1,alphabet_size + 1)) #max(words.max() for words in rows_words+columns_words)

	cells = {}
	for i,row in enumerate(rows):
		for j,v in enumerate(row):
			active = model.new_bool_var(f'{model.prefix}_{i+offset[0]}_{j+offset[1]}_cellactive')
			letter = {c:model.new_bool_var(f'{model.prefix}_{i+offset[0]}_{j+offset[1]}_{c}') for c in abc}
			model.add(sum(letter.values()) == active)

			model.add(v == 0).only_enforce_if(~active)
			for c,letter_active in letter.items():
				model.add(v == c).only_enforce_if(letter_active)

			cells[(j+offset[0],i+offset[1])] = Cell(active, letter, j+offset[0], i+offset[1], model.new_bool_var(f'{model.prefix}_{i+offset[0]}_{j+offset[1]}_blank'), v)

	return cells

def create_word_mapping(model, cells:dict[tuple[int,int], Cell], words:dict[tuple[int,int,bool,int], np.ndarray], alphabet_size:int) -> dict[tuple[int,int,bool,int], Slot]:
	'''
	indexes all possible word locations (x,y,h,n) to a variable that is true
	when a word is at that location

	specific coordinates can be limited to a specific set of words note that if the <none> word (all -1) 
	is provided then extra variables must be created.

	if a full dictionary is provided for a row or column than the constraints can be ommitted from the board construction
	'''
	W,H = max(x for x,y in cells.keys())+1, max(y for x,y in cells.keys())+1
	N = max(W,H)

	print('Creating word bindings')
	# there are "only" 2730 word positions on a 15² board
	# any can be active, or not. Easy to test by looking at cell activity
	pos = [(x,y,h,n) for x,y,h,n in product(range(W), range(H), [0,1], range(2,N+1)) if x*h + y*(n-h) + n <= W*h+H*(1-h) and (x,y) in cells]
	pos_active = {p: model.new_bool_var(f'{model.prefix}_{p}_active') for p in pos}
	
	slots = {}
	for j,((x,y,h,n),v) in enumerate(pos_active.items()):
		if j%50 == 0:
			print(f'{j}/{len(pos_active)}')
		w_cells = [cells[(x+i*h, y+i*(1-h))] for i in range(0, n)]
		lb = (~cells[(x-1,y)].active if x > 0 and h else h)
		rb = (~cells[(x+n,y)].active if x+n < W and h else h)
		tb = (~cells[(x,y-1)].active if y > 0 and not h else 1-h)
		bb = (~cells[(x,y+n)].active if y+n < H and not h else 1-h)
		model.add(sum(c.active for c in w_cells) + lb + rb + tb + bb == n+2).only_enforce_if(v)
		model.add(sum(c.active for c in w_cells) + lb + rb + tb + bb  < n+2).only_enforce_if(~v)

		word = [cell.letter_int for cell in w_cells]
		if words is not None and (x,y,h,n) in words:
			# if a word must be placed we can operate directly on the board state
			# otherwise we need an internal representation of the word that is conditionally channeled to the board state
			_words = words[(x,y,h,n)]
			if any((_words==[-1]*n).all(1)):
				word = [model.new_int_var(0, alphabet_size+1, f'{model.prefix}_slot_{x}_{y}_{h}_{n}_letter_{i}') for i in range(n)]
				for cell, c in zip(w_cells, word):
					model.add(cell.letter_int == c).only_enforce_if(v)
			else:
				model.add(v == 1)

			_words = _words[_words.min(-1)>=0,:]
			if _words.shape[0] <= 1200:
				model.add_allowed_assignments(word, _words)
			else:
				model.add_automaton(word, *create_scrabble_automaton(_words)[:3])

		slots[(x,y,h,n)] = Slot(v, x,y,h,n, w_cells, word)

	return slots

def single_component(model, cells:dict[tuple[int,int], Cell], start:tuple[int, int]):
	'''
	Adds constraints to cells that guarantee that all active cells form a single component
	the location of `start` must be active. (W//2, H//2) in normal scrabble
	'''
	LONGEST_PATH = len(cells)//4
	depth = {p:model.new_int_var(0, LONGEST_PATH, f'{model.prefix}_{p}_depth') for p in cells}
	for (x,y), cell in cells.items():
		d = depth[(x,y)]
		if (x,y) != start:
			# all active cells must have a valid depth
			model.add(d == LONGEST_PATH).only_enforce_if(~cell.active)
			model.add(d < LONGEST_PATH).only_enforce_if(cell.active)
			# and must be connected
			connected = []
			for p in [(x-1, y), (x+1, y), (x, y-1), (x, y+1)]:
				if p in cells:
					v = model.new_bool_var(f'{model.prefix}_isconnected_{x}_{y}->{p}')
					model.add(depth[p] == d-1).only_enforce_if([v, cell.active])
					connected.append(v)

			model.add(sum(connected) > 0).only_enforce_if(cell.active)

	if start:
		model.add(cells[start].active == 1)
		model.add(depth[start] == 0)
	
	return depth

def limit_letter_count(model, cells:dict[tuple[int,int], Cell], letter_count:dict[int,int]):
	'''
	Adds constraints to cells such that the total letter count is with
	the provided `letter_count` which simply maps alphabet indices to maximum count
	blanks are taken into acount and won't add to the total letter count
	'''
	for c, limit in letter_count.items():
		assert c > 0, "Zero character is reserved for <empty>"
		lettercount = 0
		for cell in cells.values():
			v = model.new_bool_var(f'{model.prefix}_letter_is_active_{cell.x}_{cell.y}_{c}')
			model.add(v == 0).only_enforce_if(cell.blank)
			model.add(v == cell.letter[c]).only_enforce_if(~cell.blank)
			lettercount += v
		model.add(lettercount <= limit)

def estimate_score(model, slots:dict[tuple[int, int, bool, int], Slot], word_multiplier, letter_multiplier, multiplier_active, scores, scoring_positions:set[tuple[int,int,bool,int]]=[], bingo=False):
	'''
	Will do total score estimation of a board with many options
	for single turns this scoring is (when well configured) perfectly calculated
	but for total game score this function will do a 'one shot' approach that is
	inaccurate.

	word_multiplier and letter_multiplier contain tuples (multiplier, active)
	active is allowed to be a constant
	'''
	W,H = max(x+(n-1)*h for x,y,h,n in slots.keys())+1, max(y+(n-1)*(1-h) for x,y,h,n in slots.keys())+1
	score = 0

	# to find out the word-multiplication factor of each word position
	# we need to assign the multipliers. We start by assigning each multiplier
	# to either the vertical or horizontal direction.
	mult_dir = {(x,y):model.new_bool_var(f'{model.prefix}_mult_dir_{x}_{y}') for x,y in product(range(W), range(H))}

	print('Binding words to score')
	# and we can sum score as a sum over those active word locations
	for j, ((x,y,h,n),slot) in enumerate(slots.items()):
		v = slot.active
		if scoring_positions and (x,y,h) not in scoring_positions:
			continue

		if j%50 == 0:
			print(f'{j}/{len(slots)}')

		if n >= 8 and bingo:
			score += v*50

		positions = [(x+i*h, y+i*(1-h)) for i in range(0, n)]

		# get active multiplication
		options = {(x,y): word_multiplier[y][x] for (x,y) in positions if (x,y) in mult_dir}
		# all subsets of positions [[(x,y), ...], ...] that contain a word multiplier
		subsets = list(chain(*[combinations(options.keys(), i) for i in range(len(options)+1)]))
		# and their (unique) possible effective scores multipliers if activated
		multis  = sorted({prod(options[p] for p in s) for s in subsets})
		
		# a variable for which exact subset is actived
		subset_vars = {s:model.new_bool_var(f'{model.prefix}_p{x}_{y}_{h}_{n}_s{s}') for s in subsets}
		# a variable for which specific multiplication factor is activated
		multi_vars = {m:model.new_bool_var(f'{model.prefix}_p{x}_{y}_{h}_{n}_m{m}') for m in multis}
		model.add(sum(multi_vars.values()) == 1)
		
		# a specific multiplier is activated when one of it's compatible subsets is
		for m in multi_vars:
			# the subsets of tiles that create the word multiplier m
			subsets_m = [subset_vars[s] for s in subsets if prod(options[p] for p in s) == m]
			model.add(multi_vars[m] <= sum(subsets_m))

		# and a subset can only be actived when all its specific multiplier tiles are active
		for subset in subsets:
			for pos in [p for p in subset if p in multiplier_active]:
				model.add(subset_vars[subset] <= multiplier_active[pos])

		# and we can filter subsets
		for m, multi_active in multi_vars.items():
			for cell in slot.cells:
				binding = {c:model.new_bool_var(f'{model.prefix}_p{x}_{y}_{h}_{n}_l{c}_m{m}') for c in range(1,27)}
				for c,letter_active in binding.items():
					assert c > 0, "<zero> is reversed for <empty>"
					model.add(letter_active == 1).only_enforce_if([cell.letter[c], v, ~cell.blank, multi_active])
					for w in [~cell.letter[c], ~v, cell.blank, ~multi_active]:
						model.add(letter_active == 0).only_enforce_if(w)

					base_score = m*scores[c]
					# we need this if we want dynamic multipliers (eg: for max turn scores)
					# score += letter_active * (scores[c]*m)
					# score += double_active * (scores[c]*m)
					# score += triple_Active * (scores[c]*m)
					# where double and triple active are triggered by dynamic letter_multiplier
					score += letter_active * base_score
					if letter_multiplier[cell.y][cell.x] > 1:
						if (cell.x, cell.y) in multiplier_active:
							lmum_active = model.new_bool_var('lmul_active')
							model.add(lmum_active == 0).only_enforce_if(~letter_active)
							model.add(lmum_active == 0).only_enforce_if(~multiplier_active[(cell.x, cell.y)])
							model.add(lmum_active == 1).only_enforce_if(letter_active, multiplier_active[(cell.x, cell.y)])
							score += lmum_active * (letter_multiplier[cell.y][cell.x]-1)*base_score
						else:
							score += letter_active * (letter_multiplier[cell.y][cell.x]-1)*base_score

	return score

def read_board_state(solver, cells, alphabet):
	W, H = max([x for x,y in cells])+1, max([y for x,y in cells])+1
	lines = [[0]*W for i in range(H)]
	for (x,y), cell in cells.items():
		active_letter = [c for c,v in cell.letter.items() if (b if isinstance(v, bool) else solver.Value(v))]
		if active_letter:
			lines[y][x] = alphabet.to_str(active_letter)

	return lines

def do_solve(model, cores = 8, log = True, time_limit = 0, extra_probing = 0, linearization_level = -1, optimize_with_core = False, callback = None):
	'''
	Applies solver to model and returns solved state of vars
	you can modify the solver and iterate for more solutions

	extra_probing: add N extra diversified copies of the probing_max_lp subsolver (the
		portfolio's dedicated objective lower-bound prover). extra_subsolvers are pushed to
		the front of the portfolio and each gets a distinct seed, so they close the bound
		from different angles in parallel. Helps when the bottleneck is *proving* optimality.
	linearization_level: if >=0, override the global LP strength (2 = max LP).
	optimize_with_core: enable core-based (implicit-hitting-set / max-HS) objective search.
		Historically left off here ("takes a lot of memory and barely helps"); exposed as a
		parameter so we can measure its help-vs-memory tradeoff (experiment 23).
	'''
	solver = cp_model.CpSolver()
	solver.parameters.log_search_progress = log
	solver.parameters.num_search_workers = cores
	solver.parameters.optimize_with_core = optimize_with_core
	# more iters takes long and has no benefit in my tests
	solver.parameters.max_presolve_iterations = 1
	if extra_probing:
		solver.parameters.extra_subsolvers.extend(["probing_max_lp"] * extra_probing)
	if linearization_level >= 0:
		solver.parameters.linearization_level = linearization_level
	if time_limit:
		solver.parameters.max_time_in_seconds = time_limit

	while True:
		if solver.Solve(model, callback) in [cp_model.FEASIBLE, cp_model.OPTIMAL]:
			yield solver
		else:
			break
