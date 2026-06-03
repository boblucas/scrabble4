from collections import *
from itertools import *
from functools import *
import numpy as np
import math
from dataclasses import dataclass
import toml
import os


@dataclass
class Alphabet:
	'''
	Conversion from string to np arrays
	we order alphabetically and encode as int8's, so that negative values are
	easily available to users. The 0 index is not used so that it can serve as
	a context dependend flag. Additionally you can then flag characters by 
	using -x.
	'''
	abc:list # idx -> str
	cba:dict # str -> idx

	def __init__(self, alphabet):
		assert len(alphabet) < 128, "To use alphabets beyond 127 characters please update code to use int16 instead of int8"
		self.abc = {i+1:c for i,c in enumerate(sorted(alphabet))}
		self.cba = {c:i+1 for i,c in enumerate(sorted(alphabet))}

	def __len__(self): return len(self.cba)
	def __iter__(self): return self.cba.keys()

	def to_str(self, array): return ''.join(self.abc[i] for i in array)
	def to_arr(self, string): return np.array([self.cba[c] for c in string], dtype=np.int8)
	def to_tup(self, string): return tuple(self.cba[c] for c in string)

	def to_arrays(self, strings):
		assert len(strings) == 0 or all(len(s) == len(strings[0]) for s in strings), "All strings must be equal length"
		return np.stack([to_arr(s) for s in strings])

@dataclass
class Rules:
	abc:str
	alphabet:Alphabet
	letters:list
	counts:dict
	scores:dict

	hand_size:int
	emptyhand_bonus:int
	blank_count:int

	N:int
	W:int
	H:int
	word_multiplier:np.ndarray
	letter_multiplier:np.ndarray

	words_str:set
	words:list
	words_lookup:set

def construct_rules(language, board, word_file=None, hand_size=7, emptyhand_bonus=50):
	''' Will create a rules object given a simple language and board name. '''
	LANG = toml.load('data/languages.toml')
	BOARD = toml.load('data/boards.toml')['board']

	if not word_file:
		word_file = f'data/words/{language}'
	if not language in LANG:
		raise ValueError(f'Unkown language {language} please add to languages.toml or choose from {", ".join(LANG.keys())}')
	if not board in BOARD:
		raise ValueError(f'Uknown board type, please add to boards.toml or choose from {", ".join(BOARD.keys())}')
	if not os.path.exists(word_file):
		raise FileNotFoundError(f"Could not find dictionary at {word_file}")

	l = LANG[language]
	blank_count = 0
	letters = sorted([(k.replace('_','*').lower(), l['letters'][k], l['bag'][k]) for k in l['bag']])
	if letters[0][0] == '*':
		blank_count = letters[0][2]
		letters = letters[1:]

	b = BOARD[board].strip().split('\n')
	N = max(len(b[0]), len(b))
	abc = ''.join([c for c,p,n in letters if c != '*'])
	words = (set(abc) | set(open(word_file).read().lower().split('\n'))) - {''}
	words = {w for w in words if len(w) <= N}
	alphabet = Alphabet(abc)
	return Rules(
		abc = abc,
		alphabet = alphabet,
		letters = letters,
		counts = Counter({alphabet.cba[c]:n for c,p,n in letters if c != '*'}),
		scores = {alphabet.cba[c]:p for c,p,n in letters if c != '*'},
		hand_size = hand_size,
		emptyhand_bonus = emptyhand_bonus,
		blank_count = blank_count,
		N = N, W=len(b[0]), H=len(b),
		word_multiplier = np.array([[int(c) if c.isnumeric() else 1 for c in row] for row in b]),
		letter_multiplier = np.array([[' _bcdef'.index(c) if c in 'bcdef' else 1 for c in row] for row in b]),
		words_str = words,
		words = [alphabet.to_tup(w) for w in words],
		words_lookup = set([alphabet.to_tup(w) for w in words])
	)


@cache
def prefixable(words):
	''' Returns all words that have the property that the first letter can be 
	removed while remaining a valid word. The words are grouped into sets by 
	that first letter.'''
	return defaultdict(set, {k:set(g) for k,g in groupby(sorted(x for x in words if x[1:] in words), key=lambda x: x[0])})

