from abc import abstractmethod

from BaseSystem import BaseSystem
from constants import SystemIdentifier


class SoundSystem(BaseSystem):
    @abstractmethod
    def play(self, sound: str, system_id: SystemIdentifier, volume: float = 1.0) -> None:
        pass
