#!/bin/bash
cd /home/bob/programming/scrabble4
# arg: R0 R14 R7 M0 M14 M7 tag
MGR0="$1" MGR14="$2" MGR7="$3" MGM0="$4" MGM14="$5" MGM7="$6" MGTAG="$7" \
SEED="$8" MGTL=200 nice -n 8 .venv/bin/python -u experiments/mg_solver2.py 2>&1 | grep -E "solver2:|VERBONDEN" | sed "s/^/[$7 s$8] /"
