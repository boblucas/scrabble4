# MAXGAME: het maximale-totaalscore-spel (dutch2026) — 3974 → 4319 (+8,7%)

**Resultaat:** het hoogste bekende volledig-bereikbare Scrabble-spel (beide spelers gecombineerd,
dutch2026-lexicon): **4319 punten** — `geschenkcheques` (rij 0, ×27) / `flexwerkstertje` (rij 7, ×9)
/ `polymelkzuurtje` (rij 14, ×27), 40 zetten, 101 tegels, 1 blanco, elke tussenstand legaal,
onafhankelijk geverifieerd door de Python-arbiter `score_game`. Zie `results/RECORD_4319.txt`
(leesbaar) en `results/maxgame_BEST.json` (machine-leesbaar, her-verifieerbaar).

## Het spelmodel

Framework (Bob): twee ×27-woorden op rij 0 en 14 (elk drie TWS), één ×9-woord op rij 7 (center-DWS
al gespend door de opening), alle overige tegels als voorbereidende zetten. De drie ankerrijen
worden afgesloten met een 7-tegel-"slotzet" (de 7 masker-cellen); de overige 8 cellen per rij
("pre-cellen") liggen er dan al. Arbiter: `maxgame_score.score_game` — valideert elke tussenstand
(alle runs ≥2 zijn dict-woorden), zak-boekhouding, center-start, connectiviteit. Reserve-regel:
de tegenstander houdt ≥1 tegel ⇒ bord ≤101 tegels.

## Architectuur (volledig-Rust hot-path)

`mg_full.rs` (één binary, ~700 regels) bevat de complete pijplijn; Python doet alleen eenmalige
precompute (woordenlijsten, premietabellen, maskercombo's) en de **eind-verificatie** vóór elke
recordpromotie (`mg_verify_rust.py` → `score_game`, exacte match vereist). Cross-validatie: elke
gepromoveerde score matchte exact (rust_total == python_total) — de Rust-scorer is een bewezen
correcte port.

Pijplijn per poging:
1. **Solver**: pre-bord-constructie (alleen pre-cellen + kol-7-opening) → brug-ruggengraat
   (8-woorden) → component-getargete DFS (korte stubs/rungs) tot 1 verbonden component
   (= decomposeerbaar naar een echte zetreeks).
2. **Verrijking** (`RUST_ENRICH`): resterende zaktegels als lange stubs (voorkeur 7-nieuwe-tegels
   = bingo-lijn), incl. **blanco-wildcards** (`RUST_NBLANK`).
3. **Beam-decompose**: zoek de score-maximale zetvolgorde/groepering (staat = geplaatst-set;
   dedup per bitset met max-cumscore = correcte DP; beam W begrenst de frontier).
4. Slotzetten-scoring + uitvoer (bord + zetreeks + blanks) → Python-verificatie.

## De hefbomen, in volgorde van ontdekking en impact

| # | hefboom | winst | inzicht |
|---|---------|-------|---------|
| 1 | Score-max decompose | 3974→~4100 | de score van een VAST bord hangt af van de zetvolgorde (bingo-groepering, ketting-herscoring) |
| 2 | Rust-port (~100×) | →4158 | doorvoer maakt bord-variatie betaalbaar |
| 3 | Triple-keuze | →4211 | finals variëren per R7-woord; top-core triples sluiten vaak NIET |
| 4 | Combo-concentratie | →4265 | alle restarts op hét beste maskercombo i.p.v. verdeeld |
| 5 | 7e-bingo-verrijking (Bob) | +12-15/bord | leftover-tegels als 7-lijnen i.p.v. dribbels |
| 6 | **LNS-ladder** | →4309 | evolutionair buurt-zoeken (behoud structuurgroepen met kans p, hervul rest): 20× sluitingsdichtheid, co-evolueert prep én finals |
| 7 | Blanco-wildcards | in record | blank scoort 0 maar telt voor de +50-bonus; bord-cap 101 |
| 8 | **Exacte decompose-DP** | →4319 | wide-beam DP (W=4-10M states, ~50GB) op het beste bord: +10 die beam-34 miste — méér, kleinere zetten om ketting-herscores te oogsten |

## Negatieve resultaten (drie keer onafhankelijk bevestigd waar relevant)

- **Value-bias** in solver-woordkeuze: slechter (doodt diversiteit; de beam extraheert prep toch).
- **Finals-adjacency** (TWS-buurcel-kruiswoorden sturen): finbias, pre-seed én post-sluiting-stubpas
  — alle drie nul effect; de kruiswoord-legaliteit naast maskercellen laat structureel bijna niets toe.
- **Beam-verbreding zonder meer** (34→96) op bestaande borden: nul — pas de sprong naar W=miljoenen
  (echte DP) vond de +10.
- **Top-core triples (bouwcuratrixjes-familie, ~4300 kern-potentieel)**: sluiten NIET, ook niet bij
  600 restarts/combo — de ankermaskers fragmenteren de pre-cel-connectiviteit onherstelbaar.
- **Globale analytische UB's**: structureel te los door (a) prep/finals-tegeldeling en (b)
  ketting-herscoring (een kolom als `wegknip`→`wegknipt` herscoort de hele run per verlenging).
  De oude "klasse-UB 4324" gold alleen voor de oude flauwekulexcuus-skeletfamilie, niet voor deze.

## Verificatie-discipline

Elke record-claim doorloopt: (1) Rust-uitvoer bevat de volledige zetreeks + blanco-cellen,
(2) `mg_verify_rust.py` herbouwt het spel en draait de échte Python-`score_game`,
(3) promotie alleen bij `ok=True` én exacte score-match. De arbiter definieert het spel;
elke modelaanname wordt tegen de arbiter getest (les uit de HMAX=8-geschiedenis van dit project).

## Reproductie

```bash
# precompute (eenmalig): woorden/premies dumpen
python experiments/maxgame_precompute-achtig  # zie mg_rustfleet.sh env-setup
rustc -O -C target-cpu=native experiments/mg_full.rs -o experiments/mg_full_bin
# fleet:    experiments/mg_rustfleet.sh R0 R7 R14 NWORKERS NREST TLMS BEAMW MAXCOMBOS
# ladder:   experiments/mg_lns_ladder.sh GENS WORKERS NREST TLMS BEAMW   (pool: $TMP/lnspool.txt)
# exact-DP: DECOMP_ONLY=1 MGBEAMW=8000000 experiments/mg_full_bin < SCORED-regels
# verify:   VR0=... VR7=... VR14=... MINPROMOTE=... python experiments/mg_verify_rust.py "<SCORED-regel>"
```

## Open eindes

- Verliesvrij DP-bewijs van het bordoptimum (frontier piekt ~7M states; W=8-10M loopt).
- Een geldige klasse-UB voor deze triple-familie bestaat nog niet (de scherpe route is
  bord-conditionele exactheid + exhaustie over enumereerbare dimensies zoals maskercombo's).
- LNS-ladder met beam-128-evaluatie (loopt) — dichtere ranking kan de buurt verder openen.
