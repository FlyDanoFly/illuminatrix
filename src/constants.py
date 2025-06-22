from enum import Enum, Flag, StrEnum, auto


class IlluminatrixError(Exception):
    """Base class for Illuminatrix specific errors. (Better to use builtins, may remove this later)"""
    pass


type ColorType = tuple[float, float, float]
type SystemIdentifier = int


class TowerEnum(Enum):
    Tower_1 = auto()
    Tower_2 = auto()
    Tower_3 = auto()
    Tower_4 = auto()
    Tower_5 = auto()
    Tower_6 = auto()
    Tower_7 = auto()


class LightPos(Flag):
    Tower_top = auto()
    Tower_bottom = auto()
    Pad_top = auto()
    Pad_bottom = auto()
    All = Tower_top | Tower_bottom | Pad_top | Pad_bottom


tower_to_system_identifier: dict[TowerEnum, SystemIdentifier] = {
    TowerEnum.Tower_1: 0,
    TowerEnum.Tower_2: 1,
    TowerEnum.Tower_3: 2,
    TowerEnum.Tower_4: 3,
    TowerEnum.Tower_5: 4,
    TowerEnum.Tower_6: 5,
    TowerEnum.Tower_7: 6,
}

class Environment(StrEnum):
    EMBEDDED = auto()
    WEB = auto()
    PRINT = auto()


ENVIRONMENT_CONTEXT = {
    Environment.EMBEDDED: {},
    Environment.WEB: {
        "server_address": "wss://houseofsucky.xyz/illuminatrix_simulation_server",
        # "ack_style": "",  # not sure about the scope of this yet
    },
    Environment.PRINT: {},
}
