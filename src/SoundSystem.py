from abc import abstractmethod

from BaseSystem import BaseSystem
from constants import SystemIdentifier


class SoundSystem(BaseSystem):
    @abstractmethod
    def play(self, tower_id: SystemIdentifier, sound: str): pass
