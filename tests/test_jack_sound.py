"""Tests for JackSound's mixing math: volume, fades, loops, channel maps.

Pure numpy — no JACK server, no audio hardware. Runs two ways:

    poetry run pytest tests/
    poetry run python tests/test_jack_sound.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy  # noqa: E402

from constants.constants import TowerEnum  # noqa: E402
from systems.concrete.JackSoundSystem import JackSound  # noqa: E402

SAMPLERATE = 1000


def make_sound(n_samples: int = 200, volume: float = 1.0, num_loops: int = 0) -> JackSound:
    data = numpy.ones(n_samples, dtype=numpy.float32)
    return JackSound(filename="test", data=data, samplerate=SAMPLERATE,
                     volume=volume, num_loops=num_loops)


def make_buffers(channels: int = 7, frames: int = 50) -> list[numpy.ndarray]:
    return [numpy.zeros(frames, dtype=numpy.float32) for _ in range(channels)]


def test_volume_applied_and_unmapped_channels_silent():
    snd = make_sound(volume=0.5)
    bufs = make_buffers()
    snd.mix_into(bufs, [TowerEnum.Tower_1, TowerEnum.Tower_3])
    assert numpy.allclose(bufs[0], 0.5)
    assert numpy.allclose(bufs[2], 0.5)
    assert not bufs[1].any(), "unmapped channel must stay silent"


def test_position_advances_once_regardless_of_channel_count():
    solo, multi = make_sound(), make_sound()
    bufs = make_buffers()
    solo.mix_into(bufs, [TowerEnum.Tower_1])
    multi.mix_into(bufs, list(TowerEnum))
    assert solo.position == 50
    assert multi.position == 50, "playing on 7 towers must not advance 7x"


def test_fade_advances_once_per_callback_across_channels():
    # Regression: fade_out_index used to advance once per mapped channel,
    # so a multi-tower sound faded N times too fast
    snd = make_sound()
    snd.start_fade_out(0.1)  # 100 frames of fade curve at 1kHz
    bufs = make_buffers(frames=50)
    snd.mix_into(bufs, [TowerEnum.Tower_1, TowerEnum.Tower_2, TowerEnum.Tower_3])
    assert snd.fade_out_index == 50, "one 50-frame callback consumes 50 fade frames"
    assert not snd.is_done()
    snd.mix_into(make_buffers(frames=50), [TowerEnum.Tower_1, TowerEnum.Tower_2])
    assert snd.fade_out_index == 100
    assert snd.is_done(), "fade curve exhausted"


def test_fade_is_identical_on_every_mapped_channel():
    snd = make_sound()
    snd.start_fade_out(0.1)
    bufs = make_buffers(frames=50)
    snd.mix_into(bufs, [TowerEnum.Tower_1, TowerEnum.Tower_7])
    assert numpy.array_equal(bufs[0], bufs[6]), "all towers hear the same fade"
    expected = snd.fade_out_curve[:50]
    assert numpy.allclose(bufs[0], expected)


def test_fade_starts_from_current_volume():
    snd = make_sound(volume=0.5)
    snd.start_fade_out(0.1)
    bufs = make_buffers(frames=50)
    snd.mix_into(bufs, [TowerEnum.Tower_1])
    assert abs(bufs[0][0] - 0.5) < 1e-6, "fade begins at the sound's volume"
    assert bufs[0][49] < bufs[0][0], "and decreases"


def test_looping_wraps_and_finite_loops_run_out():
    snd = make_sound(n_samples=30, num_loops=1)
    snd.mix_into(make_buffers(frames=50), [TowerEnum.Tower_1])
    assert snd.position == 0, "wrapped to the start"
    assert snd.loops == 0
    assert not snd.is_done()
    snd.mix_into(make_buffers(frames=50), [TowerEnum.Tower_1])
    assert snd.is_done(), "last loop played out"


def test_infinite_loop_never_finishes():
    snd = make_sound(n_samples=30, num_loops=-1)
    for _ in range(10):
        snd.mix_into(make_buffers(frames=50), [TowerEnum.Tower_1])
        assert not snd.is_done()


def test_stop_is_immediately_done_and_mixes_silence():
    snd = make_sound()
    snd.stop()
    assert snd.is_done()
    bufs = make_buffers()
    snd.mix_into(bufs, [TowerEnum.Tower_1])
    assert not bufs[0].any(), "a stopped sound contributes nothing"


def test_towers_beyond_output_count_are_skipped():
    # Stereo fallback: 2 physical ports, sound mapped to all 7 towers
    snd = make_sound()
    bufs = make_buffers(channels=2)
    snd.mix_into(bufs, list(TowerEnum))  # must not raise
    assert numpy.allclose(bufs[0], 1.0)
    assert numpy.allclose(bufs[1], 1.0)
    assert snd.position == 50


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items())
             if name.startswith("test_") and callable(fn)]
    for fn in tests:
        fn()
        print(f"{fn.__name__} OK")
    print(f"\nAll {len(tests)} tests passed")
