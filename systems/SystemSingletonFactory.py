from bases.InputSystem import InputSystem
from bases.LightSystem import LightSystem
from bases.SoundSystem import SoundSystem
from constants.constants import Environment
from systems.concrete.dmx_controller import DmxController
from systems.concrete.EmbeddedLightSystem import EmbeddedLightSystem
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
        Environment.EMBEDDED: EmbeddedLightSystem,
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

        # The embedded light system's controllers are constructed here,
        # not by the class: the DMX controller from its config dict in the
        # context, and the serial controller shared with the input system
        # (same link carries pad colors down and switch states up; its
        # start/stop are refcounted, so each system runs the lifecycle
        # independently)
        light_kwargs = dict(self.context["light_system"])
        light_system = SystemSingletonFactory.LIGHT_SYSTEM_MAP[self.mode]
        if light_system is EmbeddedLightSystem:
            light_kwargs["dmx_controller"] = DmxController(**light_kwargs.pop("dmx_controller", {}))
        if isinstance(self._input_system, SwitchInputSystem):
            light_kwargs["serial_controller"] = self._input_system.serial_controller
        self._light_system = light_system(**light_kwargs)

        sound_system = SystemSingletonFactory.SOUND_SYSTEM_MAP[self.mode]
        self._sound_system = sound_system(**self.context["sound_system"])

    def get_light_system(self) -> LightSystem:
        return self._light_system

    def get_sound_system(self) -> SoundSystem:
        return self._sound_system

    def get_input_system(self) -> InputSystem:
        return self._input_system
