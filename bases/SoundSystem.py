from abc import abstractmethod

from bases.BaseSystem import BaseSystem
from constants.constants import SystemIdentifier


class Sound:
    pass


class SoundSystem(BaseSystem):
    @abstractmethod
    def load_sound_bank(self, path: str) -> None:
        """Load a sound bank from the specified path."""
        pass

    @abstractmethod
    def play(self, sound: str, system_ids: list[SystemIdentifier] | None = None, volume: float = 1.0) -> Sound:
        pass

    @abstractmethod
    def are_any_sounds_playing(self) -> bool:
        """Check if any sounds are currently playing."""
        return False
