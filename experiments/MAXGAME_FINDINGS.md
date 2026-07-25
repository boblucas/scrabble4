# MAXGAME: het maximale-totaalscore-spel (dutch2026) — 3974 → 4399 (+10,7%)

**Resultaat:** het hoogste bekende volledig-bereikbare Scrabble-spel (beide spelers gecombineerd,
dutch2026-lexicon): **4399 punten** (stand 2026-07-25, 7e+8e-bingo-doorbraak `ranziger`/`emigrante` — bob's structurele inzichten; het intro hieronder beschrijft de 4319-fase)

(historisch intro:) **4319 punten** — `geschenkcheques` (rij 0, ×27) / `flexwerkstertje` (rij 7, ×9)
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

## Addendum (2026-07-24): maskergroottes + bouwcuratrixjes-eliminatie

**Maskergrootte-aanname gevalideerd.** Variabele maskers (3-7 cellen per slotzet) toegevoegd aan
de pipeline (`MGSIZES`, per rij instelbaar; tegel-cap dynamisch 101−Σ|masker|):
- size-5 op de record-triple: **bestaat niet** (geen pre-run-legale configuratie);
- pure size-6: prep-record 818 maar finals −458 (bingo's + DLS-dekking weg) → netto veel slechter;
- gemengd (alleen rij 7 kleiner): top 4266 (prep 809, finals 3457) → −55 t.o.v. record.
Masker=7 is dus optimaal voor de record-triple.

**Bouwcuratrixjes-familie (rank 1) definitief geëlimineerd — via de maskergrootte-ontdekking.**
De connectiviteits-analyse (`mg_connect_analysis.py`: per (kolom,rij) exhaustief uit het lexicon
of een verticale verbinding bestaat; noodzakelijke voorwaarde per segment) toonde: rij 0 heeft
maar 6 legale maskers; totaal 18.600 combo's. De EXHAUSTIEVE sweep daarover (25.028 gesloten
borden!) onthulde: de familie sluit WÉL — de oude "onbouwbaarheid" was een artefact van de
masker=7-aanname — maar **max finals over alle combo's = 3319** en top-totaal 4000. Zelfs met
record-klasse prep (~790) en exacte-DP-polish blijft het plafond ~4160, ruim 150 onder 4321.
De proxy-"jackpot" (kern 3884) bestond nooit: die maskers zijn pre-run-illegaal.

Dit valideert het eliminatieladder-patroon voor een toekomstig optimaliteitsbewijs:
per familie (exhaustieve finals-max over de maskerruimte) + (prep-bovengrens) < 4321 ⇒ familie weg.

## Optimaliteitsbewijs: status en gemeten muren (2026-07-24)

**Pijler 1 — frame-lemma (RIGOUREUS, af):** finals-mains ≤ 4005 (zak-gerelaxeerd); de
(3,3,2)-TWS-partitie is bewijsbaar optimaal (beste alternatief ≥300 lager); center-lemma:
de lijn-7-slotzet krijgt nooit ×18 (zet 1 dekt het center en kan geen 15-lijn voltooien).
Hoogste lijn-waarde in het lexicon: `croquemboucheje` (63).

**Pijler 2 — sound extra-bovengrens (E*): DRIE relaxaties gemeten, alle ≥2-3× realiteit:**
1. Per-cel-kruisrelaxatie: F*(rank13)=5829 vs gerealiseerd 3559 (7 cellen claimen elk de q).
2. Lexicon-ketting-DP: kettingen zelf mooi gecapt (`fox→…→foxysten`, 135 kaal voor 8 tegels,
   nesting-diepte ~6) — maar elke tegel scoort in TWEE richtingen en sound-separabel telt beide
   vol: extra-UB ≈ 2000+ vs gerealiseerd 896.
3. Per-tegel-dieptebound: zelfde probleem, ×wm-stapeling maakt het erger.
**Structurele conclusie:** de maxgame-score is orde-afhankelijk (ketting-herscoring) — "bordwaarde"
is zelf al een max over exponentieel veel ordeningen. Elke separabele relaxatie gooit precies de
verstrengeling weg (gedeelde letters; kruisingen die in beide richtingen op elk moment woorden
moeten zijn) die de realiteit begrenst. Dit is waarom max-turn (2102) wél bewijsbaar was
(beurtscore is orde-vrij, per-combinatie beslisbaar) en maxgame fundamenteel moeilijker is.

**Pijler 3 — per-familie mains-max-frontier (exact, masker-legaal, center-lemma):** loopt;
gecached per (woord,rol). Dit is de rigoureuze per-familie-component; met de gemeten E*-muur
volstaat hij niet voor massa-eliminatie, wel voor het uitsluiten van de staart en het prioriteren
van exhaustieve per-familie-sweeps (rank1-stijl, 18.600-combo's bewezen haalbaar per familie).

**Eerlijke eindstatus:** een volledig aannamevrij optimaliteitsbewijs vergt per-familie complete
beslisprocedures (B&B over pre-borden met de exacte decompose-DP als inner) — een
onderzoeksprogramma van maanden, analoog aan maar zwaarder dan de 2102-campagne. Rigoureus
staat nu: LB=4321 (geverifieerd spel), frame-structuur afgedwongen, per-familie mains-grenzen,
en exhaustieve eliminaties van de onderzochte families. Geconjectureerd optimum: ~4330-4360.
