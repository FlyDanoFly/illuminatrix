"""Tests for JackSoundSystem's bank cache and boot preload. The module's
bank loader is replaced with a counting fake — no files, no JACK.

Runs two ways:

    poetry run pytest tests/
    poetry run python tests/test_sound_bank_cache.py
"""

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import systems.concrete.JackSoundSystem as jsm_mod  # noqa: E402
from systems.concrete.JackSoundSystem import JackSoundSystem  # noqa: E402


class StubMixer:
    def __init__(self):
        self.started = False

    def startup(self):
        self.started = True


class FakeLoader:
    """Counts loads per path; optionally fails for specific paths."""

    def __init__(self, fail_paths: set[str] | None = None):
        self.calls: list[str] = []
        self.fail_paths = fail_paths or set()
        self._original = jsm_mod.load_sound_bank
        jsm_mod.load_sound_bank = self

    def __call__(self, directory: str) -> dict:
        self.calls.append(directory)
        if directory in self.fail_paths:
            raise FileNotFoundError(directory)
        # Shaped like SoundData as far as the load-summary log needs
        return {"a_sound": types.SimpleNamespace(data=[0.0] * 10, samplerate=10)}

    def restore(self):
        jsm_mod.load_sound_bank = self._original


def test_second_load_is_a_cache_hit():
    loader = FakeLoader()
    try:
        system = JackSoundSystem(mixer=StubMixer())
        system.load_sound_bank("sound_banks/simon")
        first = system.sound_bank
        system.load_sound_bank("sound_banks/simon")
        assert loader.calls == ["sound_banks/simon"], "loaded from disk exactly once"
        assert system.sound_bank is first, "same cached bank object"
    finally:
        loader.restore()


def test_trailing_slash_is_the_same_bank():
    # Music.py says "sound_banks/music/", others omit the slash
    loader = FakeLoader()
    try:
        system = JackSoundSystem(mixer=StubMixer())
        system.load_sound_bank("sound_banks/music/")
        system.load_sound_bank("sound_banks/music")
        assert len(loader.calls) == 1
    finally:
        loader.restore()


def test_preload_warms_cache_for_game_entries():
    loader = FakeLoader()
    try:
        banks = ["sound_banks/ambient", "sound_banks/simon"]
        system = JackSoundSystem(mixer=StubMixer())
        system.preload_sound_banks(banks)
        assert loader.calls == banks, "every declared bank loaded up front"
        system.load_sound_bank("sound_banks/ambient")  # a game entering
        assert len(loader.calls) == 2, "mid-show switch never touches disk"
    finally:
        loader.restore()


def test_broken_preload_bank_does_not_break_boot():
    loader = FakeLoader(fail_paths={"sound_banks/broken"})
    try:
        system = JackSoundSystem(mixer=StubMixer())
        system.preload_sound_banks(["sound_banks/broken", "sound_banks/simon"])  # must not raise
        system.load_sound_bank("sound_banks/simon")
        assert loader.calls.count("sound_banks/simon") == 1, "good bank preloaded and cached"
    finally:
        loader.restore()


def test_unpreloaded_bank_loads_on_demand_and_is_cached():
    # A game running in a context that never preloaded (tests, future
    # harnesses) still gets its bank — it just pays the load once
    loader = FakeLoader()
    try:
        system = JackSoundSystem(mixer=StubMixer())
        system.load_sound_bank("sound_banks/surprise")
        system.load_sound_bank("sound_banks/surprise")
        assert loader.calls == ["sound_banks/surprise"], "loaded once, cached after"
    finally:
        loader.restore()


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items())
             if name.startswith("test_") and callable(fn)]
    for fn in tests:
        fn()
        print(f"{fn.__name__} OK")
    print(f"\nAll {len(tests)} tests passed")
