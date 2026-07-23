#!/bin/bash
# EEN-actie-publicatie naar github.com/boblucas/scrabble4: verse gefilterde mirror
# (>90MB-blobs eruit; GitHub-limiet) en force-push van beide branches.
# Vereist GH_TOKEN in de omgeving. Gebruik: GH_TOKEN=... experiments/push_github.sh
set -e
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
git clone --quiet --mirror /home/bob/programming/scrabble4 "$TMP/m"
cd "$TMP/m"
/home/bob/programming/scrabble4/.venv/bin/python -m git_filter_repo --strip-blobs-bigger-than 90M --force >/dev/null 2>&1
git push --force --quiet "https://x-access-token:${GH_TOKEN}@github.com/boblucas/scrabble4.git" experiments/automaton-cpsat-verification master
echo "gepusht: $(git log -1 --format=%h experiments/automaton-cpsat-verification)"
