# Fellowship game mechanics


## Damage formula

For typical effects, damage is scaled directly by crit, expertise and main stat:

- main stat and expertise have a multiplicative effect on damage:

    ```
    scaled_damage = base_damage / 1000 * main_stat * (1 + expertise_percent)
    ```

- crit percent changes the chance of a critical hit.
    Criticals deal double damage, further modified by any modifiers to critical damage (from purple gems or talents such as rime 6a).
    When crit percent goes above 100%, the hit is guaranteed to be a grievous critical.

    ````
    normal_hit_damage = scaled_damage
    crit_damage = 2 * scaled_damage * (1 + bonus_crit_multiplier)
    grievous_crit_damage = (1 + crit_percent) * scaled_damage * (1 + bonus_crit_multiplier)
    ````

Averaging out the chance of a crit, we get the overall formula for damage:

````
average_damage = (1 + crit_percent (2 * (1 + bonus_crit_multiplier) - 1) ) * base_damage / 1000 * main_stat * (1 + expertise_percent)
````


## Effects of haste

Haste scales:

- GCD duration, except on Meiko and Mara:

    ```
    gcd_duration = 1.5 / (1 + haste_percent)
    ```

- cast times, except for channels

- dot tick rate

- channel tick rate, but not their duration

    - for example:
        - Elarion's heartseeker barrage will always last 2 seconds (without the talent)
        - But haste will change the tick rate from `0.2` to `0.2 / (1 + haste_percent)`
        - This means that the number of ticks changes from 10 to `floor(10 * (1 + haste_percent))`
        - There are *breakpoints* every 10% of haste:
            - between 0 and 9.9%: 10 hits
            - between 10 and 19.9: 11 hits
            - etc

Overall, for most characters, haste just scales multiplicatively their dps: they do the same thing but faster.
However:

- haste makes it so that you go faster through your good abilities and have to cast more of your bad ones.
    This makes haste slightly worse.
- haste double dips for dots:
    - you cast them faster.
    - they tick faster.
- other mechanics might have good interactions with haste


## Channels and dots: damage




## Snapshotting

- When the game creates a missile (for example, elarion arrow, rime spell object, etc.), it snapshots the stats of the character.
    - For example, for rime, when under the effects of the Winter's Embrace buff (+20% damage):
        - using comet creates the missile straight away, getting the +20% damage buff;
        - casting blast or bolt only benefits *if the cast finishes while the buff is still on*;
        - casting torrent: only the ticks which complete while the buff is still on benefit.

- For channels, tick rate appears to be static and computed when the spell is cast.

- For some effects which do an attack on schedule (elarion volley, rime bursting ice), these snapshot haste on cast. Damage is dynamic: they snapshot character stat on each attack.

- For DoTs, tick rate is dynamic. If haste changes, the tick rate is updated instantaneously. Damage is also dynamic: they snapshot character stat on each attack.

## Damage accumulators


## realPPM mechanics


## Cast checks

Casts have a number of checks:

- is the cast facing the right direction.
- is the target close enough.
- is the target visible.
- are there sufficient resources to do the cast.

These checks are done both:

- at cast start; preventing a cast when conditions aren't met.
- at cast end; cancelling an invalid cast if conditions don't remain satisfactory.



## Main stat multipliers

there are three types of main stat modifiers:

- true multipliers: drakheim set * 1.2, wraithtide set * 1.04 and white 4/9 1.03 /1.09
- additive multipliers (bucket 2): everything else
- additive flat

The final formula is:

- (base main stat + additive) * (1 + SUM bucket 2) * PRODUCT true_multipliers

Main stat modifiers are

```
GEMS

overcap = x

PCT

red 1 = 0.03
red 6 = 0.09
white 4 = 0.03      (True multiplier)
white 9 = 0.09      (True multiplier)
blue 1 = 0.08
blue 6 = 0.24

ADDITIVE FLAT

red 2 = 15
red 7 = 45
white 2 = 25
white 7 = 75


TRAITS

willful = 0.048
vengeful = 0.064
martial = 0.1
hidden power = 0.12

SETS

Draconic = 0.18
Drakheim = 0.2      (True multiplier)
Torment = 0.04      (True multiplier)

HERO SPECIFIC
Helena - Second Wind = 0.2      (True multiplier)
```


## Events

Various mechanics of the game are triggered in response to specific events.

For example, the spirit proc triggers when an ability sends the AbilityCastSuccess event:

- on instant casts, this is immediate.
- on casts, this is at the end of a cast.
- on channels, this is at the end of the channel.

Paying attention to the precise event triggering an effect can be key in understanding it precisely enough to model it in a simulation.

## Time of flight

In game, various effects have various time-of-flight mechanics:

- instant,
- fixed delay,
- fixed speed,
- etc.

The simulation currently applies flat time-of-flight to each ability.
Everything is very ad-hoc and unrealistic.
