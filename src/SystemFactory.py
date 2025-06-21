# from DmxLightSystem import DmxLightSystem
from JackSoundSystem import JackSoundSystem
from constants import Environment
from LightSystem import LightSystem
from NullSoundSystem import NullSoundSystem
from PrintLightSystem import PrintLightSystem
from PrintSoundSystem import PrintSoundSystem
from SoundSystem import SoundSystem

# from WebRelayLightSystem import WebRelayLightSystem
from WebsocketSimulation import WebsocketSimulation


class SystemFactory:
    LIGHT_SYSTEM_MAP: dict[Environment, LightSystem] = {
        # Environment.EMBEDDED: DmxLightSystem,
        Environment.EXTERNAL: WebsocketSimulation,
        # Environment.LOCAL: WebRelayLightSystem,
        Environment.PRINT: PrintLightSystem,
    }
    SOUND_SYSTEM_MAP: dict[Environment, SoundSystem] = {
        Environment.EMBEDDED: PrintSoundSystem,
        Environment.EXTERNAL: JackSoundSystem,
        # Environment.EXTERNAL: PrintSoundSystem,
        Environment.LOCAL: PrintSoundSystem,
        Environment.PRINT: PrintSoundSystem,
    }

    _light_system: LightSystem
    _sound_system: SoundSystem

    def __init__(self, mode: Environment, context: dict | None=None):
        self.mode: Environment = mode
        self.context: dict = context or {} # optional shared context, e.g. websocket
        self._light_system = SystemFactory.LIGHT_SYSTEM_MAP[self.mode]()
        self._light_system.setup(**self.context)
        self._sound_system = SystemFactory.SOUND_SYSTEM_MAP[self.mode]()
        self._sound_system.load_sound_bank("../sound_bank_1")
        # self._sound_system.setup(**self.context)

    def get_light_system(self) -> LightSystem:
        return self._light_system

    def get_sound_system(self) -> SoundSystem:
        return self._sound_system
