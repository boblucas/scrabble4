#!/bin/bash
# continue pijplijn-worker: pakt atomair een volgende seed en draait door tot STOP-bestand.
cd /home/bob/programming/scrabble4
CTR=experiments/results/maxgame_seedctr
STOP=experiments/results/maxgame_STOP
[ -f "$CTR" ] || echo 2000 > "$CTR"
while [ ! -f "$STOP" ]; do
  SD=$(flock "$CTR" -c 'S=$(cat '"$CTR"'); echo $((S+1)) > '"$CTR"'; echo $S')
  experiments/maxgame_pipeline.sh "$SD" 5 > /dev/null 2>&1
done
