#!/bin/bash
M=$1; D=/tmp/exam_sol; rm -rf $D; mkdir -p $D; cd $D
S=$(date +%s)
codex exec -m "$M" --skip-git-repo-check "$(cat /tmp/problem2.md) Print the file content to stdout." > out.txt 2>err.txt </dev/null
E=$(( $(date +%s)-S ))
grep -v '^```' out.txt > solution2.py
echo "model=$M secs=$E"
python3 /tmp/test2.py 2>&1 | tail -2
