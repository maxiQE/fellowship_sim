"""Step-by-step rotation inspector.

Runs a single simulation, pausing before each cast so you can observe the
game state and confirm the rotation's choice.

Run with:
    python scripts/inspect_rotation.py
"""

import contextlib
import math

from fellowship_sim import configure_logging
from fellowship_sim.base_classes.ability import WeaponAbility
from fellowship_sim.base_classes.stats import RawStatsFromScores
from fellowship_sim.elarion.ability import HighwindArrow, Multishot
from fellowship_sim.elarion.builds import ElarionSetupBasic
from fellowship_sim.elarion.effect import CelestialImpetusAura, LunarlightMarkEffect
from fellowship_sim.elarion.rotations.void_barrage import VoidBarrage
from fellowship_sim.simulation.base import FightOver
from fellowship_sim.simulation.scenarios import boss_fight_scenario, generate_new_scenario

# ---------------------------------------------------------------------------
# Parameterization
# ---------------------------------------------------------------------------

# TRACE | DEBUG | INFO | SUCCESS | WARNING | ERROR
LOG_LEVEL = "INFO"

scenario = boss_fight_scenario(
    duration=300,
    delay_since_last_fight=25,
    initial_spirit_points=130,
)

# 20/20/25/30
STATS = RawStatsFromScores(
    main_stat=2444.0,
    crit_score=900,
    expertise_score=1100,
    haste_score=1655,
    spirit_score=855,
)
HIGH_HP_UPTIME = 0.85

setup = ElarionSetupBasic(
    raw_stats=STATS,
    high_hp_uptime=HIGH_HP_UPTIME,
)

rotation = VoidBarrage()

# ---------------------------------------------------------------------------
# Setup logging + initialize objects
# ---------------------------------------------------------------------------

configure_logging(LOG_LEVEL)

state, elarion = generate_new_scenario(scenario=scenario, setup=setup, rng_seed=12345)

num_enemies_initial = state.num_enemies

# ---------------------------------------------------------------------------
# Manually go through rotation
# ---------------------------------------------------------------------------

SEPARATOR = "=" * 64


def _cd(cooldown: float) -> str:
    return f"{cooldown:.1f}s"


def print_state() -> None:
    sg = elarion.skystrider_grace
    ss = elarion.skystrider_supremacy
    wa = elarion.weapon_ability
    hb = elarion.heartseeker_barrage
    vol = elarion.volley
    lm = elarion.lunarlight_mark
    hwa = elarion.highwind_arrow
    ms = elarion.multishot

    ci_aura = elarion.effects.get(CelestialImpetusAura)

    damage_list = [enemy.damage_tracker.total for enemy in state._enemies]
    main = damage_list[0]
    secondary = sum(damage_list[1:])
    total = sum(damage_list)

    bin_key_size = state.main_target.damage_tracker.bin_key_size
    damage_bucket_list = [list(enemy.damage_tracker.total_by_time_bin.values()) for enemy in state._enemies]
    if state.time >= 2 * bin_key_size:
        instant_dps = [buckets[-2] / bin_key_size for buckets in damage_bucket_list]
    else:
        instant_dps = [0 for buckets in damage_bucket_list]
    main_instant_dps = instant_dps[0]
    secondary_instant_dps = sum(instant_dps[1:])
    total_instant_dps = sum(instant_dps)

    marks_list = [enemy.effects.get(LunarlightMarkEffect) for enemy in state.enemies]
    mark_counts_list = [e.stacks if e is not None else 0 for e in marks_list]
    assert len(marks_list) == len(mark_counts_list)
    main_mark_count = mark_counts_list[0]
    secondary_mark_count = sum(mark_counts_list[1:])

    print(f"\n{SEPARATOR}")
    print(
        f"  t={state.time:6.2f}s   focus={elarion.focus:5.1f}   spirit={elarion.spirit_points:.0f}/{elarion.max_spirit_points:.0f}"
        f"   haste={elarion.stats.haste_percent * 100:<2.0f}   main_target_percent_hp={state.main_target.percent_hp}"
    )
    print(
        f"  dmg      : main={main:>12,.0f}"
        + (f"  secondary={secondary:>12,.0f}  total={total:>12,.0f}" if num_enemies_initial >= 2 else "")
    )
    print(
        f"  total dps: main={main / (state.time + 0.01):>12,.0f}"
        + (
            f"  secondary={secondary / (state.time + 0.01):>12,.0f}  total={total / (state.time + 0.01):>12,.0f}"
            if num_enemies_initial >= 2
            else ""
        )
    )
    print(
        f"  inst dps : main={main_instant_dps:>12,.0f}"
        + (
            f"  secondary={secondary_instant_dps:>12,.0f}  total={total_instant_dps:>12,.0f}"
            if num_enemies_initial >= 2
            else ""
        )
    )
    print()

    # Key info
    ci_str = (
        f"ci_proc={ci_aura.real_ppm.proc_chance * 100:.0f}%  ci_stacks={elarion.celestial_impetus_stacks}"
        if ci_aura is not None
        else "ci=n/a"
    )
    marks_str = f"marks: main={main_mark_count}  secondary={secondary_mark_count}"
    print(f"  {ci_str}   {marks_str}")

    # Long cooldowns
    wa_str = f"weapon({_cd(wa.cooldown)})" if isinstance(wa, WeaponAbility) else "weapon(n/a)"
    print(f"  long  cd : grace({_cd(sg.cooldown)})  supremacy({_cd(ss.cooldown)})  {wa_str}")

    # Short cooldowns
    print(f"  short cd : barrage({_cd(hb.cooldown)})  volley({_cd(vol.cooldown)})  mark({_cd(lm.cooldown)})")

    # HWA: charges + cooldown
    assert isinstance(hwa, HighwindArrow)
    print(f"  hwa      : {hwa.charges}/{hwa.max_charges} charges  cd={_cd(hwa.cooldown)}")

    # Multishot: charges + empowered status
    assert isinstance(ms, Multishot)
    ms_empowered = f"  [{ms.empowered_by()}]" if ms.is_empowered() else ""
    print(f"  multishot: {ms.charges}/{ms.max_charges} charges{ms_empowered}")

    # Active effects on elarion
    if elarion.effects:
        fx_str = "  |  ".join(str(fx) for fx in elarion.effects if math.isfinite(fx.duration))
        print(f"  effects  : {fx_str}")


step = 0
with contextlib.suppress(FightOver):
    for ability in rotation(elarion):
        step += 1
        print_state()

        if ability is None:
            print("  >>> (nothing castable — passing)")
        else:
            print(f"  >>> {ability}")

        try:
            input("\n  [Enter] to cast, [Ctrl-C] to quit ")
        except KeyboardInterrupt:
            print("\nAborted.")
            break

        if ability is not None:
            ability.cast(target=state.main_target)

print(f"\n{SEPARATOR}")
print(f"Fight over at t={state.time:.1f}s after {step} steps.")
print(f"Total damage: {elarion.damage_tracker.total:,.0f}")
