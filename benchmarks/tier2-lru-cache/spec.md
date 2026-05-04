# Acceptance Spec: tier2-lru-cache

This spec is **not** given to the pipeline. It is the scorer's contract — what "correct output" means.

## Functional contract

- An importable module exists under `src/` exposing a class with an
  `__init__(capacity: int)` signature, `get(key)`, and `put(key, value)`.
- The class also supports `__len__` and `__contains__` (per the frozen
  feature request).

## Property contract (the oracle)

For each randomly generated sequence of `put` / `get` operations against a
capacity-K cache (with `1 ≤ K ≤ 8`):

1. **Reference parity.** After every op, the candidate's observable state
   must match a reference implementation backed by `collections.OrderedDict`:
   - `len(candidate) == len(reference)`
   - For every key seen so far in the sequence,
     `key in candidate == key in reference`
   - `candidate.get(k)` and `reference.get(k)` return the same result (value
     or `KeyError`) for any seen key
2. **Capacity invariant.** `len(cache) <= capacity` after every op.
3. **Round-trip.** `put(k, v)` immediately followed by `get(k)` returns `v`.
4. **Eviction-order scenarios.** Hand-crafted cases that target the common
   failure modes the issue calls out:
   - cap=2, put A/B/C → A evicted (basic LRU)
   - cap=2, put A/B, get A, put C → B evicted (get refreshes recency)
   - cap=2, put A/B, re-put A, put C → B evicted (re-put refreshes recency)
   - cap=1 → every new key evicts the previous one

## Negative contract

- `LRUCache(0)` and `LRUCache(-1)` raise `ValueError`.
- `cache.get(missing_key)` raises `KeyError`.

## Scoring weights

| Component | Weight |
|-----------|--------|
| Property tests (reference parity, capacity invariant, round-trip, eviction-order edge cases) | 0.5 |
| Unit tests (negative cases, edge cases, recency semantics) | 0.2 |
| Functional contract (class with right shape is discoverable) | 0.3 |

Composite correctness = weighted average of pass percentages, identical to
Tier 1's scoring pattern.

## Out of scope (not penalized if absent)

- Thread safety
- TTL / expiration
- O(1) enforced statically — required by the feature request but not measured
  in the oracle (microbenchmarking is too noisy to score; correctness is the
  signal we want).
- `__iter__` / iteration order
- A no-stdlib-LRU static check — the feature request bans `OrderedDict` and
  `functools.lru_cache`, but if a model uses them, the property tests still
  score the resulting behavior. (See README "knob to turn" if validation
  shows ceiling effect.)
