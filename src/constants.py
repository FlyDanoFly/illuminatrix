from enum import Enum, Flag, auto, StrEnum


class IlluminatrixError(Exception):
    """Base class for Illuminatrix specific errors. (Better to use builtins, may remove this later)"""
    pass


type ColorType = tuple[float, float, float] # | list[float]
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
    EXTERNAL = auto()
    LOCAL = auto()
    PRINT = auto()


ENVIRONMENT_CONTEXT = {
    Environment.EMBEDDED: {},
    Environment.EXTERNAL: {
        "server_url": "wss://houseofsucky.xyz/illuminatrix_simulation_server",
        # "ack_style": "",  # not sure about the scope of this yet
    },
    Environment.LOCAL: {
        "server_url": "ws://localhost:8000"
        # "ack_style": "",  # not sure about the scope of this yet
    },
    Environment.PRINT: {},
}


## Brainstorm, 10 minutes no solutions

# Tower interface
# class Tower:
#     # This gets passed controllers and how this tower identifies itself
#     def __init__(self): pass
#
#     def set_color(self, color): pass
#     def set_tower_color(self, color): pass
#     def set_pad_color(self, color): pass
#     def set_tower_top_color(self, color): pass
#     def set_tower_bottom_color(self, color): pass
#     def set_pad_top_color(self, color): pass
#     def set_pad_bottom_color(self, color): pass
#     def play_sound(self, color): pass
#     def is_pressed(self): pass
#     # or
#     def set_color(self, part, color): pass
#     # where part is a bit enum: all, tower, tower_top, tower_bottom, etc

# No enums at all
# clss TowerController:
#     # same as above, performs the action on all towers
#     def set_color(self, part, color)
#     # add one-indexed stuff here
#
#     # What should it accept? Integeras and enums?
#     # Trying for both
#     def __getitem__(self, idx: Tower | int):
#         if isinstance(idx, Tower):
#             idx = idx.value - 1
#         elif self.one_indexed:
#             idx += 1
#         return self.towers[idx]

# TODO: NOT IMPLEMENTED YET
# What is the world where systems use tower enums?
# class WebLightSystem:
#     accumulate_dict: {} # {Tower_1: color}
#     def update(self):
        # Turn accumulate_dict into a message and send the message
        # Does this interact directly with the websocket? probably yes?
        # the ide is the subsystems get .updates but towers do now
        # if tower is an enum, translate the tower to the int that is sent across the wire
        # for subsystem it is zero-inedxed int for tower number
        # do we need a level of indirection?
        # Never call the subsystem from game code
        # If always numbers in a subsystem you can build the message and not need to re-translate it
        # Build an opaque identifier for the Tower, just pass the opaque identifier to the subsystem and it will direct appropriately
        # opaque identifier is actually an int but the towers don't have to know that
        # OK, I'm liking it
        # all systems have the same scheme, 0 means tower 0 for all usbsystems
        # and I really really hope that it will always go clockwise from there
        # it would be great if we can set it when we build it
        # I suppose we can alter which is 0 in the seftware if needed
        # The remapping is not too processor intensive, probably an addition and mod
        # OK

    # Systems deal with towers as ints
    # Hong on, how's the picup?
    # How about Tower.Tower_1 = 1
    # Do this explicitly because we'd need a translation
    # self.towers = [
    # Tower(identifier, light_system, sound_system, input_system)
    # for identifier in Towers]

    # or tower_to_system_identifier{Tower.Towewr_1: 0}
    # This would allow the enum to be auto()
    # Put in the base class?
    # It would need to be in the system base class??
    # self.tower = Tower.tower_1
    # self.system_indentifier = light_system_tower_to_identifier[self.tower]
    # def set_color: self.light_system.set_color(self.system_identifier, color)
    
