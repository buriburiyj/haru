#!/bin/bash
M=$1; D=/tmp/exam_sol; rm -rf $D; mkdir -p $D; cd $D
S=$(date +%s)
codex exec -m "$M" --skip-git-repo-check "$(cat /tmp/problem2.md) Write the file to $D/solution2.py." > out.txt 2>err.txt
echo "model=$M secs=$(( $(date +%s)-S ))"
python3 /tmp/test2.py 2>&1 | tail -2
