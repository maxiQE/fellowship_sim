# Unit test




# Integration tests

Multishot: max number of charges

Focus proc -> +1 spirit

Navigators intuition:
    - buffs correct stat
    - renews correctly
    - updates stats on add and on remove
    - complex scenario:
        - buff comes in, applies to spirit
        - base stat changes, making haste the biggest one
        - buff is renewed
        - assert buff is still targetting spirit


Harmonious soul: HarmoniousSoulBuff

    - test expiration -> -1 stack instead of removal
    - test adding: +1 stack + renew




# Functional tests

- celestial shot with CI proc can consume mark immediately
- spirit proc from celestial shot can consume mark immediately

- EH horizon CDA:
    - stacking with HWA
    - stacking with skylit grace
    - stacking with chronoshift

- Chronoshift + skylit grace stacking

