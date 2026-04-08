# Fellowship game mechanics


## Damage formula


## Effects of haste


## Channels and dots: damage


## Snapshotting


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

The simulation currently ignores all time-of-flight and 
