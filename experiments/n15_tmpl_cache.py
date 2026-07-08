"""Template-proto DISK-CACHE voor oracle-modellen op grote lexicons.

Probleem: _oracle_template bouwt het CP-SAT-model in Python (~20u op het 4,1M-woorden
ctc-lexicon) en dat gebeurde PER worker-proces.  Oplossing: bouw 1x, serialiseer
(model-proto binair + var-indexmap json); workers laden in seconden en reconstrueren
een CpModel + cells-facade met dezelfde var-indices.

build_cached_template(word, mask) -> (model, cells)  [drop-in voor _oracle_template]
Cache-key: (lexicon, HMAX, word, mask) -> bestand onder experiments/results/tmpl_cache/.
"""
import sys, os, json, time
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
from collections import namedtuple

ROOT = '/home/bob/programming/scrabble4'
CDIR = f'{ROOT}/experiments/results/tmpl_cache'
os.makedirs(CDIR, exist_ok=True)

CellF = namedtuple('CellF', ['active', 'letter', 'x', 'y', 'blank', 'letter_int'])


def _paths(word, mask):
    lex = os.environ.get('N15_LANG', 'dutch')
    hm = os.environ.get('N15_HMAX', '15')
    tag = f"{lex}_h{hm}_{word}_{'_'.join(str(c) for c in mask)}"
    return f'{CDIR}/{tag}.pb', f'{CDIR}/{tag}.idx.json'


def build_cached_template(word, mask):
    """Als _oracle_template maar met disk-cache. Retourneert (CpModel, cells) waar cells een
    facade is met var-objecten die naar de juiste proto-indices wijzen."""
    from ortools.sat.python import cp_model
    pb, idx = _paths(word, mask)
    import n15_twolevel as T
    if not (os.path.exists(pb) and os.path.exists(idx)):
        t0 = time.time()
        m, cells = T._oracle_template(word, mask)
        open(pb, 'wb').write(m.proto.SerializeToString())
        imap = {}
        for (x, y), cell in cells.items():
            imap[f'{x},{y}'] = {
                'active': cell.active.index,
                'blank': cell.blank.index,
                'letter_int': cell.letter_int.index,
                'letter': {str(c): v.index for c, v in cell.letter.items()},
            }
        json.dump(imap, open(idx, 'w'))
        print(f"# template gebouwd+gecached in {time.time()-t0:.0f}s -> {pb}", flush=True)
        return m, cells
    t0 = time.time()
    m = cp_model.CpModel()
    with open(pb, 'rb') as f:
        m.proto.ParseFromString(f.read())
    imap = json.load(open(idx))

    class _V:                                   # var-facade: alleen .index wordt gebruikt door
        __slots__ = ('index', '_m')             # de fix()/pen_terms/solution-paden

        def __init__(self, i, model):
            self.index = i
            self._m = model

        def __mul__(self, other):
            return NotImplemented

    # Voor pen_terms (coef * var) en sum() hebben we echte ortools-vars nodig: reconstrueer
    # lichte IntVar-wrappers via het model-proto (cp_model laat vars ophalen op index).
    def var_at(i):
        return m.get_int_var_from_proto_index(i)

    cells = {}
    for k, d in imap.items():
        x, y = (int(v) for v in k.split(','))
        cells[(x, y)] = CellF(
            active=var_at(d['active']), blank=var_at(d['blank']),
            letter_int=var_at(d['letter_int']),
            letter={int(c): var_at(i) for c, i in d['letter'].items()},
            x=x, y=y)
    print(f"# template geladen uit cache in {time.time()-t0:.1f}s", flush=True)
    return m, cells


def install(word, mask):
    """Monkeypatch n15_twolevel._oracle_template zodat oracle_beats_lb de cache gebruikt."""
    import n15_twolevel as T
    m, cells = build_cached_template(word, mask)
    T._FAST_TMPL[(word, tuple(mask))] = (m, cells)
    return m, cells


if __name__ == '__main__':
    w = sys.argv[1]
    mask = tuple(int(x) for x in sys.argv[2].split(','))
    build_cached_template(w, mask)
    print("OK")
