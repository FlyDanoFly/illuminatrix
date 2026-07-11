from abc import ABC, abstractmethod
from typing import Any

from bases.BaseSystem import BaseSystem
from constants.constants import TowerEnum


class Sound(ABC):
    @abstractmethod
    def is_done(self) -> bool:
        pass

    @abstractmethod
    def start_fade_out(self, fade_secs: float) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def mix_into(self, output_buffers: list[Any], channel_map: list[TowerEnum]) -> None:
        pass


class NullSound(Sound):
    """A silent sound that is already over.

    play() returns one when a sound can't actually start (unknown key,
    or the mixer dropped it while JACK is down), so callers gating on
    is_done() move on naturally instead of guarding against None — a
    sound whose is_done() can never come true must not escape into game
    code."""

    def is_done(self) -> bool:
        return True

    def start_fade_out(self, fade_secs: float) -> None:
        pass

    def stop(self) -> None:
        pass

    def mix_into(self, output_buffers: list[Any], channel_map: list[TowerEnum]) -> None:
        pass


class SoundSystem(BaseSystem):
    # Class-level default so subclasses that skip super().__init__()
    # still read 1.0 (full volume) until someone sets it
    _master_volume: float = 1.0

    def set_master_volume(self, volume: float) -> None:
        """Scale all output by 0.0-1.0, on top of per-sound volumes.
        Applies to sounds already playing, not just future play() calls.
        Default just records it; silent systems have nothing to scale."""
        self._master_volume = volume

    @abstractmethod
    def load_sound_bank(self, path: str) -> None:
        """Load a sound bank from the specified path."""
        pass

    def preload_sound_banks(self, paths: list[str]) -> None:
        """Optimization hook: warm these banks ahead of time so later
        load_sound_bank calls don't stall. Default: do nothing."""

    @abstractmethod
    def play(self, sound: str, tower_enums: list[TowerEnum] | None = None, volume: float = 1.0, num_loops: int = 0) -> Sound:
        """Play a sound from the loaded bank. Always returns a Sound:
        one that can't start (unknown key, mixer down) comes back as an
        already-finished NullSound, so callers never need a None guard."""

    @abstractmethod
    def stop_all(self, fade_secs: float = 0.25):
        pass

    @abstractmethod
    def are_any_sounds_playing(self) -> bool:
        """Check if any sounds are currently playing."""
        return False

    def get_tower_levels(self) -> dict[TowerEnum, float]:
        """Perceptual output level per tower, 0.0 (silence) to 1.0 (full
        scale), smoothed for driving lights: instant attack, gentle
        release. Default: all silent, so systems without real audio
        output (Null, Print) degrade to a dark meter for free."""
        return {tower_enum: 0.0 for tower_enum in TowerEnum}
