from enum import Enum, Flag, StrEnum, auto


class IlluminatrixError(Exception):
    """Base class for Illuminatrix specific errors. (Better to use builtins, may remove this later)"""
    pass


# Color type is RGB or HSV agnostic
type ColorType = tuple[float, float, float]

# Type alias to clarify game update loop return type
type ShouldStop = bool | None


class TowerEnum(Enum):
    Tower_1 = auto()
    Tower_2 = auto()
    Tower_3 = auto()
    Tower_4 = auto()
    Tower_5 = auto()
    Tower_6 = auto()
    Tower_7 = auto()


class ControllerSwitchEnum(Enum):
    START = auto()
    NEXT_GAME = auto()
    RESET = auto()
    # NEXT_VARIATION = auto()  # If we decide to do variations


class LightPos(Flag):
    Tower_top = auto()
    Tower_bottom = auto()
    Pad_top = auto()
    Pad_bottom = auto()
    All = Tower_top | Tower_bottom | Pad_top | Pad_bottom


class Environment(StrEnum):
    EMBEDDED = auto()
    WEB = auto()
    PRINT = auto()


ENVIRONMENT_CONTEXT = {
    Environment.EMBEDDED: {
        "light_system": {
            # DmxController config; defaults live in dmx_controller.py.
            # Override here if needed, e.g.: {"universe": 1}
            "dmx_controller": {},
        },
        "sound_system": {},
        "input_system": {
            # SerialController config; defaults live in serial_controller.py.
            # Override here if the controller enumerates elsewhere, e.g.:
            # "serial_controller": {"serial_port": "/dev/ttyACM1"},
            "serial_controller": {},
        },
        "effect_system": {},
    },
    Environment.WEB: {
        "light_system": {
            "server_address": "wss://houseofsucky.xyz/illuminatrix_simulation_server",
            # "ack_style": "",  # not sure about the scope of this yet
        },
        "sound_system": {},
        "input_system": {},
        "effect_system": {},
    },
    Environment.PRINT: {
        "light_system": {},
        "sound_system": {},
        "input_system": {},
        "effect_system": {},
    },
}
