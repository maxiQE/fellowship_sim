# Recipes

## Add standard ability

A standard ability either:

- applies a self buff,
- does a standard single target or AOE attack.

It can be implemented by just overwritting the standard fields of Ability.
The standard run-down of ability implements the appropriate logic.

## Add effect to entity

entity.effects.append(EffectClass())

## Empowered ability: copy Elarion Multishot

NB: if somehow the empowered charge thing can resolved in a simpler fashion, do that !!

- write a shared class for all empowered providers

- add additional fields and functions:
    - fields
        - _empowered_providers
        - any other field needed for empowered functionality

    - functions
        - is_empowered -> bool
        - empowered_by -> str (human readable)
        - _empowered_by__instance -> EmpoweredProvider (machine readable)
        - register_empowered_provider(self, provider)
        - unregister_empowered_provider(self, provider)

- overwrite normal ability functions as needed for empowered functionality
    - _check_availability
    - _do_cast
    - _pay_cost_for_cast


