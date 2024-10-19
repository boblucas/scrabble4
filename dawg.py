# DAWG was copied from LEXPY (https://github.com/aosingh/lexpy/tree/main) with minor
# changes to support ordered collections of arbitrary comparable objects 
# instead of just strings. Most features except building the automaton were removed
from collections import defaultdict
from itertools import product
import numpy as np

T_ANY = -1
T_NONE = -2

def automaton_words_from_dict(fixed_words:dict[int, list[int]], row:list[set[int]]):
    '''
    the input for `create_scrabble_automaton` is a 2D matrix representating
    all words at all positions in a row. This function creates such a matrix
    from a `position -> word list` dict, where the words are lists of integers. 
    Row is a static filter of valid letters. -1 specifies that anything
    is allowed. <= -2 specifies that that tile must remain empty.
    '''
    max_depth = len(row)
    aligned_words = []
    if all(T_ANY in row[i] or T_NONE in row[i] for i in range(max_depth)):
        aligned_words.append([0]*max_depth)

    for i,words in fixed_words.items():
        for w in words:
            if not w or i+len(w) > len(row): continue

            if i+len(w) < len(row): w = tuple([*w, -2])
            
            _i = i
            if i > 0:
                w = tuple([-2, *w])
                _i -= 1

            if all(T_ANY in row[_i+j] or w[j] in row[_i+j] for j in range(len(w))):
                w = tuple(max(0, x) for x in w)
                aligned_words.append([0]*_i + list(w) + [0]*(max_depth-_i-len(w)))
    
    return np.array(aligned_words, dtype=np.int8)

def automaton_words_from_list(words:list[tuple[int]], n:int, row:list[set[int]] = None):
    '''
    like the function above but simply puts all words at all positions
    '''
    if not row:
        row = [{T_ANY}]*n
    fixed_words = defaultdict(set)
    for i,w in enumerate(words):
        for i in range(n-len(w)+1):
            fixed_words[i].add(w)

    return automaton_words_from_dict(fixed_words, row)

def create_scrabble_automaton(words:np.ndarray):
    '''
    Creates an constant depth automaton that describes a valid row or column in a
    scrabble game. Each word (seperated by whitespace) must be in the dictionary.
    Visualise the nodes as the edges of the board spaces. node[0] means the left edge.
    node[max_depth] means the rightmost edge

    words is a 2D numpy matrix of shape (n, word length), -1 is used for padding.
    don't forgot the empty string.
    '''

    # positional encoding required for SAT translation
    # each character becomes (character, rank position, is start of word)
    max_depth = words.shape[-1]

    start_of_word = np.zeros_like(words)
    start_of_word[np.arange(words.shape[0]),np.argmax((words >= 0), axis=1)] = 1

    words = np.concatenate(
        (words[:,:,np.newaxis],
        np.repeat(np.arange(max_depth).reshape(1, max_depth, 1), words.shape[0], axis=0), 
        start_of_word[:,:,np.newaxis]),
        axis=2)

    dawg_words = [tuple(tuple(c) for c in w) for w in words]
    dawg = DAWG(sorted(dawg_words))
    nodes = defaultdict(lambda: len(nodes))
    edges, terminal, done = set(), set(), set()
    names = {}

    def get_node(node):
        _id = nodes[node.val] if node.val and node.val[0] <= 0 else nodes[node.id]
        names[(node, node.id)] = _id
        return _id

    stack = [dawg.root]
    while stack:
        node = stack.pop()
        if node in done: continue
        done.add(node)

        for _, child in node.children.items():
            edges.add((get_node(node), child.val[0], get_node(child)))
            stack.append(child)
    
    # connect all 'empty' tile nodes back into the FSA
    starts = {i:{} for i in range(max_depth)}
    empties = {i:{} for i in range(max_depth+1)}
    for node in dawg.all_nodes():
        if node.val[2]:
            starts[node.val[1]][get_node(node)] = node
        if node.val[0] <= 0:
            empties[node.val[1]][get_node(node)] = node
        
    for (node, _), automaton_id in names.items():
        if node.val and node.val[1] == max_depth-1:
            terminal.add(automaton_id)

    for depth in range(max_depth-1):
        for a,b in product(empties[depth].values(), starts[depth+1].values()):
            edges.add((get_node(a), b.val[0], get_node(b)))
    

    return (0, terminal, edges) #, {v:k.val for (k,_),v in names.items()}

class FSANode:
    __slots__ = 'id', 'val', 'children', 'count'
    def __init__(self, _id, val):
        self.id = _id
        self.val = val
        self.children = {}
        self.count = 0

    def add_child(self, letter, _id=None):
        self.children[letter] = FSANode(_id, letter)

    def __getitem__(self, letter):
        return self.children[letter]

    def __str__(self):
        strarr = [str(self.val), str(self.count)]
        for letter, node in self.children.items():
            strarr.append(str(letter))
            strarr.append(str(node.id))
        return "".join(strarr)

    def __eq__(self, other): return self.__str__() == other.__str__()
    def __hash__(self): return self.__str__().__hash__()
    def __repr__(self):  return f"FSANode(id={self.id}, label={self.val}, count={self.count}, children={len(self.children)})"

