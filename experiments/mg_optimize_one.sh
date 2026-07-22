#!/bin/bash
# Focus-optimizer voor EEN triple: probeer veel seed-offsets -> gesloten bord -> score-max decompose,
# houd de hoogste ECHTE score bij. Beat-flag zodra >3974. args: R0 R14 R7 TAG NITER
cd /home/bob/programming/scrabble4
R0="$1"; R14="$2"; R7="$3"; TAG="$4"; NITER="${5:-40}"; SEEDOFF="${6:-0}"
RECORD=3974
LOG=experiments/results/mg_opt_${TAG}.log
: > "$LOG"
best=0
for it in $(seq 1 "$NITER"); do
  sb=$(( SEEDOFF + (it-1)*3 ))
  MGR0="$R0" MGR14="$R14" MGR7="$R7" MGTAG="OPT_${TAG}" \
    MGKMASK=8 MGSEEDS=3 MGSEEDBASE=$sb MGTL=12 MGTALL=50 \
    nice -n 8 .venv/bin/python -u experiments/mg_solver3.py >/dev/null 2>&1
  if [ -f experiments/results/mg_decomp_OPT_${TAG}.json ]; then
    dec=$(MGTAG="OPT_${TAG}" MGSRC=decomp nice -n 8 .venv/bin/python -u experiments/mg_decompose_max.py 2>&1 | grep MAXDECOMP)
    sc=$(echo "$dec" | grep -oE "SCORE=[0-9]+" | grep -oE "[0-9]+")
    okv=$(echo "$dec" | grep -oE "ok=(True|False)")
    echo "iter${it} sb${sb}: ${dec}" >> "$LOG"
    if [ "$okv" = "ok=True" ] && [ -n "$sc" ]; then
      if [ "$sc" -gt "$best" ]; then
        best=$sc
        cp experiments/results/mg_gamemax_OPT_${TAG}.json experiments/results/mg_optbest_${TAG}_${sc}.json 2>/dev/null
        echo "  NEW BEST ${sc}" >> "$LOG"
      fi
      if [ "$sc" -gt "$RECORD" ]; then
        echo ">>> >RECORD: ${sc} > ${RECORD} (${R0}/${R7}/${R14}) <<<" >> "$LOG"
        cp experiments/results/mg_gamemax_OPT_${TAG}.json experiments/results/mg_beat_${TAG}_${sc}.json
      fi
    fi
    rm -f experiments/results/mg_decomp_OPT_${TAG}.json
  fi
done
echo "opt ${TAG} klaar, best=${best}" >> "$LOG"