@cache
def postfixable(words):
	''' Returns all words that have the property that the last letter can be 
	removed while remaining a valid word. The words are grouped into sets by 
	that last letter.'''
	return defaultdict(set, {k:set(g) for k,g in groupby(sorted([x for x in words if x[:-1] in words], key=lambda x: x[::-1]), key=lambda x: x[-1])})

@cache
def pillars(words, N):
	''' Returns all words of length N that have the property that the first and
	last letter can be removed (in at least one ordering) while remaining a 
	valid word. The words are grouped into sets by combining those two letters'''
	return defaultdict(set, {k:set(g) for k,g in groupby(sorted([w for w in words if len(w) == N and w[1:-1] in words and (w[1:] or w[:-1] in words)], key=lambda w: w[0]+w[-1]), key=lambda w: w[0]+w[-1])})

Coord = namedtuple('Coord', ['x', 'y', 'h', 'n'])

@cache
def all_positions(W, H):
	''' all valid position on an empty board'''
	positions = []
	for x,y in product(range(W),range(H)):
		positions += [Coord(x,y,1,x2-x+1) for x2 in range(x,W)]
		positions += [Coord(x,y,0,y2-y+1) for y2 in range(y,H)]
	return positions

def valid_positions(board, W, H):
	''' all valid position on an given board with static tiles '''
	return [Coord(x,y,h,n) for x,y,h,n in all_positions() if not (
		(h and x > 0 and not board[y*W+x-1] in ' -') or 
		(h and x+n < W and not board[y*W+x+n] in ' -') or 
		(not h and y > 0 and not board[(y-1)*W+x] in ' -') or 
		(not h and y+n < H and not board[(y+n)*W+x] in ' -') or
		('-' in [board[(y+i*(1-h))*W+(x+i*h)] for i in range(n)] ))]

def tuple_to_npcount(w, abc):
	''' given a word return a |abc| sized array with letter counts '''
	return np.array([w.count(i) for i in range(len(rules.abc))], dtype=np.int8)

def word_to_npcount(w, abc):
	''' given a word return a |abc| sized array with letter counts '''
	return np.array([w.count(abc[i]) for i in range(len(abc))], dtype=np.int8)

def has_sufficient_tiles(input_counts, allowed_blanks, counts):
	''' given a N x |abc| matrix of letters counts, will return N sized matrix of booleans
	to signify all inputs where sufficient letters are available '''
	return np.sum(np.clip((counts - input_counts),-(allowed_blanks+1),0), axis=1) >= -allowed_blanks

def has_sufficient_tiles_single(text, allowed_blanks, counts, abc):
	return has_sufficient_tiles(np.array([word_to_npcount(text, abc)]), allowed_blanks, counts)

def sufficient_tiles(text, allowed_blanks, counts):
	''' returns all ways text can be valid with minimum amount of letters replaced by blanks'''
	allowed_blanks -= text.count('*')
	replacements = [(k, v-counts[k]) for k,v in Counter(text).items() if v > counts[k]]
	if sum(y for x,y in replacements) > allowed_blanks: return
	for pos in product(*[combinations([i for i,c in enumerate(text) if c==k], v) for k,v in replacements]):
		pos = set(chain(*pos))
		yield ''.join(['*' if i in pos else c for i,c in enumerate(text)])

def valid_subwords(w, words):
	return [(i, w[i:j]) for i in range(len(w)) for j in range(i+1, len(w)+1) if w[i:j] in words]

def get_word_score(rules, w, x, y, h, placed):
	'''
	Gives the score of placing a given word including multipliers applied for logging and verification
	'''
	score = 0
	wm = 1
	for i in range(len(w)):
		_x,_y = x+i*h, y+i*(1-h)
		s = rules.scores[w[i]]
		if placed[i]:
			s *= rules.letter_multiplier[_y,_x]
			wm *= rules.word_multiplier[_y,_x]
		score += s
	return score*wm + (sum(placed) == rules.hand_size) * rules.emptyhand_bonus, wm