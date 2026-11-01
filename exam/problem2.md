Write solution2.py defining:
1) merge_intervals(intervals): merge overlapping intervals, intervals sharing only an endpoint ARE merged ([1,2],[2,3]->[[1,3]]), integer-adjacent ([1,2],[3,4]) are NOT merged; return sorted list of [s,e] lists.
2) lru_cache_sim(capacity, ops): ops are ("put",k,v) or ("get",k); return list of get results (-1 if missing); put of existing key updates and refreshes recency; capacity<=0 stores nothing.
3) eval_expr(s): evaluate +,-,*,/ (true division), unary minus, and parentheses on a string with spaces; raise ValueError on invalid input. No eval().
Output only the file content.
