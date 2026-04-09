# Code objectives

## Known issues

- DOTs mechanics are not game accurate:
    - tick rate is dynamic in-game; fixed in sim
    - accumulation mechanic is not correct (splinters)

- diamond strike: coded as multiplicative between number of echo stacks and number of harmonious souls stacks

- brave machinations: coding as triggering on the DOT

- green 1/6 is downplayed when no adds are present

## Todo

- documentation:
    - all abilities with non trivial implementations should have a detailed description of the model
    - auto extract docs (with sphinx?)


- Points that maybe need addressing:
    - functional test:
        - check if willful momentum applies to the cast that triggered the spirit proc
            - CS -> trigger spirit -> buffed damage
            - NOT CS -> trigger spirit -> normal damage

    - rotation is scuffed on cold starts:
        - it holds weapon instead of sending it

        - hold weapon + grace + ult for execute if possible
        - don't hold weapon and grace if ult is super far away

    - functional test for last lights + execute set
        - enemy HP goes down
        - check damage increase **in a scenario**

    - improve Effect collection to have more explicit API

    - try to remove all lazy imports

    - dot rewrite:
        - dynamic tick rate
        - dynamic damage (That should already work)
    - dot effects: take snapshot on dot creation instead of having the creator create the snapshot
        - fixed by improved snapshotting??

    - can all events be broadcasted at post init then finalized immediately when they have modifiers???

    - barrage: factor to standard channel
        - requires temporary ability modifiers
        - proposal:
            - have multiple variants of the ability
                - doesn't work: they need to share a lot of information like cooldown

    - rotations: priority list does not work as intended
        - unavailable abilities are skipped
        - but available abilities do not cause a return to the start of the list

    - state: move away from global singleton pattern now that code is solidified

    - no-op setup effect

    - stats: add flag to ignore static modifiers so that user can simply copy scores or percents from stronghold character sheet, without subtracting static effects
    - on score buildup, add flags to ignore gems (and other modifiers which are included in the character sheet); NB this is for ease of use

    - volley CDR is not correct, I think? Need to test how it stacks with ult
        - current = cooldown multiplier = (1 + haste_percent + num_volley) * chronoshift
        - correct = ??

    - effects attach at on_add instead of at __postinit__, and most of them do not actually need attached_to
        **Initial surprise:** Effect subclasses do setup in `on_add()` instead of `__post_init__()`. This is unusual for dataclasses.

        **Why:** Effects need `attached_to` to be set before they can subscribe to the bus or interact with the character. `attached_to` is set by `EffectCollection.append()` just before calling `on_add()`. A `__post_init__` would run at construction time, before the effect is attached to anything. This design is deliberate and correct.

        - this needs a rewrite

    - splinters rework:
        - listener on stat modifications:
            - trigger tick recompute
        - listener on crit:
            - no tick recompute
            - stored damage recompute
        - each tick is a dynamic damage event
            - look at current stored damage
            - tick
        - on remove:
            - partial tick
        - tests: look at model


- talent builds: give syntax so that this is possible:
    talents = BarrageBuild - "impending heartseeker" + "focused_expanse" + "skyward munitions"

- player HP model for ruby storm

- state config:
    - enemy percent hp decrease with time
    - spirit point regen with time
    - spirit point regen during combat
    - player character 80%HP uptime
    - gather time: can only hit a fraction of enemies during gather? Damage uncounted?
    - gather time: num enemies
    - important effects
    - harmonious soul stack handling

- Patient Soul
Heroic
Standing still for 3 seconds grants you Patient Soul, increasing your Max Health by 5% and your Expertise Rating by 107 / 141 / 177 / 212. 
Patient Soul persists for 6 sec after you start moving.
-> add simple uptime percent and add a stack of events like for minotaur

- ? usage of the full event variety

- ? automated reconstruction of the enums? construction of the enums somehow?

- ? time of flight: ability cast -> wait -> damage

# TODO: the can_cast bullshit

### 3.9 `can_cast()` uses MRO introspection for method discovery

[base_classes/ability.py:72-85](src/fellowship_elarion_model/base_classes/ability.py#L72-L85)

```python
def can_cast(self) -> CastReturnCode:
    checks: dict[str, Any] = {}
    for cls in reversed(type(self).__mro__):
        for name, attr in cls.__dict__.items():
            if callable(attr) and getattr(attr, _CHECK_ATTR, False):
                checks[name] = attr
    for check in checks.values():
        result = check(self)
        ...
```

**Initial surprise:** The loop `reversed(type(self).__mro__)` combined with a dict seems like it's trying to deduplicate but the iteration order is unintuitive.

**What it does:** It walks the MRO from base to derived (reversed MRO), inserting marked methods by name. A subclass method with the same name overwrites the base entry — correct override semantics. Then it iterates the dict values and runs all checks.

**The problem:** Python dicts (3.7+) preserve insertion order. Since the loop goes base→derived, the dict ends up with base methods first, derived methods last. This means base checks run before derived checks — intentional. However, the pattern is fragile: if two unrelated classes in the MRO define different `@can_cast_check` methods with the same name but different semantics, one silently wins. Also, `checks.values()` returns values in insertion order, so the run order depends on the iteration order of `cls.__dict__`, which is consistent in CPython but not guaranteed by the language spec.

A simpler implementation would just collect all marked callables in MRO order without deduplication.

#### Final review

TODO:

- Indeed, this stinks...
- For the time being, I propose to just collect all without deduplication
- This needs to documented thoroughly!! This is a key implementation detail for further dev work


# Insights

## Dummay abilities

Dummay abilities are a good way to easily tag onto the character to do stuff (like spirit procs)

## Message passing

- It would be ideal to separate message passing into:
    - collect relevant *commands* + application priority
    - resolve commands in order
    - include the possiblity for a command to apply to other commands to suppress them

## Dataclass usage

- dataclass inheritance:
    - base dataclass Effect
    - child dataclass VolleyEffect
    is super akward by default.
    If the base defines any fields with defaults, then the child can't have any required arguments.
    This is fixed by using @dataclass(kw_only=True) which forces all arguments to be keyword.
- dataclass inheritance is perfectly flexible.
    - A field can be defined as non-init with a default at base
    - Then redefined as init with no-default on the child
- a field with no information is field(default=MISSING, default_factory=MISSING, init=True, repr=True, hahs=None, compare=True, kw_only=False)
