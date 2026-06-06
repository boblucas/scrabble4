"""
Shared turn renderer + persistence for the holistic max-turn search (exp28 / exp29).

The holistic solver only logs the SCORE; the actual placement (which verticals, which
bridges, which tile is a blank) lives in the solver's variable assignment and is lost the
moment the process exits. For a month-long N=15 run we must NOT have to re-solve just to
look at the board -- so when a winner is found we extract it here and write a viewable
artifact (both the pre-turn setup board and the post-turn board, blanks shown as '*').

Glyph legend in the rendered board:
    .      empty cell
    A      a normal tile (main-word tile or a vertical-word tile)
    a      a connectivity BRIDGE tile (lowercased so it stands out)
    *      a BLANK tile (per request) -- the letter it represents is listed in the legend
On the PRE-turn board, the newly-placed (UPPERCASE in turn_str) row-0 tiles are absent --
they are exactly the tiles the scoring turn puts down.
"""


def chosen_from_solver(solver, xv, cands, scoring):
    """Return {col: (word_tuple, score)} for the picked vertical in each scoring column."""
    chosen = {}
    for c in scoring:
        for i, (w, sc, rq) in enumerate(cands[c]):
            if solver.Value(xv[(c, i)]):
                chosen[c] = (w, sc)
                break
    return chosen


def render(solver, cells, chosen, turn_str, rules, main_score=None, vert_score=None):
    """Build a human-readable text block: pre-turn board, post-turn board, and a legend.

    chosen: {col: (word_tuple, score)} from chosen_from_solver.
    """
    W, H, abc = rules.W, rules.H, rules.alphabet
    vert_cells = {(c, ri) for c, (w, _) in chosen.items() for ri in range(len(w))}

    def active(x, y):
        return bool(solver.Value(cells[(x, y)].active))

    def is_blank(x, y):
        return bool(solver.Value(cells[(x, y)].blank))

    def letter_at(x, y):
        cell = cells[(x, y)]
        for code, bv in cell.letter.items():
            if solver.Value(bv):
                return abc.to_str([code])
        return '?'

    blanks = []   # (x, y, letter)
    for (x, y) in cells:
        if active(x, y) and is_blank(x, y):
            blanks.append((x, y, letter_at(x, y)))

    def glyph(x, y, pre_turn):
        if y == 0:                                   # row 0 = the main word. Scoring cols are stored
            if pre_turn and turn_str[x].isupper():   # INACTIVE in the setup model (they are the tops
                return '.'                           # of the verticals), so read row 0 from turn_str:
            return turn_str[x].upper()               # pre-turn shows only pre-placed; post shows all
        if not active(x, y):
            return '.'
        if is_blank(x, y):
            return '*'                               # blank tile (per request); letter is in the legend
        lt = letter_at(x, y).lower()
        if (x, y) in vert_cells:
            return lt.upper()                        # part of a chosen scoring vertical
        return lt                                    # connectivity bridge / cross-word fill tile (lowercase)

    def grid_text(pre_turn):
        out = []
        for y in range(H):
            out.append('   ' + ' '.join(f'{glyph(x, y, pre_turn):>2}' for x in range(W)))
        return '\n'.join(out)

    L = []
    tot = (main_score or 0) + (vert_score or 0)
    L.append(f"turn = {turn_str}   main={main_score}  verticals={vert_score}  TOTAL={tot}")
    L.append("")
    L.append("PRE-TURN board (what is on the board BEFORE the scoring turn; '*' = blank):")
    L.append(grid_text(pre_turn=True))
    L.append("")
    L.append("POST-TURN board (after playing the turn; UPPERCASE row-0 = newly placed; lowercase = bridge; '*' = blank):")
    L.append(grid_text(pre_turn=False))
    L.append("")
    L.append("chosen scoring verticals (top tile = the main-word letter placed this turn):")
    for c in sorted(chosen):
        w, sc = chosen[c]
        L.append(f"   col {c:2d}: {abc.to_str(w):20} len={len(w):2d}  score={sc}")
    if blanks:
        L.append("blank tiles (drawn as '*'):")
        for x, y, lt in blanks:
            L.append(f"   ({x},{y}) plays as '{lt}'")
    else:
        L.append("blank tiles: none")
    return '\n'.join(L)


def save(path, text, header=''):
    with open(path, 'w') as f:
        if header:
            f.write(header.rstrip('\n') + '\n\n')
        f.write(text + '\n')
    return path


# A solution callback that checkpoints the board on every improving incumbent. The holistic for a
# single hard main word can solve for hours/days (N=15); without this we would only see the board
# when Solve() finally returns, and a crash mid-proof would lose everything. With it, the latest
# incumbent placement is always on disk and viewable.
from ortools.sat.python import cp_model


class SaveBoardCallback(cp_model.CpSolverSolutionCallback):
    def __init__(self, cells, xv, cands, scoring, turn_str, rules, path,
                 main_score=None, header='', verbose=True):
        super().__init__()
        self._cells, self._xv, self._cands, self._scoring = cells, xv, cands, scoring
        self._turn, self._rules, self._path = turn_str, rules, path
        self._main, self._header, self._verbose = main_score, header, verbose
        self.best = None

    def on_solution_callback(self):
        obj = int(self.ObjectiveValue())
        if self.best is not None and obj <= self.best:
            return
        self.best = obj
        chosen = chosen_from_solver(self, self._xv, self._cands, self._scoring)
        text = render(self, self._cells, chosen, self._turn, self._rules,
                      main_score=self._main, vert_score=obj)
        save(self._path, text, header=f"{self._header}  incumbent verticals={obj}")
        if self._verbose:
            print(f"\n[checkpoint] new incumbent verticals={obj} -> {self._path}\n{text}\n", flush=True)
