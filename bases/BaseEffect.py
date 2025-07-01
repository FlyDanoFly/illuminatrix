from bases.InputSystem import InputSystem
from bases.LightSystem import LightSystem
from bases.SoundSystem import SoundSystem
from systems.SystemSingletonFactory import SystemSingletonFactory


class BaseEffect:
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

    def update(self, delta_secs: float) -> bool:
        """Returns True if still playing"""
        raise NotImplementedError("Subclasses should implement this method")

    def is_playing(self) -> bool:
        raise NotImplementedError("Subclasses should implement this method")

    def is_done(self) -> bool:
        raise NotImplementedError("Subclasses should implement this method")
