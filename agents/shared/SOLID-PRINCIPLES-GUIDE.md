# SOLID Principles & Maintainability Guide

Reference material for the code-reviewer agent. **This file is NOT auto-injected into agent
prompts** — it is human/onboarding documentation. The reviewer agent has a compact cue in its
definition; this is the full framework for when reviewers (human or AI) want the underlying
rationale.

These are not suggestions. Violations of these principles are architectural defects that
compound over time. Flag them as HIGH severity only when they create concrete maintenance risk.

## SOLID Principles

### Single Responsibility Principle (SRP)

Every module, class, and function should have exactly one reason to change. One stakeholder,
one axis of change.

- **God objects/modules**: A class or module that handles persistence AND business logic AND
  formatting AND validation has four reasons to change. Demand it be split.
- **Mixed abstraction levels**: A function that parses raw input, applies business rules, AND
  writes results violates SRP. Each concern is a separate function or collaborator.
- **"And" in the name**: If describing what a class does requires "and", it probably does too
  much. `UserManagerAndNotifier` is two classes.
- **Config bloat**: A settings/config object that every module depends on is a hidden god
  object. Each module should depend only on the config values it needs.
- **Test smell**: If a unit test requires extensive setup across unrelated concerns, the unit
  under test has too many responsibilities.

### Open/Closed Principle (OCP)

Modules should be open for extension but closed for modification. New behavior should not
require changing existing, tested code.

- **Switch/if-else chains on type**: A function with `if type == "A" ... elif type == "B" ...`
  that grows with every new type violates OCP. Demand polymorphism, a registry, or a strategy
  pattern.
- **Hardcoded behavior**: Functions that embed specific rules instead of accepting a strategy
  or configuration force modification for every new case.
- **Missing extension points**: When adding a feature requires editing three existing files
  rather than adding one new file and registering it, the architecture is closed for extension.
- **Fragile base classes**: Base classes that require subclass changes when modified are
  ticking time bombs.

### Liskov Substitution Principle (LSP)

Subtypes must be substitutable for their base types without breaking correctness. Every
implementation of an interface must honor the full contract, not just the signature.

- **Exceptions from subtypes**: A subclass that raises `NotImplementedError` for a base class
  method violates LSP. If it can't do the operation, it shouldn't inherit from that type.
- **Narrowed preconditions / widened postconditions**: A subclass that accepts fewer inputs or
  returns more types than the parent promises breaks substitutability.
- **Empty implementations**: Implementing an interface method as a no-op to satisfy a type
  checker means the abstraction is wrong. Decompose the interface.
- **Type checks against concrete types**: `isinstance(x, ConcreteImpl)` downstream means the
  abstraction is leaky — callers should not need to know the concrete type.

### Interface Segregation Principle (ISP)

No client should be forced to depend on methods it does not use. Prefer small, focused
interfaces over large, general-purpose ones.

- **Fat interfaces**: An interface with 10+ methods where most implementations only use 3-4
  should be decomposed into role-specific interfaces.
- **Adapter proliferation**: If many classes implement an interface by stubbing out half its
  methods, the interface is too broad.
- **Forced dependencies**: A module importing a large dependency (class, config, service)
  just to access one field or method indicates a missing, narrower interface.
- **Test doubles smell**: If mocking an interface for tests requires stubbing many irrelevant
  methods, the interface is too fat.

### Dependency Inversion Principle (DIP)

High-level policy should not depend on low-level detail. Both should depend on abstractions.
Abstractions should not depend on details.

- **Direct instantiation of collaborators**: A class that creates its own database connection,
  HTTP client, or file handler inside its methods is untestable and tightly coupled. Demand
  injection via constructor, method parameter, or factory.
- **Import direction**: Business logic modules should never import from infrastructure modules
  (database, HTTP, file I/O) directly. Infrastructure implements interfaces defined by the
  business layer.
- **Framework coupling**: Business rules that import framework types (web request objects,
  ORM models, CLI argument parsers) directly cannot be reused or tested without the framework.
