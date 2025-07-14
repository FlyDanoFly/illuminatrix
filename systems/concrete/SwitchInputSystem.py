import logging
# from enum import Flag, auto

import serial

from bases.InputSystem import InputSystem
# from components.Tower import Tower
from constants.constants import ControllerSwitchEnum, TowerEnum
# from utils.KBHit import KBHit

logger = logging.getLogger(__name__)


# class StompPad(Flag):
#     StompPad1 = auto()
#     StompPad2 = auto()
#     StompPad3 = auto()
#     StompPad4 = auto()
#     StompPad5 = auto()
#     StompPad6 = auto()
#     StompPad7 = auto()

TOWER_TO_BITMASK: dict[TowerEnum, int] = {
    tower_enum: 0b01 << (tower_enum.value - 1) for tower_enum in TowerEnum
}

SWITCH_TO_BITMASK: dict[ControllerSwitchEnum, int] = {
    controller_switch_enum : 0b01 << (controller_switch_enum.value - 1)
    for controller_switch_enum in ControllerSwitchEnum
}

# SWITCH_TO_TOWER_MAP: dict[StompPad, TowerEnum] = {
#     StompPad.StompPad1: TowerEnum.Tower_1,
#     StompPad.StompPad2: TowerEnum.Tower_2,
#     StompPad.StompPad3: TowerEnum.Tower_3,
#     StompPad.StompPad4: TowerEnum.Tower_4,
#     StompPad.StompPad5: TowerEnum.Tower_5,
#     StompPad.StompPad6: TowerEnum.Tower_6,
#     StompPad.StompPad7: TowerEnum.Tower_7,
# }

# TOWER_STR_TO_TOWER = {
#     str(TowerEnum.Tower_1.value): TowerEnum.Tower_1,
#     str(TowerEnum.Tower_2.value): TowerEnum.Tower_2,
#     str(TowerEnum.Tower_3.value): TowerEnum.Tower_3,
#     str(TowerEnum.Tower_4.value): TowerEnum.Tower_4,
#     str(TowerEnum.Tower_5.value): TowerEnum.Tower_5,
#     str(TowerEnum.Tower_6.value): TowerEnum.Tower_6,
#     str(TowerEnum.Tower_7.value): TowerEnum.Tower_7,
#
#     '\n': TowerEnum.Tower_4,
#     ' ': TowerEnum.Tower_4,
#     '\x1b': TowerEnum.Tower_4,
# }

# TOWER_KEYMAP = {
#     TowerEnum.Tower_1: str(TowerEnum.Tower_1.value),
#     TowerEnum.Tower_2: str(TowerEnum.Tower_2.value),
#     TowerEnum.Tower_3: str(TowerEnum.Tower_3.value),
#     TowerEnum.Tower_4: str(TowerEnum.Tower_4.value),
#     TowerEnum.Tower_5: str(TowerEnum.Tower_5.value),
#     TowerEnum.Tower_6: str(TowerEnum.Tower_6.value),
#     TowerEnum.Tower_7: str(TowerEnum.Tower_7.value),
# }
#
# CONTROLLER_KEYMAP = {
#     ControllerSwitchEnum.START: "\n",
#     ControllerSwitchEnum.NEXT_GAME: " ",
#     ControllerSwitchEnum.RESET: '\x1b',  # ESC
#     # ControllerSwitchEnum.NEXT_VARIATION: '\t',  # TAB
# }
#
FRAME_START_BYTE = 0xAA

def compute_crc8(data: bytes) -> int:
    crc = 0x00
    for byte in data:
        for _ in range(8):
            mix = (crc ^ byte) & 0x01
            crc >>= 1
            if mix:
                crc ^= 0x8C
            byte >>= 1
    return crc

def build_frame(rgb_data: list[int], control_leds: list[int]) -> bytes:
    if len(rgb_data) != 21 or len(control_leds) != 3:
        raise ValueError("RGB data must be 21 bytes and control LEDs must be 3 bytes")

    data = bytes(rgb_data + control_leds)
    crc = compute_crc8(data)
    return bytes([FRAME_START_BYTE]) + data + bytes([crc])


class SwitchInputSystem(InputSystem):
    def __init__(self, **_):
        # self._prev_switch_state: dict[str, bool] = {}
        # self._switch_state: dict[str, bool] = {}
        self._prev_switch_state: dict[TowerEnum | ControllerSwitchEnum, bool] = {}
        self._switch_state: dict[TowerEnum | ControllerSwitchEnum, bool] = {}

    def startup(self) -> None:
        self.serial = serial.Serial("/dev/ttyACM0", 115200, timeout=0.1)
        return super().startup()

    def shutdown(self) -> None:
        # TODO: shut down the pyserial connecntion
        return super().shutdown()

    def update(self, delta_secs: float) -> None: 
        lines = getattr(self, 'lines', 0)
        self._prev_switch_state = self._switch_state
        self._switch_state = {}
        # TODO: dummy stomp pad data to get the switch states
        rgb_data = [0,0,0] * 7
        control_leds = [0,0,0]
        frame = build_frame(rgb_data, control_leds)
        # print("Writing", frame)
        self.serial.write(frame)
        response = self.serial.read(2)
        # print(lines, "resp", response)
        if len(response) == 2:
            tower_switches = response[0]
            control_switches = response[1]
            for tower_enum, bitmask in TOWER_TO_BITMASK.items():
                if tower_switches & bitmask:
                    self._switch_state[tower_enum] = True
            for controller_enum, bitmask in SWITCH_TO_BITMASK.items():
                if control_switches & bitmask:
                    self._switch_state[controller_enum] = True
            # print(f"Towers: {bin(tower_switches)}, Controls: {bin(control_switches)}")
            lines += 1
        # print(self._switch_state)
        # print(self._switch_state)
        # for x in '1', '2', '3', '4', '5', '6', '7':
            # print("switch pressed", x, self.is_switch_pressed(x))

    def render(self) -> None:
        return super().render()

    def is_switch_pressed(self, switch: TowerEnum | ControllerSwitchEnum) -> bool:
        return self._switch_state.get(switch, False)

    def did_switch_transition_down(self, switch: TowerEnum | ControllerSwitchEnum) -> bool:
        return (
            not self._prev_switch_state.get(switch, False)
            and self._switch_state.get(switch, False)
        )

    def did_switch_transition_up(self, switch: TowerEnum | ControllerSwitchEnum) -> bool:
        return (
            self._prev_switch_state.get(switch, False)
            and not self._switch_state.get(switch, False)
        )

    def is_tower_switch_pressed(self, tower_enum: TowerEnum) -> bool:
        return self.is_switch_pressed(tower_enum)

    def did_tower_switch_transition_down(self, tower_enum: TowerEnum) -> bool:
        return self.did_switch_transition_down(tower_enum)

    def did_tower_switch_transition_up(self, tower_enum: TowerEnum) -> bool:
        return self.did_switch_transition_up(tower_enum)

    def is_controller_switch_pressed(self, controller_switch_enum: ControllerSwitchEnum) -> bool:
        return self.is_switch_pressed(controller_switch_enum)

    def did_controller_switch_transition_down(self, controller_switch_enum: ControllerSwitchEnum) -> bool:
        return self.did_switch_transition_down(controller_switch_enum)

    def did_controller_switch_transition_up(self, controller_switch_enum: ControllerSwitchEnum) -> bool:
        return self.did_switch_transition_up(controller_switch_enum)
