# Bonus crit damage from amethyst splinters and blessing of the deathdealer

How is bonus crit damage from blessing of deathdealer applied? I think bonus is doubled, ie:

That makes way more sense, but means that all my modelling is wrong...

    - crit_damage = base * 2 * (1 + m)
    - instead of
    - crit_damage = base * (1 + 1 + m)

changing average damage to:

    - average = base * ((1-p) + 2 * (1 + m) * p) = base * (1 + (2 * (1 + m) - 1) * p)
    - instead of
    - average = base * ((1-p) * (1 + 1 + m) * p) = base * (1 + (1 + m) * p)


# Amethyst splinters:

Theory:

- On renew:
    - discount the current accumulation by multiplying with: `remaining_time / total_time`
    - add new incomming damage
    - do not change the timing of the next tick

- haste is not snapshotted: the time to next tick is computed like a cooldown


## Open questions

### Crit multiplier role in damage formula

TC crafting question that I can't test myself
how exactly do the 5p 10p changes to crit damage multiplier work?
- A: crit damage is 2 * base * 1.03 (or * 1.09)
- B: crit damage is base + base * 1.03                   (this corresponds to mutpliying *only* the bonus damage, not the base)
If you have purple gems and are willing to help:
- cast HSB a bunch of times on a dummy
- tell me your lowest normal and your highest crit
- make sure you have 0 effects going on: no willful momentum, no nothing; ideally do it with no weapon and only a few purple gems slotted in

From angry and clankz, option A is correct

### Spirit point regen

- base rate per second
- in combat rate for high level dungeon on AOE
- in combat rate for boss fights

### Focus

- Focus cost of celestial shot (15 base) under event horizon: 7 or 8? Floor or ceiling?

### Damage scaling

- Does +20% damage scale additively or multiplicatively?

### Logs / source identifiers

- Are there "source identifiers" for damage? I think it links back to ability (used to track overall damage breakdown).
- How does this work for amethyst splinters dot damage? Kindle? Other non-ability sources?

### Kindle

- Does kindle damage increase with event horizon (snapshotting or dynamic)?
- Does it scale with expertise?

Theory: probably works like any dot: scaling on all, and dynamic

### Brave machinations

- Does brave machinations trigger on the dot of ice weapons attack? I don't think so but it's worth checking.
    - As currently coded in the sim, it triggers.

### Diamond strike

- Diamond strike damage amplification from stacks: how does it work?
    - Base damage is: `2370 * (1 + k * 0.35) * (1 + s * 0.4)` with usual main stat and expertise percent scaling; with `k` the number of HarmoniousSouls on character, and `s` the number of DiamondStrikeEcho on target.

### Voidbringer touch

- Does it scale with expertise as well as crit?
    - Tooltip value does, but my guess is the threshold doesn't and the expertise scaling applies after.

### Icicle dot

- Icicle dot renew: is the snapshot updated or not?


### Skylit Grace — multiple volleys

- It stacks.

### Double CDA (ult + hwa)

- Appears to just stack.

### CDR of skylit grace + CDA of ult

- Perhaps multiplying?


### Volley

- Volley snapshots haste (does not update dynamically).
- Does Volley snapshot expertise, crit, main stat? (very unlikely??)

## Investigated

### Haste snapshotting

- Dots snapshot haste (do not update dynamically).
- Do other accumulating dots like splinters update with haste dynamically or snapshot?

### Chronoshift

- Chronoshift tick rate scales with haste, including partial haste.


### Amethyst splinters

- Model: stored damage sums, haste updates.
    - Maybe it does more damage than expected? It's super weird.

### Empowered multishot stacking

- Fervent buff is consumed first.


