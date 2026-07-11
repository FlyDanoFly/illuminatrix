"""Tests for per-tower sound-output metering: JackMixer.process() meters
mean-square energy per channel, JackSoundSystem smooths it into 0.0-1.0
perceptual levels, and every SoundSystem answers get_tower_levels() (the
silent ones with zeros). No JACK server needed — ports are stand-ins
with real buffers.

Runs two ways:

    poetry run pytest tests/
    poetry run python tests/test_sound_levels.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from test_jack_sound import make_sound  # noqa: E402

import systems.concrete.JackSoundSystem as jsm_mod  # noqa: E402
from constants.constants import TowerEnum  # noqa: E402
from systems.concrete.JackSoundSystem import (  # noqa: E402
    JackMixer,
    JackSoundSystem,
    MixerState,
    _energy_to_level,
)
from systems.concrete.NullSoundSystem import NullSoundSystem  # noqa: E402
from systems.concrete.PrintSoundSystem import PrintSoundSystem  # noqa: E402

FRAMES = 64
# make_sound bakes amplitude in via volume (mix_into multiplies by it):
# a 0.5-volume sound of ones meters mean-square 0.25 on its channels
HALF = dict(n_samples=FRAMES * 4, volume=0.5)


class BufferPort:
    """Stands in for a jack.OwnPort: a real, writable sample buffer."""

    def __init__(self, frames: int = FRAMES):
        self._buffer = bytearray(4 * frames)  # float32 zeros

    def get_buffer(self):
        return self._buffer


def make_started_mixer(ports: int = 7) -> JackMixer:
    """A mixer wired straight to fake ports, skipping the connect dance
    (covered by test_jack_mixer.py)."""
    mixer = JackMixer()
    mixer.state = MixerState.STARTED
    mixer.outports = [BufferPort() for _ in range(ports)]
    return mixer


def test_process_meters_energy_per_channel():
    mixer = make_started_mixer()
    mixer.play(make_sound(**HALF), [TowerEnum.Tower_1, TowerEnum.Tower_3])
    mixer.process(FRAMES)
    energy = mixer.consume_channel_energy()
    assert abs(energy[0] - 0.25) < 1e-6, "tower 1 carries the 0.5-amplitude signal"
    assert abs(energy[2] - 0.25) < 1e-6, "tower 3 carries it too"
    assert energy[1] == 0.0, "tower 2 is silent"
    assert all(energy[i] == 0.0 for i in range(3, 7))


def test_master_volume_scales_output_and_meter():
    import numpy

    mixer = make_started_mixer()
    mixer.master_volume = 0.5
    mixer.play(make_sound(n_samples=FRAMES * 4, volume=1.0), [TowerEnum.Tower_1])
    mixer.process(FRAMES)
    samples = numpy.frombuffer(mixer.outports[0].get_buffer(), dtype=numpy.float32)
    assert abs(samples[0] - 0.5) < 1e-6, "unity-volume ones leave at the master gain"
    energy = mixer.consume_channel_energy()
    assert abs(energy[0] - 0.25) < 1e-6, \
        "the meter reads post-master output, so the lights follow the speakers"


def test_sound_system_hands_master_volume_to_the_mixer():
    mixer = make_started_mixer()
    system = JackSoundSystem(mixer=mixer)
    system.set_master_volume(0.5)
    assert mixer.master_volume == 0.5


def test_meter_peak_holds_between_consumes():
    mixer = make_started_mixer()
    mixer.play(make_sound(n_samples=FRAMES, volume=0.5), [TowerEnum.Tower_1])
    mixer.process(FRAMES)  # the sound ends within this block
    mixer.process(FRAMES)  # a silent block must not erase the peak
    assert mixer.consume_channel_energy()[0] > 0.0, \
        "a transient in an early block survives until the frame reads it"
    assert mixer.consume_channel_energy()[0] == 0.0, \
        "consuming resets the meter — no callbacks means it reads dark"


def test_process_zeroes_energy_when_not_started():
    mixer = make_started_mixer()
    mixer.play(make_sound(**HALF), [TowerEnum.Tower_1])
    mixer.process(FRAMES)
    assert mixer._channel_energy[0] > 0.0
    mixer.state = MixerState.SHUTDOWN
    mixer.process(FRAMES)
    assert all(e == 0.0 for e in mixer.consume_channel_energy()), \
        "the shutdown window must not leave a stale loud meter"


def test_extra_physical_ports_beyond_towers_are_ignored():
    # An 8-channel interface registers 8 ports; only 7 towers are metered
    mixer = make_started_mixer(ports=8)
    mixer.play(make_sound(**HALF), [TowerEnum.Tower_7])
    mixer.process(FRAMES)  # must not raise on the unmetered port
    assert mixer.consume_channel_energy()[6] > 0.0


def test_teardown_zeroes_energy():
    mixer = make_started_mixer()
    mixer.play(make_sound(**HALF), [TowerEnum.Tower_1])
    mixer.process(FRAMES)
    assert mixer._channel_energy[0] > 0.0
    mixer._teardown_client()
    assert all(e == 0.0 for e in mixer.consume_channel_energy()), \
        "a dead server must not freeze the lights bright"


def test_energy_to_level_mapping():
    assert _energy_to_level(0.0) == 0.0
    assert _energy_to_level(1.0) == 1.0, "full scale is 1.0"
    assert _energy_to_level(2.0) == 1.0, "clipped output clamps to 1.0"
    floor = 10 ** (jsm_mod.LEVEL_FLOOR_DB / 10.0)
    assert _energy_to_level(floor) == 0.0, "the floor reads as silence"
    assert _energy_to_level(floor / 10) == 0.0, "below the floor clamps to 0.0"
    # A full-scale sine (mean square 0.5, -3 dB) reads just under full
    level = _energy_to_level(0.5)
    assert 0.9 < level < 1.0
    # Monotonic through the useful range
    assert _energy_to_level(0.01) < _energy_to_level(0.1) < _energy_to_level(0.5)


def test_degenerate_floor_gates_instead_of_crashing():
    # LEVEL_FLOOR_DB is a documented tuning knob; 0.0 must not divide by zero
    original = jsm_mod.LEVEL_FLOOR_DB
    jsm_mod.LEVEL_FLOOR_DB = 0.0
    try:
        assert _energy_to_level(0.5) == 0.0, "below the gate reads dark"
        assert _energy_to_level(1.0) == 1.0, "full scale still registers"
        assert _energy_to_level(2.0) == 1.0
    finally:
        jsm_mod.LEVEL_FLOOR_DB = original


def test_levels_attack_instantly_and_release_smoothly():
    mixer = make_started_mixer()
    system = JackSoundSystem(mixer=mixer)
    frame_secs = 1 / 30

    mixer._channel_energy[0] = 0.5
    system.update(frame_secs)
    loud = system.get_tower_levels()[TowerEnum.Tower_1]
    assert loud == _energy_to_level(0.5), "attack is instant, no ramp-up frames"

    # The update consumed the meter, so with no new callbacks the level
    # can only release from here
    system.update(frame_secs)
    after_one = system.get_tower_levels()[TowerEnum.Tower_1]
    assert 0.0 < after_one < loud, "release decays instead of dropping to zero"

    for _ in range(int(10 * jsm_mod.LEVEL_RELEASE_SECS / frame_secs)):
        system.update(frame_secs)
    assert system.get_tower_levels()[TowerEnum.Tower_1] < 0.01, \
        "the meter settles back to dark"


def test_levels_track_their_own_tower_only():
    mixer = make_started_mixer()
    system = JackSoundSystem(mixer=mixer)
    mixer._channel_energy[3] = 0.25
    system.update(1 / 30)
    levels = system.get_tower_levels()
    assert levels[TowerEnum.Tower_4] > 0.0
    assert all(levels[t] == 0.0 for t in TowerEnum if t != TowerEnum.Tower_4)


def test_stereo_fallback_mirrors_the_mix_to_all_towers():
    # With two ports every sound plays on both, so each tower's speaker
    # really is carrying the whole mix — the meters should say so
    mixer = make_started_mixer(ports=2)
    mixer.force_play_on_all_channels = True
    system = JackSoundSystem(mixer=mixer)
    mixer._channel_energy[0] = 0.25
    system.update(1 / 30)
    levels = system.get_tower_levels()
    assert levels[TowerEnum.Tower_1] > 0.0
    assert all(levels[t] == levels[TowerEnum.Tower_1] for t in TowerEnum), \
        "every tower reports the mix level on a stereo bench"


def test_silent_systems_report_all_towers_dark():
    for system in (NullSoundSystem(), PrintSoundSystem()):
        levels = system.get_tower_levels()
        assert set(levels) == set(TowerEnum), "every tower is present"
        assert all(level == 0.0 for level in levels.values())


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items())
             if name.startswith("test_") and callable(fn)]
    for fn in tests:
        fn()
        print(f"{fn.__name__} OK")
    print(f"\nAll {len(tests)} tests passed")
