from abc import abstractmethod

from BaseSystem import BaseSystem
from constants import SystemIdentifier


class SoundSystem(BaseSystem):
    @abstractmethod
    def play(self, system_id: SystemIdentifier, sound: str) -> None:
        pass
