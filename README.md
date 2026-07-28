# scrabble4 — maximale-score-onderzoek op het dutch2026-lexicon

**🎯 [Interactieve record-viewer →](https://boblucas.github.io/scrabble4/)** — stap zet voor zet door
het 4787-punten-recordspel, de bewezen-optimale Nederlandse 2102-beurt én de bewezen-optimale Engelse (NWL) 1786-beurt.

Onderzoek naar twee extremale Scrabble-vragen op een standaard 15×15-bord (dutch2026-lexicon,
102 stenen incl. 2 blanco's):

1. **Max-turn**: wat is de hoogst mogelijke score van één beurt?
   → **2102 punten, BEWEZEN optimum** (~9,8 miljard combinaties beslist; witness + volledige
   certificaat-keten). Hoofdwoord `geschenkcheques` over drie triple-word-squares (×27).
   **Engels (NWL): 1786 punten, eveneens BEWEZEN optimum** (`oxyphenbutazone`) — het eerste
   bewezen Engelse max-turn-optimum; zie
   [`experiments/results/english/THEOREM_NWL_1786.md`](experiments/results/english/THEOREM_NWL_1786.md).
2. **Maxgame**: wat is de hoogst mogelijke totaalscore van een volledig legaal gespeeld spel
   (beide spelers samen, elke tussenstand geldig)?
   → **4787 punten, huidig record** (letterinvulling bewezen optimaal per voetafdruk via CP-SAT) (volledig bereikbare zetreeks, onafhankelijk geverifieerd).
   Zie [`experiments/MAXGAME_FINDINGS.md`](experiments/MAXGAME_FINDINGS.md) voor het volledige
   verslag (3974 → 4787, alle hefbomen en negatieve resultaten) en
   [`experiments/results/maxgame_BEST.json`](experiments/results/maxgame_BEST.json) voor het spel zelf.

## Maxgame-record in het kort

`geschenkcheques` (rij 0, ×27) / `flexwerkstertje` (rij 7, ×9) / `polymelkzuurtje` (rij 14, ×27),
101 stenen, 1 blanco, 9 opbouw-bingo's: 7 verticaal + 2 horizontaal (`emigrante` rij 4, en een 9e op
rij 12 over de DWS) — gevonden via structurele analyses (bob) + geautomatiseerde mask-swap-sweep + footprint-CP-SAT. Elke tussenstand is een geldige
bordpositie; de arbiter (`experiments/maxgame_score.py::score_game`) hervalideert het hele spel.

## Architectuur

- **Hot path in Rust** (`experiments/mg_full.rs`, één binary): pre-bord-solver (component-DFS),
  verrijking (bingo-lijnen + blanco-wildcards), score-maximale decompositie (beam/DP tot miljoenen
  staten), LNS-buurt-recombinatie en een exacte-DP-modus.
- **Python voor precompute en verificatie**: woordenlijst/premie-dumps en de eindarbiter
  `score_game`; elke recordclaim vereist een exacte match Rust↔Python (`experiments/mg_verify_rust.py`).
- **Zoek-orkestratie**: `experiments/mg_rustfleet.sh` (parallelle waves),
  `experiments/mg_lns_ladder.sh` (evolutionaire LNS-generaties),
  `experiments/mg_triple_scan.sh` (triple-sluitbaarheids-scan).

## Max-turn-certificering (N=15 = 2102)

De max-turn-tak (o.a. `experiments/xfill*`, `experiments/n15_*`, `experiments/35_certify.py`)
bewijst het beurt-optimum via enumeratie + streaming-certificaten + CP-SAT-residuen; details en
geschiedenis in `experiments/MAXGAME_PROOF.md` en de commit-log. Kernles van het hele project:
**de checker definieert het spel** — elke modelaanname (bv. een cross-woord-lengtecap) moet tegen
de witness-checker getest worden.

## Reproductie (maxgame)

```bash
rustc -O -C target-cpu=native experiments/mg_full.rs -o experiments/mg_full_bin
# precompute-dumps (woorden/premies) en env-setup: zie experiments/mg_rustfleet.sh
experiments/mg_rustfleet.sh geschenkcheques flexwerkstertje polymelkzuurtje 44 400 90 34 22
# verificatie van een SCORED-regel:
VR0=... VR7=... VR14=... MINPROMOTE=... python experiments/mg_verify_rust.py "<SCORED-regel>"
# het record zelf her-verifiëren:
python - <<'PY'
import json,sys,os; sys.path[:0]=['.','experiments']; os.environ['N15_LANG']='dutch2026'
import maxgame_score as MG
D=json.load(open('experiments/results/maxgame_BEST.json'))
print(MG.score_game(D['grid'],[[tuple(c) for c in m] for m in D['moves']],set(map(tuple,D['blanks']))))
PY
```

NB: twee >100MB oracle-ledgerbestanden (max-turn-artefacten) zijn uit de git-historie gefilterd
vanwege GitHub-limieten; alle code en resultaten zijn compleet.
