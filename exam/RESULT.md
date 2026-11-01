# Stage 0 exam (2026-11-01, box, codex-cli 0.164.0)
Problem: exam/problem.md (merge_intervals + lru_cache_sim). Run: `limactl copy exam/problem.md exam/run.sh box:/tmp/` then `limactl shell box -- bash /tmp/run.sh MODEL`.

| model | secs | tokens | notes |
|---|---|---|---|
| gpt-6-luna | 8 | 2252 | merges adjacent ints ([1,2],[3,4]); returns tuples |
| gpt-5.6-terra | 5 | 2888 | merges only shared endpoints; returns lists |

Both ran and gave plausible LRU code. I did NOT execute the outputs against tests; the "touching" wording was ambiguous, so this one problem cannot separate them.
Decision: keep the temporary order (gpt-6-luna -> gpt-5.6-terra -> gpt-5.6-luna). Next: run a harder problem with unit tests (STEPS A2).
Codex in GitHub Actions: NOT tested yet (STEPS A3).
