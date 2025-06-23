from abc import abstractmethod

from BaseSystem import BaseSystem
from constants import SystemIdentifier


class Sound:
    pass


class SoundSystem(BaseSystem):
    @abstractmethod
    def play(self, sound: str, system_ids: list[SystemIdentifier] | None = None, volume: float = 1.0) -> Sound:
        pass

    @abstractmethod
    def are_any_sounds_playing(self) -> bool:
        """Check if any sounds are currently playing."""
        return False
