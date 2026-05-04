# Feature Request: LRU cache

Please add a fixed-capacity LRU (Least Recently Used) cache to this Python project.

> **Benchmark mode — no clarifying questions.** This request is the frozen input
> for the Tier 2 regression benchmark. Every potentially-ambiguous decision is
> pre-specified below in the `Decisions` section. **Architect 1a must not ask
> clarifying questions** — proceed directly to spec finalization (1a-spec.md) and
> on to planning (1b). If a corner case is not explicitly decided here, choose the
> most idiomatic Python answer and document it in 1a-spec.md without halting.

## Requirements

- Implement an `LRUCache` class with **O(1)** `get` and `put` operations.
- Fixed capacity, set at construction time. The cache holds up to `capacity`
  key/value pairs.
- When a `put` of a *new* key would exceed capacity, evict the
  **least-recently-used** entry first, then insert.
- Both `get(key)` and `put(key, value)` mark the key as most-recently-used.
- A `put` of an *existing* key updates its value AND marks it as
  most-recently-used. It does not evict anything (count is unchanged).
- Include unit tests covering normal and edge cases.

## Out of scope

- Thread safety — single-threaded only.
- TTL / expiration — capacity-only eviction.
- Persistence to disk — in-memory only.
- Iteration (`__iter__`, `keys()`, `values()`) — not required.

## Implementation note

Do **not** use `collections.OrderedDict`, `functools.lru_cache`, or any other
prebuilt LRU mechanism from the standard library. Implement the eviction
ordering yourself using a hash map plus a doubly-linked list (or any
equivalent O(1) structure). This is intentional — the project exists to measure
what is produced from scratch.

## Decisions (frozen — do not re-ask)

These resolve the ambiguities Architect 1a would otherwise surface. Treat as
final.

### Module layout

- **Module name:** `lru_cache`. The implementation lives at `src/lru_cache.py`
  and exports an `LRUCache` class. Helper classes (e.g., a `Node` for the
  linked list) may live in the same file.
- **Package init:** `src/__init__.py` may stay empty or re-export `LRUCache` —
  implementation choice.
- **No CLI.** The benchmark scores a library API; no command-line entry point
  is required.

### Constructor

- **Signature:** `__init__(self, capacity: int) -> None`.
- **`capacity <= 0`** raises `ValueError` with a descriptive message.
  Non-integer capacity (e.g., `0.5`, `"5"`) is allowed to fail however it falls
  — no defensive type-checking required.

### Operations

- **`get(self, key) -> Any`** — returns the stored value if `key` is present,
  marking it most-recently-used. Raises `KeyError(key)` when the key is not
  present (match `dict.__getitem__` behavior, **not** `dict.get` — no implicit
  default).
- **`put(self, key, value) -> None`** — inserts when the key is new (and
  evicts the LRU entry first if `len(self) == capacity`); updates the value
  and refreshes recency when the key already exists. Returns `None`.
- **`__len__(self) -> int`** — returns the current entry count
  (`0 <= len <= capacity`).
- **`__contains__(self, key) -> bool`** — `key in cache`. Does **not** affect
  recency. (Peeking is not the same as accessing.)

### Eviction order

- "Least-recently-used" means the entry whose last `get` or `put` happened the
  longest ago among current entries.
- Inserting a *new* key when full evicts exactly one entry (the LRU).
- Updating an *existing* key never causes eviction.
- `__contains__` does not change recency; only `get` and `put` do.

### Type hints / style

- Type hints required on `__init__`, `get`, `put`, `__len__`, `__contains__`.
- Mypy strict is enabled. For value types you may use `Any` or generics
  (`TypeVar`) — both are acceptable.
- Brief one-line docstrings on `LRUCache`, `get`, and `put`. No multi-paragraph
  docstrings.

### Tests

- **Coverage:** Thorough case coverage is required; no numeric coverage floor.
- **Test file:** `test_lru_cache.py` at project root. Pytest is already
  configured.
- **Tests must cover:** capacity-1 edge case, eviction order after a sequence
  of puts and gets, `KeyError` on missing key, `ValueError` on invalid
  capacity, re-put updating value while keeping length unchanged, recency
  preservation through `get`, and `__contains__` not refreshing recency.
