from abc import ABC, abstractmethod
from typing import Any

from bases.BaseSystem import BaseSystem
from constants.constants import TowerEnum


class Sound(ABC):
    @abstractmethod
    def is_done(self) -> bool:
        pass

    @abstractmethod
    def start_fade_out(self, duration_sec: float) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def mix_into(self, output_buffers: list[Any], channel_map: list[TowerEnum]) -> None:
        pass


class SoundSystem(BaseSystem):
    @abstractmethod
    def load_sound_bank(self, path: str) -> None:
        """Load a sound bank from the specified path."""
        pass

    @abstractmethod
    def play(self, sound: str, tower_enums: list[TowerEnum] | None = None, volume: float = 1.0, num_loops: int = 0) -> Sound:
        pass

    @abstractmethod
    def stop_all(self):
        pass

    @abstractmethod
    def are_any_sounds_playing(self) -> bool:
        """Check if any sounds are currently playing."""
        return False