class DAWG:
    __slots__ = '_id', '_num_of_words', 'root', '__prev_word', '__prev_node', '__minimized_nodes', '__unchecked_nodes'
    def __init__(self, words, empty=[]):
        self._id = 1
        self._num_of_words = 1
        self.root = FSANode(1, None)

        self.__prev_word = tuple()
        self.__prev_node = empty
        self.__minimized_nodes = {}
        self.__unchecked_nodes = []

        for word in words:
            self.add(word)
        self.reduce()

    def get_word_count(self):
        return max(0, self._num_of_words - 1)

    def add(self, word, count=1):
        if word < self.__prev_word:
            raise ValueError(f"Words should be inserted in alphabetical order\n"
                             f"Previous word was '{self.__prev_word}' and current word is '{word}'")
        elif word == self.__prev_word:
            self.__prev_node.count += count
        else:
            # find common prefix between word and previous word
            common_prefix_index = 0
            for i, letters in enumerate(zip(word, self.__prev_word), start=1):
                if letters[0] != letters[1]:
                    break
                common_prefix_index = i

            self._reduce(common_prefix_index)

            if len(self.__unchecked_nodes) == 0:
                node = self.root
            else:
                node = self.__unchecked_nodes[-1][2]

            for letter in word[common_prefix_index:]:
                _id = self._id + 1
                node.add_child(letter, _id)
                self.__unchecked_nodes.append((node, letter, node.children[letter]))
                node = node.children[letter]
                self._id = _id

            node.count += count
            self.__prev_node = node

        self._num_of_words += count
        self.__prev_word = word

    def reduce(self):
        self._reduce(0)

    def all_nodes(self):
        return self.__minimized_nodes.values()

    def _reduce(self, to):
        for i in reversed(range(to, len(self.__unchecked_nodes))):
            parent, letter, child = self.__unchecked_nodes[i]
            if child.children and child in self.__minimized_nodes:
                parent.children[letter] = self.__minimized_nodes[child]
            else:
                self.__minimized_nodes[child] = child

            self.__unchecked_nodes.pop()

    def __len__(self):
        return len(self.__minimized_nodes)

def all_paths(automaton, N):
    connected = defaultdict(set)
    for f,v,t in automaton[2]:
        connected[f].add((v,t))
    
    total = 0
    def enum_paths(node, state=''):
        if len(state) == N:
            print(state)

        for v,t in connected[node]:
            enum_paths(t, state + chr(ord('a')+v-1))

    enum_paths(automaton[0])

def automaton_to_dot(automaton, names):
    print('start at', automaton[0])
    print('ends at', *automaton[1])
    for k,v in names.items():
        print(f'{k} [label="{k},{v}"]')

    for f,v,t in automaton[2]:
        print(f'{f} -> {t} [label="{chr(ord("a")+v-1)}"]')


if __name__ == '__main__':
    n = 3
    words = open('data/words/english').read().split('\n') + list('abcdefghijklmnopqrstuvwxyz') + ['']
    _words = [tuple([ord(c)-ord('a')+1 for c in w]) for w in words if len(w) <= n]
    
    auto = automaton_words_from_list(_words, n, [{-1},{5},{-1}])
    for row in auto:
        print(row, ''.join([chr(ord('a')+c-1) for c in row]))

    exit()

    import random
    random.seed(0)

    n = 3
    words = open('data/words/english').read().split('\n') + list('abcdefghijklmnopqrstuvwxyz')
    _words = [tuple([ord(c)-ord('a')+1 for c in w]) for w in words if len(w) == n]
    random.shuffle(_words)
    _words = sorted(_words[:20])
    fixed_words = automaton_words_from_list(_words, n)
    automaton, names = create_scrabble_automaton(fixed_words)
    #automaton = create_scrabble_automaton(9, words)
    print('custom reproduction:')
    all_paths(automaton, n)
    
    print('graph:')
    automaton_to_dot(automaton, names)

    print('or-tools reproduction:')
    from ortools.sat.python import cp_model
    model = cp_model.CpModel()
    line = [model.new_int_var(0, 26, f'letter_{i}') for i in range(n)]
    model.add_automaton(line, *automaton[:3])

    solver = cp_model.CpSolver()
    solver.parameters.log_search_progress = False
    solver.parameters.num_search_workers = 1
    solver.parameters.optimize_with_core = False
    solver.parameters.max_presolve_iterations = 1
    while solver.Solve(model) in [cp_model.FEASIBLE, cp_model.OPTIMAL]:
        board = ''.join([chr(ord('a')+solver.Value(line[i])-1) for i in range(n)])
        print(board)
        is_different = [model.new_bool_var(f'{board}_{i}') for i in range(n)]
        for i in range(n):
            model.add(line[i] != solver.Value(line[i])).only_enforce_if(is_different[i])
        model.add_bool_or(is_different)



