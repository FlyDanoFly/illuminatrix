"""Experiment (2026-07-03): drive stomp pad lights with a color cycle over serial.

This started life as a hacked copy of systems/concrete/SwitchInputSystem.py.
It sends a 7-second RGB triangle-wave cycle to the stomp pads every frame to
verify the controller passes light data through. If it works, the next step is
to formally hook stomp pad lighting into the light system (probably slaved to
the tower lights). Not wired into the game loop; preserved for reference.
"""

import logging
import time

import serial

from bases.InputSystem import InputSystem
from constants.constants import ControllerSwitchEnum, TowerEnum

logger = logging.getLogger(__name__)


TOWER_TO_BITMASK: dict[TowerEnum, int] = {
    tower_enum: 0b01 << (tower_enum.value - 1) for tower_enum in TowerEnum
}

SWITCH_TO_BITMASK: dict[ControllerSwitchEnum, int] = {
    controller_switch_enum : 0b01 << (controller_switch_enum.value - 1)
    for controller_switch_enum in ControllerSwitchEnum
}

SERIAL_FRAME_START_BYTE = 0xAA

# Dano 2026-07-03
#
# Quick test to see if the controller is working with the stomp pads
# This looks like it is sending RGB data to the stomp pad, but
# that it is always 0 because we hardcoded it due to time.
# Now the controller should be able to make the stomp pad lights
# be really nice, so I'm trying AI to make a quick color cycle
# to send every frame, and see if it goes through a color cycle.
# If this works, I need to formally hook up lighting to the stomp
# pads, probably for the start to slave them to the tower light.
def color_cycle(timestamp=None):
    """Return colors for 7 lights based on where `timestamp` falls in the cycle.

    The cycle is 7 seconds long. Each second is one phase in which a specific
    set of RGB channels ramps 0.0 -> 1.0 -> 0.0 (a triangle wave). After the
    seventh phase it wraps back to the start (red only).

    Returns a list of 7 items, each [red, green, blue] with values in [0.0, 1.0].
    On the first iteration all 7 items are identical.
    """
    # Which channels are active in each 1-second phase of the cycle.
    # Order: Red, Blue, Green, Red+Blue, Red+Green, Green+Blue, all three.
    # Each tuple is (red_on, green_on, blue_on).
    _PHASES = [
        (1, 0, 0),  # Red
        (0, 1, 0),  # Green
        (0, 0, 1),  # Blue
        (1, 1, 0),  # Red + Green
        (0, 1, 1),  # Green + Blue
        (1, 0, 1),  # Red + Blue
        (1, 1, 1),  # all three
    ]
    
    _CYCLE_SECONDS = len(_PHASES)  # 7

    if timestamp is None:
        timestamp = time.time()

    # xxyyzz = 10
    # i = int(timestamp) % xxyyzz
    # if i < xxyyzz / 2:
    #     print("on")
    #     return [[1.0, 1.0, 1.0],[1.0, 1.0, 1.0],[1.0, 1.0, 1.0],[1.0, 1.0, 1.0],[1.0, 1.0, 1.0],[1.0, 1.0, 1.0],[1.0, 1.0, 1.0],]
    # else:
    #     print("off")
    #     return [[0.5, 0.5, 0.5],[0.5, 0.5, 0.5],[0.5, 0.5, 0.5],[0.5, 0.5, 0.5],[0.5, 0.5, 0.5],[0.5, 0.5, 0.5],[0.5, 0.5, 0.5],]

    # Position within the 7-second cycle.
    pos = timestamp % _CYCLE_SECONDS
    phase = int(pos)
    frac = pos - phase  # 0.0 -> 1.0 within this phase

    # Triangle wave: 0 at frac=0, 1 at frac=0.5, 0 at frac=1.
    brightness = 1.0 - abs(2.0 * frac - 1.0)

    red_on, green_on, blue_on = _PHASES[phase]
    color = [red_on * brightness, green_on * brightness, blue_on * brightness]

    which_light = [0,1,2,3,4,5,6]
    return [list(color) if x in which_light else list((0,0,0)) for x in range(7)]

# Dano 2026-07-03
# Companion function to constrain converted ints to 0..255
def clamp(val, min_val, max_val):
    clamped_val = max(min_val, min(val, max_val))
    if clamped_val != val:
        logger.error("clamp prevented an overflow, val=%d, clamped_val=%d", val, clamped_val)
    return max(min_val, min(val, max_val))


def processed_color_cycle(timestamp: float=None) -> list[int]:
    rgb_data = color_cycle(timestamp)
    processed_rgb_data = [
        clamp(int(round(the_color * 255)), 0, 255) for y in rgb_data
        for the_color in y
    ]
    return processed_rgb_data


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

# Dano 2026-07-03 - See previous note, I'm hacking a bit to test the controller
# Original takes ints. I forget what the rest of the system uses, I haven't
# done the deep dive yet. I'm assuming it's all in [0.0-1.0] floats.
# That's what my test function above is anyways, so for now change
# this to accept a list of floats like so [[0.0,0.0,0.0], ...]
# and convert to ints 0-255.
def build_frame(rgb_data: list[float], control_leds: list[int]) -> bytes:
# def build_frame(rgb_data: list[int], control_leds: list[int]) -> bytes:
    if len(rgb_data) != 21 or len(control_leds) != 3:
        raise ValueError("RGB data must be 21 bytes and control LEDs must be 3 bytes")

    processed_rgb_data = [
        clamp(int(round(the_color * 255)), 0, 255)
        for the_color in rgb_data
    ]
    data = bytes(processed_rgb_data + control_leds)
    crc = compute_crc8(data)
    return bytes([SERIAL_FRAME_START_BYTE]) + data + bytes([crc])


class SwitchInputSystem(InputSystem):
    def __init__(self, **_):
        self._prev_switch_state: dict[TowerEnum | ControllerSwitchEnum, bool] = {}
        self._switch_state: dict[TowerEnum | ControllerSwitchEnum, bool] = {}

    def startup(self) -> None:
        self.serial = serial.Serial("/dev/ttyACM0", 115200, timeout=0.1)
        return super().startup()

    def shutdown(self) -> None:
        # TODO: shut down the pyserial connecntion
        self.serial.close()
        return super().shutdown()

    def update(self, delta_secs: float) -> None: 
        lines = getattr(self, 'lines', 0)
        self._prev_switch_state = self._switch_state
        self._switch_state = {}
        # TODO: dummy stomp pad data to get the switch states
        # Dano 2026-07-03 - again, just testing the control center for now
        rgb_data = [x for y in color_cycle() for x in y]
        # rgb_data = [0,0,0] * 7
        control_leds = [0,0,0]
        control_leds = [255,255,255]
        frame = build_frame(rgb_data, control_leds)
        print(f"frame (len={len(frame)}):", list(map(int, frame)))
        # print("Writing", frame)
        self.serial.write(frame)
        response = self.serial.read(2)
        print("responseA:", list(map(int, response)))
        # response = [0]
        if len(response) == 2:
            tower_switches = response[0]
            control_switches = response[1]
            for tower_enum, bitmask in TOWER_TO_BITMASK.items():
                if tower_switches & bitmask:
                    self._switch_state[tower_enum] = True
            for controller_enum, bitmask in SWITCH_TO_BITMASK.items():
                if control_switches & bitmask:
                    self._switch_state[controller_enum] = True
            lines += 1

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
