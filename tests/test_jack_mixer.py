"""Tests for JackMixer's lifecycle: degraded startup, reconnect, and
server-death recovery. The jack module is replaced with a fake (same
pattern as the serial tests' FakeSerial) — no JACK server needed.

Runs two ways:

    poetry run pytest tests/
    poetry run python tests/test_jack_mixer.py
"""

import sys
import time
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import systems.concrete.JackSoundSystem as jsm_mod  # noqa: E402
from constants.constants import TowerEnum  # noqa: E402
from systems.concrete.JackSoundSystem import (  # noqa: E402
    JackMixer,
    JackSound,
    MixerState,
)


class FakeJackError(Exception):
    pass


class FakePorts:
    def register(self, name):
        return object()  # stands in for an OwnPort; the mixer only stores it


class FakeClient:
    def __init__(self, physical_ports: int):
        self._physical_ports = physical_ports
        self.outports = FakePorts()
        self.activated = False
        self.closed = False

    def set_process_callback(self, cb):
        pass

    def set_shutdown_callback(self, cb):
        pass

    def activate(self):
        self.activated = True

    def deactivate(self):
        if self.closed:
            raise FakeJackError("client already gone")
        self.activated = False

    def close(self):
        self.closed = True

    def get_ports(self, **_):
        return [object() for _ in range(self._physical_ports)]

    def connect(self, a, b):
        pass


class FakeJack:
    """Stands in for the jack module: server presence is toggleable."""

    JackError = FakeJackError

    def __init__(self, physical_ports: int = 7):
        self.server_present = True
        self.physical_ports = physical_ports
        self.clients: list[FakeClient] = []

    def Client(self, name, no_start_server=False, servername=None):
        if not self.server_present:
            raise FakeJackError("simulated: server not running")
        client = FakeClient(self.physical_ports)
        self.clients.append(client)
        return client


def make_mixer(physical_ports: int = 7) -> tuple[JackMixer, FakeJack]:
    fake = FakeJack(physical_ports)
    jsm_mod.jack = types.SimpleNamespace(
        Client=fake.Client,
        JackError=FakeJackError,
    )
    return JackMixer(), fake


def bypass_rate_limit(mixer: JackMixer) -> None:
    mixer._last_connect_attempt_secs = time.monotonic() - (jsm_mod.JACK_RECONNECT_INTERVAL_SECS + 1)


def make_sound() -> JackSound:
    import numpy
    return JackSound(filename="test", data=numpy.ones(100, dtype=numpy.float32), samplerate=1000)


def test_startup_connects_and_registers_ports():
    mixer, fake = make_mixer()
    mixer.startup()
    assert mixer.state == MixerState.STARTED
    assert len(mixer.outports) == 7
    assert not mixer.force_play_on_all_channels


def test_stereo_fallback_detected():
    mixer, fake = make_mixer(physical_ports=2)
    mixer.startup()
    assert mixer.force_play_on_all_channels


def test_missing_server_degrades_and_drops_plays():
    mixer, fake = make_mixer()
    fake.server_present = False
    mixer.startup()  # must not raise
    assert mixer.state == MixerState.DISCONNECTED
    mixer.play(make_sound(), [TowerEnum.Tower_1])  # dropped with a warning
    assert not mixer.is_anything_playing()


def test_play_before_startup_is_a_programming_error():
    mixer, fake = make_mixer()
    try:
        mixer.play(make_sound(), [TowerEnum.Tower_1])
        raise AssertionError("expected RuntimeError")
    except RuntimeError:
        pass


def test_update_reconnects_when_server_appears():
    mixer, fake = make_mixer()
    fake.server_present = False
    mixer.startup()
    mixer.update()  # rate limited: no attempt yet
    assert mixer.state == MixerState.DISCONNECTED
    fake.server_present = True
    bypass_rate_limit(mixer)
    mixer.update()
    assert mixer.state == MixerState.STARTED
    assert len(mixer.outports) == 7


def test_server_death_drops_sounds_and_reconnects():
    mixer, fake = make_mixer()
    mixer.startup()
    mixer.play(make_sound(), [TowerEnum.Tower_1])
    assert mixer.is_anything_playing()
    first_client = fake.clients[0]

    mixer._on_server_shutdown(None, "simulated crash")  # from JACK's thread
    mixer.update()
    assert mixer.state in (MixerState.DISCONNECTED, MixerState.STARTED)
    assert not mixer.is_anything_playing(), \
        "sounds that can never finish must be dropped, or games gating on them hang"
    assert first_client.closed, "dead client torn down"

    bypass_rate_limit(mixer)
    mixer.update()
    assert mixer.state == MixerState.STARTED, "reconnected to the returned server"
    assert len(fake.clients) > 1, "a fresh client was created"


def test_shutdown_is_safe_from_any_state_and_idempotent():
    mixer, fake = make_mixer()
    fake.server_present = False
    mixer.startup()
    mixer.shutdown()  # disconnected: nothing to tear down, must not raise
    assert mixer.state == MixerState.SHUTDOWN

    mixer2, fake2 = make_mixer()
    mixer2.startup()
    mixer2.shutdown()
    mixer2.shutdown()  # second call is a no-op
    assert fake2.clients[0].closed
    mixer2.update()  # ticking after shutdown must not reconnect
    assert mixer2.client is None


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items())
             if name.startswith("test_") and callable(fn)]
    for fn in tests:
        fn()
        print(f"{fn.__name__} OK")
    print(f"\nAll {len(tests)} tests passed")
