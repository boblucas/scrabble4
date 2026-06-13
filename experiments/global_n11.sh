#!/bin/bash
# Drive per-THREAT certification for the GLOBAL N=11 max-turn proof.
#
# Input: the THREAT lines produced by
#   experiments/33_full_turn_bracket.py 11 --scale-tiles --blanks --seed-lower 852 --gvub-cap 120 --enum-only
# Each THREAT line is:   THREAT <mword> <turn_str> <main_score> <barepack_ub>
#
# For every threat EXCEPT bouwfysicus (already certified in certs/n11_fixed_221 + certs/n11_center) we run
# the certifier at the per-word vertical floor = 852 - main_score:
#   build  --board 11 --main <mword> --turn <turn_str> --floor <852-main_score> --name global_<mword>
#   check  certs/global_<mword>/ledger.json
# A CERTIFIED ledger means that (word,mask)'s verticals <= floor => its turn <= 852 (ruled out).
# A refutation (MAX > floor) means a word BEATS 852 -- surfaced LOUDLY (a new global record).
#
# Usage:  bash experiments/global_n11.sh <enum_only.log> [GLOBAL_LOWER=852] [PROCS=12] [WALL=600]
set -u
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
PY=.venv/bin/python
CERT=experiments/35_certify.py

LOG=${1:-experiments/results/enum_only_n11.log}
GLOBAL=${2:-852}
PROCS=${3:-12}
WALL=${4:-600}
WALLA=2

CERTDIR=experiments/results/certs
RESDIR=experiments/results/global_n11
mkdir -p "$RESDIR"

# Collect threat lines, skipping bouwfysicus (any mask) -- already certified.
THREATS="$RESDIR/threats.txt"
grep -a '^THREAT ' "$LOG" | awk '$2 != "bouwfysicus" {print}' > "$THREATS"
N=$(wc -l < "$THREATS")
echo "== global N=11 driver: $N non-bouwfysicus threat (word,mask) pairs from $LOG (global lower=$GLOBAL) =="
cat "$THREATS"
echo "========================================================================================"

# One certifier build+check per threat.  We fan out with xargs -P (NOT a jobs throttle).
# Each job uses --procs 12 internally for its own CP-SAT/inner fan-out, so keep OUTER parallelism low.
OUTER=${OUTER:-1}

cert_one() {
  local mword="$1" turn="$2" mscore="$3"
  local floor=$((GLOBAL - mscore))
  local name="global_${mword}"
  local blog="$RESDIR/${name}.build.log"
  local clog="$RESDIR/${name}.check.log"
  echo ">>> [$name] main=$mword turn=$turn main_score=$mscore floor=$floor" >&2
  $PY "$CERT" build --board 11 --main "$mword" --turn "$turn" --floor "$floor" \
      --name "$name" --procs "$PROCS" --wall "$WALL" --wall-a "$WALLA" > "$blog" 2>&1
  $PY "$CERT" check "$CERTDIR/$name/ledger.json" > "$clog" 2>&1
  local verdict; verdict=$(grep -aE '^(CERTIFIED|NOT CERTIFIED)$' "$clog" | tail -1)
  echo "<<< [$name] floor=$floor  verdict=${verdict:-NO-VERDICT}" >&2
}
export -f cert_one
export PY CERT CERTDIR RESDIR GLOBAL PROCS WALL WALLA

# GLOBAL is referenced inside cert_one via the exported env var.
awk '{print $2"\t"$3"\t"$4}' "$THREATS" \
  | xargs -P "$OUTER" -I{} bash -c '
      IFS=$'"'"'\t'"'"' read -r mword turn mscore <<< "{}"
      cert_one "$mword" "$turn" "$mscore"
    '

echo "========================================================================================"
echo "== global N=11 driver SUMMARY =="
fail=0
while IFS=$'\t' read -r mword turn mscore; do
  name="global_${mword}"; floor=$((GLOBAL - mscore))
  clog="$RESDIR/${name}.check.log"
  verdict=$(grep -aE '^(CERTIFIED|NOT CERTIFIED)$' "$clog" 2>/dev/null | tail -1)
  refuted=$(grep -aiE 'REFUTED' "$RESDIR/${name}.build.log" 2>/dev/null | head -1)
  printf '  %-28s floor=%-4s verdict=%-15s %s\n' "$mword" "$floor" "${verdict:-MISSING}" "$refuted"
  [ "$verdict" = "CERTIFIED" ] || fail=1
done < <(awk '{print $2"\t"$3"\t"$4}' "$THREATS")

if [ "$fail" -eq 0 ] && [ "$N" -gt 0 ]; then
  echo "ALL THREAT WORDS CERTIFIED <= $GLOBAL  -> global N=11 = $GLOBAL PROVEN (with bouwfysicus already certified)"
elif [ "$N" -eq 0 ]; then
  echo "NO non-bouwfysicus threats -> global N=11 = $GLOBAL PROVEN (bouwfysicus is the sole threat, already certified)"
else
  echo "SOME THREAT WORDS NOT CERTIFIED -- inspect logs above (a MAX>floor would be a NEW RECORD beating $GLOBAL)"
fi
exit "$fail"
