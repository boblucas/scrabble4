# Maxgame-optimaliteit: bewijsladder (dutch2026) — gestart 2026-07-19

**Status: LB = 3917 (maxgame_BEST.json, score_game-geverifieerd). Dit document bouwt de UB-kant.**
Arbiter: `maxgame_score.score_game` (state-aware sinds de impair-fix). Elke bewijslaag wordt
tegen de scorer gevalideerd.

## Stelling 1 (multiplierlijn-structuur) — BEWEZEN (numeriek geverifieerd)
Het bord heeft precies 8 TWS-cellen; precies 4 lijnen bevatten er 3: rij 0, rij 14, kol 0, kol 14.
Een zet scoort woordfactor 27 ⟺ hij dekt de 3 TWS van één zo'n lijn met NIEUWE tegels ⟹ het
hoofdwoord beslaat cel 0..14 van die lijn (15-woord). TWS-incidentie: rij-0∩kol-0={(0,0)} enz. —
elk paar {rij,kolom} deelt een TWS. Twee ×27-zetten vereisen disjuncte TWS-triples ⟹ alleen
{rij 0, rij 14} of {kol 0, kol 14}. **Gevolg: ≤ 2 ×27-zetten per spel.**

## Stelling 2 (center-uitputting) — BEWEZEN
Zet 1 dekt (7,7) (spelregel) en legt ≤7 tegels op een leeg bord ⟹ zet 1 is geen 15-woord ⟹ de
center-DWS is verbruikt vóór elk later rij-7/kol-7-15-woord. Rij 7 en kol 7 hebben elk exact 2 TWS
⟹ zulke zetten scoren ≤ ×9. Met het rijenpaar als ×27-frame verbruiken rij 0/7/14-15-woorden ALLE
8 TWS ⟹ daarna geen TWS-multiplier meer beschikbaar. (Bob's 2×27+×9-frame is dus de unieke
maximale multiplier-structuur.)

## Frame-componenten (UB's, alleen woordbestaan + zak; geen ketenbaarheid/setup-eisen)
- max enkele ×27-zet (hoofdwoord): **1751**
- max enkele ×9-zet (hoofdwoord): **617**
- max zak-haalbare (2×27 + ×9)-triple gezamenlijk: **3894** (jacquetkostuums/playbackshowtje/schrikreflexjes)

## Rest-UB V0: per-lijn stage-DP + gekoppelde budgetten (RELAXATIE — grof maar sound)
Totaalscore = Σ over (zet, gevormd woord) van woordscores + 50·#bingo's. Elk gevormd woord leeft op
één van de 30 lijnen; per lijn vormen de gescoorde intervallen een STIJGENDE keten (elke zet die
tegels aan de run toevoegt scoort het dan-actuele interval; multipliers alleen op de delta-cellen).
Per lijn ℓ: DP over intervallen [a,b] ⊂ [a',b'] met transitiescore
(Σ_delta v·LM + Σ_oud v)·Π_delta WM geeft frontier F_ℓ(#stages, #cellen) — een harde UB op wat lijn
ℓ ooit kan opleveren bij dat aantal stages/cellen, met tegelwaarden gerelaxeerd naar de beste
zak-toewijzing per lijn.
Koppeling (sound): (a) Σ_lijnen #cellen ≤ 2·101 (elke tegel ligt op 1 h- en 1 v-lijn, één keer
geplaatst); (b) Σ_lijnen #stages ≤ #zetten + 101 ≤ 202 (elke zet: 1 hoofdstage + ≤ #nieuwe
kruisstages); (c) bingo's ≤ ⌊101/7⌋·50 = 700. Knapsack over de frontiers ⟹ **U0**.
BEKENDE LOSHEID: letters per lijn onafhankelijk uit de volle zak (dubbeltelling), geen
woordbestaan-eis, geen volgorde-consistentie tussen lijnen. Aanscherpingsroute: exacte
letterkoppeling (multiset ≤ 2×zak), premium-both-directions-verfijning, woordbestaan per interval
(automaton), zet-consistentie (stage-gelijktijdigheid h+v).

## Ladder verder
1. U0 (dit script) → 2. letterkoppeling + stagebudget-verfijning → 3. frame-noodzakelijkheid:
spel met ≤1 ×27 ≤ 1751 + 617 + rest-UB' < LB ⟹ optimum gebruikt het frame → 4. klasse-sluiting
binnen het frame (triple exact, vulfase via CP-SAT + reachability-certificaat).

## Status UB-ladder (2026-07-19, avond)
V0 20243 → V1 (Lagrange+woordsom-caps) 13718 → V2 (st≤cellen, scherpere caps) 12633 →
**V3 (analytisch frontier + ketensom + zakwaarde/richting + TWS-cases) = 10806 — STAAND**.
V3b/c (gezamenlijk stagebudget 202 + delta≤7) verliezen per saldo door de waarde-bucketing
(verbruik afgerond omlaag): 11031/11141 — de fijnmazige 2D-V3 wint.

**Asymptoot-analyse:** de lijn-relaxatie bevat al: ketensom (Σ stage-bases ≤ 295/lijn),
woordsom-caps per lengte, cel- en waardebudget per richting, TWS-case-analyse, st≤cellen.
De resterende ~6.9k boven de LB zit in het ontbreken van GEOMETRISCHE consistentie
(kruis-stages verlangen echte loodrechte zetten op gedeelde cellen; niet elke lijn kan
tegelijk een diepe keten dragen). Dat is niet meer met budget-koppelingen te vangen.

**Routes naar scherper:**
(a) Begrensde exacte ILP: de 6 TWS-lijnen + hun kruisende lijnen celgewijs exact in CP-SAT,
    rest via V3-boekhouding — verwacht ~7-8k, onzeker.
(b) KLASSE-SLUITING (aanbevolen): conditioneel resultaat "gegeven het frame + anker-skelet is
    de vul+mop-up-fase ≤ X" via CP-SAT op het concrete bord (kleine ruimte!), plus
    triple-optimaliteit (al empirisch geveegd) ⟹ optimaliteit binnen de frame-klasse,
    analoog aan de ≤8-variant-2010 vóór de echte 2102.

## Klasse-sluiting: decompositie gemeten (2026-07-19)
Recordspel 3930 = **skelet 3728** (keten+slotzetten, deterministisch, score_game-geverifieerd)
+ **202 vulfase** (7 zetjes; slotzet-boost door vullercellen = 0 hier).  Klasse-optimum =
3728 + maxfill(skelet).  maxfill is een KLEIN probleem: ~15 resttegels op een vast bord van
~86 cellen; te begrenzen via exhaustieve zoektocht/CP-SAT incl. flank-kruisboost bij de
slotzetten (vullercel naast masker-TWS-cel telt x3 in de slotzet).  NB: klasse-bound moet ook
vullers vóór de slotzetten dekken (maskerdiscipline + kruisboost-term).
