from constants import ColorType, LightPos, SystemIdentifier, TowerEnum
from InputSystem import InputSystem
from LightSystem import LightSystem
from SoundSystem import SoundSystem


class Tower:
    def __init__(
            self,
            tower_enum: TowerEnum,
            system_identifier: SystemIdentifier,
            light_system: LightSystem,
            sound_system: SoundSystem,
            input_system: InputSystem,
    ):
        self._tower = tower_enum
        self._system_identifier = system_identifier
        self._light_system = light_system
        self._sound_system = sound_system
        self._input_system = input_system

    def set_color(self, color: ColorType, light: LightPos = LightPos.All):
        self._light_system.set(self._system_identifier, color, light)

    def play_sound(self, sound, volume: float = 1.0):
        self._sound_system.play(sound, self._system_identifier)

    def get_switch_state(self) -> bool:
        return self._input_system.get_switch_state(self._system_identifier)
