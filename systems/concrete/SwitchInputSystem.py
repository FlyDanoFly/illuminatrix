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

SERIAL_PORT = "/dev/ttyACM0"
SERIAL_BAUDRATE = 115200
SERIAL_TIMEOUT_SECS = 0.1
# Minimum time between attempts to (re)open the serial port
SERIAL_RECONNECT_INTERVAL_SECS = 1.0
# After this long without a valid response, report all switches released
# (until then the last known state is held, so a brief glitch doesn't
# fire phantom press/release transitions)
SERIAL_STALE_STATE_SECS = 2.0

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
    return bytes([SERIAL_FRAME_START_BYTE]) + data + bytes([crc])


class SwitchInputSystem(InputSystem):
    def __init__(self, **_):
        self._prev_switch_state: dict[TowerEnum | ControllerSwitchEnum, bool] = {}
        self._switch_state: dict[TowerEnum | ControllerSwitchEnum, bool] = {}
        self._serial: serial.Serial | None = None
        self._last_connect_attempt_secs: float = float("-inf")
        self._last_valid_response_secs: float = float("-inf")

    def startup(self) -> None:
        self._try_connect()
        if self._serial is None:
            logger.error("Could not open %s at startup, will keep retrying", SERIAL_PORT)
        return super().startup()

    def shutdown(self) -> None:
        # Gracefully shut down the pyserial connecntion
        self._disconnect()
        return super().shutdown()

    def _try_connect(self) -> None:
        """(Re)open the serial port, rate limited so a dead port doesn't spam."""
        now = time.monotonic()
        if now - self._last_connect_attempt_secs < SERIAL_RECONNECT_INTERVAL_SECS:
            return
        self._last_connect_attempt_secs = now
        try:
            self._serial = serial.Serial(SERIAL_PORT, SERIAL_BAUDRATE, timeout=SERIAL_TIMEOUT_SECS)
            self._serial.reset_input_buffer()
            logger.info("Serial connection to %s established", SERIAL_PORT)
        except (serial.SerialException, OSError) as e:
            self._serial = None
            logger.debug("Serial connect attempt to %s failed: %s", SERIAL_PORT, e)

    def _disconnect(self) -> None:
        if self._serial is None:
            return
        try:
            self._serial.close()
        except (serial.SerialException, OSError):
            pass
        self._serial = None

    def _handle_missed_response(self) -> None:
        """Keep switch state sane across a frame with no valid response.

        For a brief glitch, hold the last known state so no phantom
        press/release transitions fire. If the outage persists, clear both
        current and previous state together: switches read as released
        without ever reporting a transition.
        """
        if time.monotonic() - self._last_valid_response_secs > SERIAL_STALE_STATE_SECS:
            self._prev_switch_state = {}
            self._switch_state = {}
        else:
            self._switch_state = self._prev_switch_state

    def update(self, delta_secs: float) -> None:
        self._prev_switch_state = self._switch_state

        if self._serial is None:
            self._try_connect()
            if self._serial is None:
                self._handle_missed_response()
                return

        # TODO: dummy stomp pad data to get the switch states
        rgb_data = [0,0,0] * 7
        control_leds = [0,0,0]
        frame = build_frame(rgb_data, control_leds)
        try:
            # Flush anything stale (e.g. a late response from before a
            # reconnect) so the 2 bytes we read belong to this request
            self._serial.reset_input_buffer()
            self._serial.write(frame)
            response = self._serial.read(2)
        except (serial.SerialException, OSError) as e:
            logger.error("Serial I/O to %s failed, reconnecting: %s", SERIAL_PORT, e)
            self._disconnect()
            self._handle_missed_response()
            return

        if len(response) != 2:
            logger.debug("Short serial response (%d bytes), keeping previous switch state", len(response))
            self._handle_missed_response()
            return

        self._last_valid_response_secs = time.monotonic()
        self._switch_state = {}
        tower_switches = response[0]
        control_switches = response[1]
        for tower_enum, bitmask in TOWER_TO_BITMASK.items():
            if tower_switches & bitmask:
                self._switch_state[tower_enum] = True
        for controller_enum, bitmask in SWITCH_TO_BITMASK.items():
            if control_switches & bitmask:
                self._switch_state[controller_enum] = True

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
