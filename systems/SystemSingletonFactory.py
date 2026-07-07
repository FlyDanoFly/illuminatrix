# from DmxLightSystem import DmxLightSystem
from bases.InputSystem import InputSystem
from bases.LightSystem import LightSystem
from bases.SoundSystem import SoundSystem
from constants.constants import Environment
from systems.concrete.DmxLightSystem import DmxLightSystem
from systems.concrete.JackSoundSystem import JackSoundSystem
from systems.concrete.KeyboardInputSystem import KeyboardInputSystem
from systems.concrete.PrintInputSystem import PrintInputSystem
from systems.concrete.PrintLightSystem import PrintLightSystem
from systems.concrete.PrintSoundSystem import PrintSoundSystem
from systems.concrete.SwitchInputSystem import SwitchInputSystem
from systems.concrete.WebSimulationLightSystem import WebSimulationLightSystem


class SystemSingletonFactory:
    # TODO: flip this so these are grouped by environment
    LIGHT_SYSTEM_MAP: dict[Environment, type[LightSystem]] = {
        Environment.EMBEDDED: DmxLightSystem,
        Environment.WEB: WebSimulationLightSystem,
        Environment.PRINT: PrintLightSystem,
    }
    SOUND_SYSTEM_MAP: dict[Environment, type[SoundSystem]] = {
        Environment.EMBEDDED: JackSoundSystem,
        Environment.WEB: JackSoundSystem,
        Environment.PRINT: PrintSoundSystem,
    }
    INPUT_SYSTEM_MAP: dict[Environment, type[InputSystem]] = {
        Environment.EMBEDDED: SwitchInputSystem,
        Environment.WEB: KeyboardInputSystem,
        Environment.PRINT: PrintInputSystem,
    }

    _light_system: LightSystem
    _sound_system: SoundSystem
    _input_system: InputSystem

    def __init__(self, mode: Environment, context: dict):
        self.mode: Environment = mode
        self.context: dict = context or {}

        input_system = SystemSingletonFactory.INPUT_SYSTEM_MAP[self.mode]
        self._input_system = input_system(**self.context["input_system"])

        # The pad LEDs ride the same serial link as the switches, so the
        # light system borrows the input system's controller; the input
        # system owns its lifecycle
        light_kwargs = dict(self.context["light_system"])
        if isinstance(self._input_system, SwitchInputSystem):
            light_kwargs["stomp_pad_controller"] = self._input_system.stomp_pads
        light_system = SystemSingletonFactory.LIGHT_SYSTEM_MAP[self.mode]
        self._light_system = light_system(**light_kwargs)

        sound_system = SystemSingletonFactory.SOUND_SYSTEM_MAP[self.mode]
        self._sound_system = sound_system(**self.context["sound_system"])

    def get_light_system(self) -> LightSystem:
        return self._light_system

    def get_sound_system(self) -> SoundSystem:
        return self._sound_system

    def get_input_system(self) -> InputSystem:
        return self._input_system
