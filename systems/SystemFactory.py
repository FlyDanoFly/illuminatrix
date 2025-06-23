# from DmxLightSystem import DmxLightSystem
from typing import Type

from bases.InputSystem import InputSystem
from bases.LightSystem import LightSystem
from bases.SoundSystem import SoundSystem
from constants.constants import Environment
from systems.concrete.JackSoundSystem import JackSoundSystem
from systems.concrete.KeyboardInputSystem import KeyboardInputSystem
from systems.concrete.PrintInputSystem import PrintInputSystem
from systems.concrete.PrintLightSystem import PrintLightSystem
from systems.concrete.PrintSoundSystem import PrintSoundSystem
from systems.concrete.WebsocketSimulation import WebsocketSimulation


class SystemFactory:
    LIGHT_SYSTEM_MAP: dict[Environment, LightSystem] = {
        # Environment.EMBEDDED: DmxLightSystem,
        Environment.WEB: WebsocketSimulation,
        Environment.PRINT: PrintLightSystem,
    }
    SOUND_SYSTEM_MAP: dict[Environment, SoundSystem] = {
        # Environment.EMBEDDED: PrintSoundSystem,
        Environment.WEB: JackSoundSystem,
        Environment.PRINT: PrintSoundSystem,
    }
    INPUT_SYSTEM_MAP: dict[Environment, Type[InputSystem]] = {
        # Environment.EMBEDDED: PrintInputSystem,
        Environment.WEB: KeyboardInputSystem,
        Environment.PRINT: PrintInputSystem,
    }

    _light_system: LightSystem
    _sound_system: SoundSystem
    _input_system: InputSystem

    def __init__(self, mode: Environment, context: dict | None=None):
        self.mode: Environment = mode
        self.context: dict = context or {} # optional shared context, e.g. websocket
        self._light_system = SystemFactory.LIGHT_SYSTEM_MAP[self.mode]()
        self._light_system.setup(**self.context)
        self._sound_system = SystemFactory.SOUND_SYSTEM_MAP[self.mode]()
        # TODO: move the sound bank loading to the game code
        self._sound_system.load_sound_bank("sound_banks/lucy_whack_a_mole_1/")
        # self._sound_system.setup(**self.context)
        # TODO: 
        self._input_system = SystemFactory.INPUT_SYSTEM_MAP[self.mode](7)

    def get_light_system(self) -> LightSystem:
        return self._light_system

    def get_sound_system(self) -> SoundSystem:
        return self._sound_system

    def get_input_system(self) -> InputSystem:
        return self._input_system
