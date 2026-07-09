from bases.InputSystem import InputSystem
from bases.LightSystem import LightSystem
from bases.SoundSystem import Sound, SoundSystem
from constants.constants import ColorType, LightPos, TowerEnum
from managers.EffectManager import EffectManager
from managers.ManagerSingletonFactory import ManagerSingletonFactory
from systems.SystemSingletonFactory import SystemSingletonFactory


class Tower:
    def __init__(self, tower_enum: TowerEnum, system: SystemSingletonFactory, manager: ManagerSingletonFactory):
        self._tower_enum = tower_enum
        self._light_system: LightSystem = system.get_light_system()
        self._sound_system: SoundSystem = system.get_sound_system()
        self._input_system: InputSystem = system.get_input_system()
        self._effects: EffectManager = manager.get_effect_manager()

    def set_color(self, color: ColorType, light: LightPos = LightPos.All):
        self._light_system.set(self._tower_enum, color, light)

    def play_sound(self, sound, volume: float = 1.0, num_loops: int = 0) -> Sound | None:
        """None when the sound is unknown or was dropped (JACK down) —
        callers gating on the result must treat None as already done."""
        return self._sound_system.play(sound, [self._tower_enum], volume, num_loops)

    def is_switch_pressed(self) -> bool:
        return self._input_system.is_tower_switch_pressed(self._tower_enum)

    def did_switch_transition_down(self) -> bool:
        return self._input_system.did_tower_switch_transition_down(self._tower_enum)

    def did_switch_transition_up(self) -> bool:
        return self._input_system.did_tower_switch_transition_up(self._tower_enum)
