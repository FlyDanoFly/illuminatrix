from abc import ABC, abstractmethod

from bases.InputSystem import InputSystem
from bases.LightSystem import LightSystem
from bases.SoundSystem import SoundSystem
from constants.constants import ShouldStop
from systems.SystemSingletonFactory import SystemSingletonFactory


class BaseEffect(ABC):
    """
    Base class for re-usable effects.

    Games can use subclasses to do effects. They should instantiate the effect and then
    pass it to the TowerController that will take in from there.
    """

    def attach_systems(self, system: SystemSingletonFactory) -> None:
        """
        ** Should only be called by the manager class. **
        """
        self._light_system: LightSystem = system.get_light_system()
        self._sound_system: SoundSystem = system.get_sound_system()
        self._input_system: InputSystem = system.get_input_system()

    @abstractmethod
    def update(self, delta_secs: float) -> ShouldStop:
        """Returns True if not playing"""

    @abstractmethod
    def is_playing(self) -> bool:
        pass

    @abstractmethod
    def is_done(self) -> bool:
        pass
