# Coding instructions

## Tooling
- tests: pytest, run with `pytest ...`
- code analysis:
    - linting with `ruff`: run with `ruff check --output-format=concise ...`
    - typechecking with `ty`: run with `ty check --output-format=concise ...`

## Types
- All variables, parameters, and return values must be fully typed at all times — no `Any`, no implicit `Any` from missing annotations.
- Do not introduce new types (dataclasses, TypedDicts, enums, aliases, etc.) without explicit user approval. If a new type seems necessary, describe what it would look like and wait for a decision before writing it.
- Prefer the narrowest correct type. Use `Literal`, `TypeGuard`, `Final`, and union types rather than widening to a broader type for convenience.

## Architecture
- Read and understand the existing architecture before making any changes. Do not infer structure from one file alone.
- If you find a structural issue or inconsistency, report it clearly with the file and line reference, then stop and wait for the user's direction. Do not work around it silently.
- Do not add new modules, packages, or top-level files without user approval.

## Code style
- Avoid excessive OOP nesting. Prefer flat, composable functions over deep class hierarchies. Classes are appropriate for stateful game objects (characters, buffs, combat state); they are not appropriate for pure transformations or lookups.
- Keep functions small and single-purpose. If a function needs a comment to explain what it does, it should probably be split or renamed.
- No dead code. Do not leave commented-out blocks, unused imports, or placeholder stubs in committed code.
- Do not add logging, metrics, or debug prints unless explicitly asked.

## Simulation-specific rules
- Game mechanics must be derived from the spec or explicit user instruction — never invented. If a mechanic is ambiguous, ask rather than assume.
- Randomness must always flow through a single, explicitly passed RNG object. No module-level `random` calls.
- Simulation state must remain serializable and inspectable. Avoid closures or runtime-generated objects that obscure state.
- Aggregation logic (Monte Carlo) must stay strictly separate from single-run simulation logic.

## Scope
- Only change what is needed to complete the requested task. Do not refactor, rename, or reformat surrounding code.
- Do not add error handling, validation, or fallbacks for cases that cannot occur given the simulation's invariants.
- Do not add docstrings or comments to code you did not write, unless asked.

## Micro instructions
- all dataclass should be `kw_only=True`
- all calls to a function should be with keywords, unless applied to a variable with a similar name

# Project summary

The codebase is a **discrete-event simulator** (or *sim*) for the world-of-warcraft-like game Fellowship.
he objective is to simulate to some high level of accuracy the various mechanics of the game in order to be able to:
- perform single simulations of taking specific actions on specific game states;
- combine multiple simulations in a monte-carlo aggregate;
- derive insights from these aggregates.
Currently, a single game character is available (Elarion).

The core loop is:

- Repeat multiple times to average out the random elements
    - Setup a game State
    - Setup a Player
    - Use some Ability following the logic encoded by a Rotation
    - Resolve any randomness using the global rng at state.rng
    - Collate the damage inflicted by the Rotation in a Metric

In order to account for various modifiers, the State element maintains an event bus.
Multiple game elements can subscribe to the event bus.

# Details

### Event Bus

`EventBus` in [base_classes/events.py](../src/fellowship_sim/base_classes/events.py) is the primary decoupling mechanism. Handlers subscribe by event type and optionally register an owner for bulk-unsubscribe. The owner-based unsubscribe uses `id(owner)` — documented as a workaround because mutable dataclasses aren't hashable.

The various events are in the same file.

### Stat Pipeline

Stats flow through three layers (in [[base_classes/statps.py](../src/fellowship_sim/base_classes/stats.py)])

```
RawStats, immutable
MutableStats
    - add various modifiers to RawStats
FinalStats, immutable
```

Stat recalculation needs to be triggered manually with [Player.recalculate_stats(self)](../src/fellowship_sim/base_classes/entity.py).

### Damage

To compute damage from a given source, the base damage of the source needs to be combined with stats.
[This is encoded in base_classes/combat.py](../src/fellowship_sim/base_classes/combat.py#L112).
A few damage events do not scale with stats, or have exceptional scaling.

### Time model

[The State object holds a queue of timed events](../src/fellowship_sim/base_classes/state.py). [TimedEvent is encoded here](../src/fellowship_sim/base_classes/timed_events.py).
To handle time:
- The state finds the next timed event.
- Time moves to that point: this modifies the cooldown of player abilities and the duration of active effects.
- The timed event resolves
- NB: the expiration time of effects is encoded in the timed events.

### Direct user interaction

To interact with the simulator, the user must:
- setup a state and player object, from configuration parameters passed as ordinary function parameters,
- call the player abilities, as ordinary python functions,
- the ability resolves, changing the state of the sim and resolving events until the player is available again,
- once the player is available again, the call to the ability function returns.
This direct interaction with the sim is intended to be used for exploration and verification.

### Estimating the average damage of a rotation and character setup

The typical usage of the simulation is:
- setup a state and player object, from configuration parameters passed as ordinary function parameters,
- choose a policy to automatically choose abilities according to the state,
- compute the average damage over multiple repetitions.
The user can then compare setups and rotations.
