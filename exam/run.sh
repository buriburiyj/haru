#!/bin/bash
# usage: run.sh MODEL  (runs inside box)
M=$1; D=/tmp/exam_sol; mkdir -p $D; cd $D
S=$(date +%s)
codex exec -m "$M" --skip-git-repo-check "$(cat /tmp/problem2.md)" > out.txt 2>err.txt
echo "model=$M secs=$(( $(date +%s)-S )) exit=$?"
