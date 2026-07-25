# STELLING: max-turn(NWL, standaard 15x15) = 1786

De hoogst mogelijke score van een enkele Scrabble-beurt onder NWL-lexicon en volledige regels
(zak/blanco's, tail-legaliteit, opzet-bord-legaliteit, reserve) is EXACT 1786 punten.

## Bewijs (5 componenten)
1. WITNESS: oxyphenbutazone-bord scoort 1786 (officiele checker: WITNESS OK; N15_best_1786.json).
2. 15-LETTER-HOOFDWOORDEN, veeg: gesloten-vorm colbest-UB over alle 3.839 NWL-15-woorden;
   slechts 2 woorden hebben UB > 1786: oxyphenbutazone (1839) en psychoanalyzing (1797).
3. OXYPHENBUTAZONE: alle 495 maskers — 450 via colbest-UB<=1786; 45 gecertificeerd
   (oracle nominale+verticale-blanco-band + laneB turn-blanco-slice) alle UNSAT boven 1786;
   hotspot-masker exact (93.443 band-combos UNSAT @1786).
4. PSYCHOANALYZING: 15 maskers met UB>1786, elk oracle-CERTIFIED <=1786
   (turn-blanco's uitgesloten via het 27-punts-argument: lb >= UB_MASK-27 voor alle 15).
5. SUB-15-HOOFDWOORDEN: sound UB = 9*best14(+dubbel-letter-relaxatie 71) + 50 + top-7 colbest
   = 1139 << 1786 (mains op niet-TWS-rijen nog lager: wm<=4, kruisen <=2x(woordsom+lm) per kolom).

Eerste bewezen Engelse max-turn-optimum. Vervangt de folklore-constructies (~1780-1785).
Ledgers/logs: experiments/results/english/, oracle_parallel/oxyphenbutazone_*, psy_or_*.
