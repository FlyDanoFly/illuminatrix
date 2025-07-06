from bases.BaseEffect import BaseEffect
from bases.BaseSystem import BaseSystem
from bases.InputSystem import InputSystem
from bases.LightSystem import LightSystem
from bases.SoundSystem import SoundSystem
from systems.SystemSingletonFactory import SystemSingletonFactory


# TODO: The interfaces is the same as BaseSystem but this isn't really a system, either find a better word that can be the interface for a game loop "system" or make it derive from a different but exactly the same base class. We're NOT doing BaseSystemOrManager
class EffectManager(BaseSystem):
    """
    Manage reusuable effects.

    This is a higher level system than the fundamental systems, e.g. light, sound, input. Instead of being independent it sits on top of them, calling them but never the other direction.
    """
    def __init__(self, system: SystemSingletonFactory) -> None:
        self._active_effects = []
        self._system = system
        self._light_system: LightSystem = system.get_light_system()
        self._sound_system: SoundSystem = system.get_sound_system()
        self._input_system: InputSystem = system.get_input_system()

    def startup(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def render(self) -> None:
        pass

    def start_effect(self, effect: BaseEffect) -> None:
        effect.attach_systems(self._system)
        self._active_effects.append(effect)

    def update(self, delta_secs: float) -> None:
        """Returns true if something is playing"""
        still_playing = []
        for effect in self._active_effects:
            effect.update(delta_secs)
            if effect.is_playing():
                still_playing.append(effect)
        self._active_effects = still_playing