- **Concrete return types from factories**: Factory functions that return concrete types
  instead of interfaces defeat the purpose of the abstraction.

## Maintainability — The Primary Quality Metric

Code is read and modified 10x more than it is written. Every review decision should optimize
for the next developer who touches this code, not the developer who wrote it.

### Coupling and Cohesion

- **Afferent coupling (who depends on me)**: Modules with many dependents are expensive to
  change. Flag high fan-in modules that lack stable, narrow interfaces.
- **Efferent coupling (who I depend on)**: Modules with many dependencies are fragile. Flag
  high fan-out modules — they break when any dependency changes.
- **Temporal coupling**: Functions that must be called in a specific order without the
  compiler/type system enforcing it will be called out of order. Demand that ordering
  constraints are structural, not documented.
- **Connascence**: When two modules must change together, they have hidden coupling. Demand
  it be made explicit through shared abstractions or eliminated entirely.
- **Feature envy**: A function that accesses more data from another module than its own is in
  the wrong module. Move it.
- **Cohesion**: A module where every function operates on the same data and serves the same
  purpose is highly cohesive. A module with unrelated functions grouped by convenience is a
  junk drawer. Demand cohesion.

### Complexity Management

- **Cyclomatic complexity**: Functions with more than 3-4 branch points (if/else/switch/try)
  are hard to test exhaustively and hard to reason about. Demand decomposition.
- **Nesting depth**: More than 2-3 levels of nesting obscures control flow. Demand early
  returns, guard clauses, or extraction into named functions.
- **Boolean parameters**: `process(data, validate=True, async_mode=False, retry=True)` is
  three functions pretending to be one. Each flag doubles the behavior space.
- **Primitive obsession**: Passing raw strings, ints, or dicts where a domain type would
  prevent misuse. An `email: str` can be anything; an `Email` value object self-validates.
- **Magic values**: Hardcoded numbers, strings, or indices that only make sense with context.
  Demand named constants or enums.
- **Deep vs shallow modules**: A module with a narrow interface and complex internals (deep)
  is good. A module with a complex interface and trivial internals (shallow) adds ceremony
  without value.

### Change Safety

- **Shotgun surgery**: A single logical change requiring edits across many files indicates
  missing abstractions. The change should be localized.
- **Divergent change**: A single module that changes for many different reasons needs to
  be split (SRP violation at the module level).
- **Speculative generality**: Abstractions, interfaces, or configuration created "in case we
  need it later" add complexity now for hypothetical future value. Demand YAGNI — generalize
  only when the second use case arrives.

## Testable Architecture — Non-Negotiable

Code that cannot be unit-tested in isolation is architecturally broken. This applies to
every file, not just files in a test suite.

### Dependency Management for Testability

- **Constructor injection**: Dependencies passed at construction time, not created internally.
  If you can't swap a dependency in a test without monkey-patching, the design is wrong.
- **Pure core / imperative shell**: Business logic should be pure functions or objects with
  injected dependencies. I/O, framework calls, and side effects live at the boundary. The
  core is trivially testable; the shell is thin and tested via integration tests.
- **Seams**: Every point where behavior might vary (data source, external service, time,
  randomness) needs a seam — an interface or parameter that tests can control.
- **No global state**: Singletons, module-level mutable variables, and class variables shared
  across instances make tests order-dependent and non-parallelizable. Demand explicit passing.

### Test Structure Red Flags

- **Excessive mocking**: If a test requires mocking more than 2-3 collaborators, the code
  under test has too many dependencies. Fix the production code, not the test.
- **Test brittleness**: Tests that break when internal implementation changes (not behavior)
  are testing the wrong thing. Demand tests that assert outcomes, not mechanics.
- **Setup-heavy tests**: A test that needs 20+ lines of setup to exercise one behavior means
  the code is doing too much or requiring too much context. The production code is the problem.
- **Untestable paths**: Error handlers, fallback paths, and edge cases that "never happen"
  still need to be testable. If they can't be triggered in a test, the design needs a seam.
