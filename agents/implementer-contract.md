# Implementer Contract

A context brief is Haiku-ready when it satisfies ALL of the following. This is the canonical
source of truth — both the architect-planner (who writes briefs) and the implementer-agent
(who executes them) derive their rules from this contract.

1. **SELF-CONTAINED**: All needed interfaces, types, and signatures are provided inline in the brief. No "see task X" references — all dependencies are materialized.
2. **SINGLE-FILE**: Produces exactly one file or one logical unit at an exact path.
3. **FULLY-SPECIFIED**: No design decisions are left to the implementer. Types, naming conventions, patterns, error handling, and constraints are explicit.
4. **BOUNDED**: Under 150 lines of expected output. If longer, split further.
5. **VERIFIABLE**: Build and test commands are provided. Expected coverage target is stated.
6. **SCOPED**: Only listed files are produced. No helpers, extensions, utilities, logging, analytics, or refactoring beyond what the brief specifies.
7. **LIMITED-INLINE-EXCEPTION**: You may inline-fix a trivial issue ONLY if ALL of the following hold: (a) the fix is in a file you are already editing as part of the brief; (b) the change is under 5 lines; (c) it is purely mechanical — typo, unused import, obvious dead-code removal; (d) it does NOT change behavior and does NOT add new code paths. Anything else — cross-file fixes, new abstractions, logic changes, adding error handling, adding logging — is out-of-scope. Escalate those to the architect; do NOT absorb them into your current task.
