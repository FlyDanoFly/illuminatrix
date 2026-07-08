from bases.BaseSystem import BaseSystem
from bases.InputSystem import InputSystem
from bases.LightSystem import LightSystem
from bases.SoundSystem import SoundSystem
from constants.constants import Environment
from systems.concrete.dmx_controller import DmxController
from systems.concrete.EmbeddedLightSystem import EmbeddedLightSystem
from systems.concrete.JackSoundSystem import JackMixer, JackSoundSystem
from systems.concrete.KeyboardInputSystem import KeyboardInputSystem
from systems.concrete.PrintLightSystem import PrintLightSystem
from systems.concrete.PrintSoundSystem import PrintSoundSystem
from systems.concrete.serial_controller import SerialController
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
        # Keys 1-7 are the towers; enter/space/esc the controller buttons.
        # Degrades to no input when stdin is not a TTY
        Environment.PRINT: KeyboardInputSystem,
    }

    _light_system: LightSystem
    _sound_system: SoundSystem
    _input_system: InputSystem
    _active_systems: list[BaseSystem]

    def __init__(
            self,
            mode: Environment,
            context: dict,
            sound_system_override: type[SoundSystem] | None = None,
    ):
        self.mode: Environment = mode
        self.context: dict = context or {}

        # The embedded controllers are constructed here, not by the
        # systems, each from its config dict in the context. The serial
        # controller is one instance serving two systems (the same link
        # carries pad colors down and switch states up); its lifecycle is
        # refcounted, so every holder runs startup/shutdown independently
        serial_controller: SerialController | None = None

        input_kwargs = dict(self.context["input_system"])
        input_system = SystemSingletonFactory.INPUT_SYSTEM_MAP[self.mode]
        if input_system is SwitchInputSystem:
            serial_controller = SerialController(**input_kwargs.pop("serial_controller", {}))
            input_kwargs["serial_controller"] = serial_controller
        self._input_system = input_system(**input_kwargs)

        light_kwargs = dict(self.context["light_system"])
        light_system = SystemSingletonFactory.LIGHT_SYSTEM_MAP[self.mode]
        if light_system is EmbeddedLightSystem:
            light_kwargs["dmx_controller"] = DmxController(**light_kwargs.pop("dmx_controller", {}))
            light_kwargs["serial_controller"] = serial_controller
        self._light_system = light_system(**light_kwargs)

        sound_kwargs = dict(self.context["sound_system"])
        sound_system = sound_system_override or SystemSingletonFactory.SOUND_SYSTEM_MAP[self.mode]
        # Popped unconditionally: the mixer config is JACK transport
        # detail, meaningless to an overridden (e.g. --no-sound) system
        mixer_config = sound_kwargs.pop("mixer", {})
        if sound_system is JackSoundSystem:
            sound_kwargs["mixer"] = JackMixer(**mixer_config)
        self._sound_system = sound_system(**sound_kwargs)

        # Everything the game loop drives each frame, in update order.
        # The serial transport goes first: its exchange sends the colors
        # the game/effect updates just staged and caches the switch
        # response, so the input system reading pressed_switches later
        # this frame sees this frame's exchange
        self._active_systems = []
        if serial_controller is not None:
            self._active_systems.append(serial_controller)
        self._active_systems += [
            self._light_system,
            self._sound_system,
            self._input_system,
        ]

    def get_active_systems(self) -> list[BaseSystem]:
        """Every per-frame participant in loop order: the three systems
        plus any transports that ride the loop."""
        return list(self._active_systems)

    def get_light_system(self) -> LightSystem:
        return self._light_system

    def get_sound_system(self) -> SoundSystem:
        return self._sound_system

    def get_input_system(self) -> InputSystem:
        return self._input_system
