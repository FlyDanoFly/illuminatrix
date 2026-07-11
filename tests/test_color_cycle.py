"""Tests for ColorCycle's sound-reactive behavior: the whitening clamp
(an overdriven knob whites out instead of crashing), the ambient-loop
self-heal (a dropped loop is re-played, throttled), and the intro fade
timing. Runs on the fake systems from test_game_controller.

Runs two ways:

    poetry run pytest tests/
    poetry run python tests/test_color_cycle.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from test_game_controller import FakeManagerFactory, FakeSystemFactory  # noqa: E402

import games.ColorCycle as cc_mod  # noqa: E402
from components.TowerController import TowerController  # noqa: E402
from constants.constants import TowerEnum  # noqa: E402
from games.ColorCycle import (  # noqa: E402
    COLOR_CYCLE_SUSTAIN_TIME_SEC,
    LOOP_RETRY_SECS,
    ColorCycle,
)

FRAME_SECS = 1 / 30


class Rig:
    def __init__(self):
        self.systems = FakeSystemFactory()
        self.sounds = self.systems.sound
        self.lights = self.systems.light
        self.managers = FakeManagerFactory(self.systems)
        self.effects = self.managers.get_effect_manager()
        self.towers = TowerController(self.systems, self.managers)
        self.game = ColorCycle(self.towers)


def test_first_frame_starts_a_loop_and_fade_per_tower():
    rig = Rig()
    rig.game.first_frame_update()
    loop_names = {f"ambient_tower_{t.value}" for t in TowerEnum}
    assert set(rig.sounds.played) == loop_names, "one ambient loop per tower"
    assert len(rig.effects._active_effects) == len(TowerEnum)


def test_intro_fade_uses_the_sustain_constant():
    rig = Rig()
    rig.game.first_frame_update()
    for effect in rig.effects._active_effects:
        assert effect._sustain_time_sec == COLOR_CYCLE_SUSTAIN_TIME_SEC, \
            "the fade must not silently reuse the fade time as sustain"


def test_overdriven_whitening_whites_out_instead_of_crashing():
    rig = Rig()
    rig.game.first_frame_update()
    rig.effects.stop_all()  # skip the intro gate
    rig.sounds.levels = {t: 1.0 for t in TowerEnum}
    original = cc_mod.SOUND_LEVEL_WHITENING
    cc_mod.SOUND_LEVEL_WHITENING = 1.5
    try:
        # One ramp-length step applies the full whitening; must not raise
        # on the negative saturation it would otherwise produce
        rig.game.update(cc_mod.SOUND_LEVEL_RAMP_SECS)
    finally:
        cc_mod.SOUND_LEVEL_WHITENING = original
    assert all(color == (1.0, 1.0, 1.0) for color in rig.lights.colors.values()), \
        "full level with an overdriven knob clamps to white"


def test_loud_towers_run_whiter_than_quiet_ones():
    rig = Rig()
    rig.game.first_frame_update()
    rig.effects.stop_all()
    rig.sounds.levels[TowerEnum.Tower_1] = 1.0
    rig.game.update(cc_mod.SOUND_LEVEL_RAMP_SECS)
    loud = rig.lights.colors[TowerEnum.Tower_1]
    assert min(loud) > 0.0, "a loud tower is pulled toward white"


def test_whitening_ramps_in_after_the_intro():
    rig = Rig()
    rig.game.first_frame_update()
    rig.effects.stop_all()
    rig.sounds.levels = {t: 1.0 for t in TowerEnum}
    rig.game.update(FRAME_SECS)
    first = min(rig.lights.colors[TowerEnum.Tower_1])
    rig.game.update(FRAME_SECS)
    second = min(rig.lights.colors[TowerEnum.Tower_1])
    assert first < 0.2, "whitening starts near zero at the handoff, no snap"
    assert second > first, "and eases in over the ramp"


def test_dropped_loops_are_replayed_after_the_retry_window():
    rig = Rig()
    rig.game.first_frame_update()  # NullSound: every loop is born "done"
    assert len(rig.sounds.played) == len(TowerEnum)
    rig.game.update(LOOP_RETRY_SECS / 2)
    assert len(rig.sounds.played) == len(TowerEnum), "throttled: no retry yet"
    rig.game.update(LOOP_RETRY_SECS / 2 + 0.1)
    assert len(rig.sounds.played) == 2 * len(TowerEnum), \
        "done loops are re-played once the window elapses"


def test_healing_works_during_the_intro_fade():
    rig = Rig()
    rig.game.first_frame_update()
    assert rig.effects.are_any_playing(), "intro fades still running"
    rig.game.update(LOOP_RETRY_SECS + 0.1)
    assert len(rig.sounds.played) == 2 * len(TowerEnum), \
        "the effect gate must not block loop healing"


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items())
             if name.startswith("test_") and callable(fn)]
    for fn in tests:
        fn()
        print(f"{fn.__name__} OK")
    print(f"\nAll {len(tests)} tests passed")
