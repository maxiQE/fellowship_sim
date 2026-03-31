# Test architecture

**Critical instruction** If writing a test reveals weird behavior:

- Have the test fail trivially with `assert False`.
- Mark the test as unfinished with a `# TODO` comment.
- Detail the ambiguity in the todo comment.
- Report the issue to user.

## Test types

The tests in this project are organized in three categories:

- unit tests: these test a single function call as it is implemented in the code and check it for correctness.
    These tests check that each single function behaves as it should.

- integration tests: these test a single logic element (ability, effect, etc) in a controlled environment with as few interacting elements as possible active.
    These tests check that the implementation details of the simulation are well-controlled.

    - These are aimed at convincing developpers that the current code is solid.

    - For example, to test the damage of the multishot ability, we set up a state with simple enemies, a basic Elarion with no effects and use multishot through its _do_cast private API.

        - adding effects make the test too complex for the *integration* level.
        - using the cast user-facing API introduces additional complexity beyond the scope of the *integration* level.

    - For example, to test the "highwind arrow gives multishot charges" interaction, we set up a state with simple enemies, a basic elarion and use highwind arrow through its _do_cast private API.

    - For example, to test the "celestial impetus effect interactions with the impending barrage effect", we set up a state with simple enemies, a basic Elarion with no effects then add the celestial impetus and impending barrage effects manually.
        
        - We check the validity of the behavior at a low level: does heartseeker barrage recover cooldown; is the 

- functional tests: these reproduce a fully realistic user interaction with the sim with all interacting elements.
    They test a few specific predictions on specific controlled situations.
    They check that the simulation reproduces a controlled model of the game, regardless of implementation details.

    - For example, testing the number of hits of an ability against specific haste breakpoints is a functional test: it's about game logic.

The frontier between integration and functional is fuzy but the overall idea is that:

- Tests that are easy to explain to game players are functional.
- Tests that focus on game logic are functional.
- Tests that are higher-level are functional.
- Tests with fuzzier predictions are functional.
- Tests that use the user-facing API are functional.

It's fine to make mistakes with that classification.

## Test coding style

- Each test should have a brief docstring giving a high level overview of what it tests for.
- Group tests into classes around a single behavior or feature (e.g. one class per mechanic, per ability, or per CDR source). A class docstring can capture context that would otherwise need a section header comment.
- Do not write module-level factory helpers (e.g. `_make`, `_make_bare`). Use pytest fixtures instead — global ones from `conftest.py` where they fit, or class-level fixtures for setup shared within one class.
- For comparison tests that set up two independent states side by side, inline both constructions in the test body. Using a fixture for one and inlining the other is asymmetric and harder to read.
- Avoid `# -----` section dividers; the class structure makes them redundant.

## RNG

In all tests, RNG should be controlled. If the RNG is central to the behavior of the sim:

- Use either a FixedRNG, if possible, or SequenceRNG as appropriate. These two should be the default in integration tests.
- Document which elements are random.

In many functional tests, the behavior should not depend on the RNG.
For these, we check that the predictions are valid over a range of seeded RNG.

Unit tests should not interact with the RNG.

## Parametric tests

Pytest makes it straightforward to repeat the same test while varying inputs slightly.
Where the correctness of the behavior should be independent of a parameter, parametrize over it to confirm that independence.
Parametric tests also helps avoid repeating code in tests.
Try to use parametric tests as appropriate.

For example, testing the same situation against a variety of:

- seeded RNG,
- character stats,
- character setups,

ensures that we test for non-interaction.
