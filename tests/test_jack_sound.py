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


def test_looping_wraps_gapless_and_finite_loops_run_out():
    snd = make_sound(n_samples=30, num_loops=1)
    bufs = make_buffers(frames=50)
    snd.mix_into(bufs, [TowerEnum.Tower_1])
    assert numpy.allclose(bufs[0], 1.0), "loop boundary fills the whole buffer — no silent gap"
    assert snd.loops == 0
    assert not snd.is_done()
    snd.mix_into(make_buffers(frames=50), [TowerEnum.Tower_1])
    assert snd.is_done(), "last loop played out"


def test_infinite_loop_never_finishes_and_fills_every_buffer():
    snd = make_sound(n_samples=30, num_loops=-1)
    for _ in range(10):
        bufs = make_buffers(frames=50)
        snd.mix_into(bufs, [TowerEnum.Tower_1])
        assert numpy.allclose(bufs[0], 1.0), "gapless across every wrap"
        assert not snd.is_done()


def test_loop_boundary_coinciding_with_block_end_is_not_done():
    # Regression: when the block ends exactly at the data's end, position
    # rests at len(data) without wrapping; a looping sound must still
    # report not-done and continue on the next callback
    snd = make_sound(n_samples=50, num_loops=-1)
    snd.mix_into(make_buffers(frames=50), [TowerEnum.Tower_1])
    assert snd.position == 50, "block ended exactly at the data end"
    assert not snd.is_done()
    bufs = make_buffers(frames=50)
    snd.mix_into(bufs, [TowerEnum.Tower_1])
    assert numpy.allclose(bufs[0], 1.0), "next callback wrapped and kept playing"


def test_stop_is_immediately_done_and_mixes_silence():
    snd = make_sound()
    snd.stop()
    assert snd.is_done()
    bufs = make_buffers()
    snd.mix_into(bufs, [TowerEnum.Tower_1])
    assert not bufs[0].any(), "a stopped sound contributes nothing"


def test_zero_length_sound_is_born_done_and_mixes_nothing():
    # Regression: an empty/corrupt file played as a loop used to spin
    # mix_into's wrap loop forever on the JACK realtime thread
    snd = make_sound(n_samples=0, num_loops=-1)
    assert snd.is_done(), "a zero-length sound is finished before it starts"
    bufs = make_buffers()
    snd.mix_into(bufs, [TowerEnum.Tower_1])  # must return, not hang
    assert not bufs[0].any()


def test_stop_on_looping_sound_mixes_silence():
    # Regression: stop() on a num_loops=-1 sound used to re-wrap in the
    # one mix_into before pruning and emit a full-amplitude sample (click)
    snd = make_sound(num_loops=-1)
    snd.mix_into(make_buffers(), [TowerEnum.Tower_1])
    snd.stop()
    assert snd.is_done()
    bufs = make_buffers()
    snd.mix_into(bufs, [TowerEnum.Tower_1])
    assert not bufs[0].any(), "a stopped looping sound contributes nothing"


def test_fade_restart_continues_from_current_amplitude():
    # Regression: retriggering start_fade_out used to rebuild the curve
    # from full volume — an audible pop when two stop_alls overlap
    snd = make_sound()
    snd.start_fade_out(0.1)  # 100-frame curve from 1.0
    snd.mix_into(make_buffers(frames=50), [TowerEnum.Tower_1])
    mid_amplitude = snd.fade_out_curve[50]  # ~0.5
    snd.start_fade_out(0.1)
    bufs = make_buffers(frames=50)
    snd.mix_into(bufs, [TowerEnum.Tower_1])
    assert abs(bufs[0][0] - mid_amplitude) < 0.02, \
        "restarted fade begins near the current amplitude, not full volume"


def test_zero_duration_fade_then_refade_does_not_crash():
    # Regression: a fade shorter than one sample leaves an empty active
    # curve; a second overlapping fade then indexed the empty array
    snd = make_sound()
    snd.start_fade_out(0.0)
    snd.start_fade_out(1.0)  # must not raise
    bufs = make_buffers(frames=50)
    snd.mix_into(bufs, [TowerEnum.Tower_1])
    assert abs(bufs[0][0] - 1.0) < 0.01, "refade starts from the sound's volume"


def test_zero_duration_fade_alone_completes_next_callback():
    snd = make_sound()
    snd.start_fade_out(0.0)
    snd.mix_into(make_buffers(), [TowerEnum.Tower_1])
    assert snd.is_done(), "an empty curve exhausts immediately"


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
