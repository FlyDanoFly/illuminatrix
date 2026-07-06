import logging
import os
import time

import serial

from bases.InputSystem import InputSystem
from constants.constants import ControllerSwitchEnum, TowerEnum
from experiments.stomp_pad_color_cycle import processed_color_cycle

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
# Reads are non-blocking (we only consume in_waiting bytes); writes can
# block only if the OS buffers fill because the device stopped draining —
# the timeout turns that into a SerialException and the reconnect path
SERIAL_WRITE_TIMEOUT_SECS = 0.1
# Response frame: start byte + tower switches + control switches + CRC8
RESPONSE_FRAME_SIZE = 4
# Minimum time between attempts to (re)open the serial port
SERIAL_RECONNECT_INTERVAL_SECS = 1.0
# After this long without a valid response, report all switches released
# (until then the last known state is held, so a brief glitch doesn't
# fire phantom press/release transitions)
SERIAL_STALE_STATE_SECS = 2.0
# While disconnected, repeat an ERROR log at this interval so a dead
# controller is visible in the log stream, not just one line at startup
SERIAL_DISCONNECTED_LOG_INTERVAL_SECS = 30.0

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


def extract_latest_response(buffer: bytearray) -> tuple[int, ...] | None:
    """Consume every complete, CRC-valid response frame in the buffer and
    return the newest (tower_switches, control_switches), or None if no
    complete valid frame is present yet.

    Garbage and corrupt frames are discarded byte-by-byte (a false start
    byte fails CRC and resyncs); an incomplete frame at the tail is left
    in place for a later read to finish.
    """
    latest: tuple[int, ...] | None = None
    while True:
        start = buffer.find(SERIAL_FRAME_START_BYTE)
        if start == -1:
            buffer.clear()
            return latest
        if start:
            del buffer[:start]
        if len(buffer) < RESPONSE_FRAME_SIZE:
            return latest
        payload = bytes(buffer[1:RESPONSE_FRAME_SIZE-1])
        if compute_crc8(payload) == buffer[RESPONSE_FRAME_SIZE-1]:
            latest = tuple(payload[:RESPONSE_FRAME_SIZE-1])
            del buffer[:RESPONSE_FRAME_SIZE]
        else:
            del buffer[:1]


class SwitchInputSystem(InputSystem):
    def __init__(self, serial_port: str = SERIAL_PORT, baudrate: int = SERIAL_BAUDRATE, **_):
        self._port: str = serial_port
        self._baudrate: int = baudrate
        self._prev_switch_state: dict[TowerEnum | ControllerSwitchEnum, bool] = {}
        self._switch_state: dict[TowerEnum | ControllerSwitchEnum, bool] = {}
        self._serial: serial.Serial | None = None
        self._rx_buffer: bytearray = bytearray()
        self._last_connect_attempt_secs: float = float("-inf")
        self._last_valid_response_secs: float = float("-inf")
        self._last_disconnected_log_secs: float = float("-inf")
        self._state_was_cleared: bool = False

    def startup(self) -> None:
        self._try_connect()
        if self._serial is None:
            logger.error("Could not open %s at startup, will keep retrying", self._port)
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
        # Missing device is the common failure and stat() is near-free;
        # serial.Serial() against a mid-enumeration USB device can block
        # the frame loop for hundreds of ms
        if not os.path.exists(self._port):
            logger.debug("Serial port %s not present", self._port)
            return
        try:
            self._serial = serial.Serial(
                self._port,
                self._baudrate,
                timeout=0,  # non-blocking reads; we only consume in_waiting bytes
                write_timeout=SERIAL_WRITE_TIMEOUT_SECS,
            )
            self._serial.reset_input_buffer()
            self._rx_buffer.clear()
            # Reset so a future outage logs immediately again
            self._last_disconnected_log_secs = float("-inf")
            logger.info("Serial connection to %s established", self._port)
        except (serial.SerialException, OSError) as e:
            self._serial = None
            logger.debug("Serial connect attempt to %s failed: %s", self._port, e)

    def _log_disconnected(self) -> None:
        """Repeat an ERROR while the controller is missing — a dead input
        system otherwise looks like a healthy idle installation."""
        now = time.monotonic()
        if now - self._last_disconnected_log_secs < SERIAL_DISCONNECTED_LOG_INTERVAL_SECS:
            return
        self._last_disconnected_log_secs = now
        logger.error(
            "Switch controller %s unavailable — all switches read released until it returns",
            self._port,
        )

    def _disconnect(self) -> None:
        self._rx_buffer.clear()
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
        without reporting a release transition, and _state_was_cleared
        makes the first response after recovery transition-free too (a
        switch held across the whole outage must not register as a fresh
        press).
        """
        if time.monotonic() - self._last_valid_response_secs > SERIAL_STALE_STATE_SECS:
            self._prev_switch_state = {}
            self._switch_state = {}
            self._state_was_cleared = True
        else:
            # Hold the last known state. Explicit copy: update() aliased
            # prev and current to the same dict, and equal-but-distinct
            # objects keep a future in-place mutation from corrupting both
            self._switch_state = dict(self._prev_switch_state)

    def update(self, delta_secs: float) -> None:
        self._prev_switch_state = self._switch_state

        if self._serial is None:
            self._try_connect()
            if self._serial is None:
                self._log_disconnected()
                self._handle_missed_response()
                return

        # TODO: dummy stomp pad data to get the switch states
        rgb_data = processed_color_cycle()
        # rgb_data = [0,0,0] * 7
        control_leds = [0,0,0]
        request = build_frame(rgb_data, control_leds)
        try:
            # Non-blocking: consume whatever has arrived (normally last
            # frame's response — measured round trip is 4-11ms, well inside
            # a 33ms frame), then send this frame's request. The loop never
            # waits on the wire, so a silent device costs nothing.
            if self._serial.in_waiting:
                self._rx_buffer.extend(self._serial.read(self._serial.in_waiting))
            logger.debug("recv %s", self._rx_buffer.hex())
            logger.debug("send %s", request.hex())
            self._serial.write(request)
        except (serial.SerialException, OSError) as e:
            logger.error("Serial I/O to %s failed, reconnecting: %s", self._port, e)
            self._disconnect()
            self._handle_missed_response()
            return

        if len(self._rx_buffer) > 16 * RESPONSE_FRAME_SIZE:
            # A babbling device must not grow the buffer without bound
            del self._rx_buffer[:-RESPONSE_FRAME_SIZE]

        payload = extract_latest_response(self._rx_buffer)
        if payload is None:
            logger.debug("No valid switch response this frame, keeping previous switch state")
            self._handle_missed_response()
            return

        self._last_valid_response_secs = time.monotonic()
        new_state: dict[TowerEnum | ControllerSwitchEnum, bool] = {}
        tower_switches, control_switches, *_ = payload
        for tower_enum, bitmask in TOWER_TO_BITMASK.items():
            if tower_switches & bitmask:
                new_state[tower_enum] = True
        for controller_enum, bitmask in SWITCH_TO_BITMASK.items():
            if control_switches & bitmask:
                new_state[controller_enum] = True
        if self._state_was_cleared:
            # First response after an outage cleared the state: a switch
            # held across the whole outage is not a fresh press
            self._prev_switch_state = dict(new_state)
            self._state_was_cleared = False
        self._switch_state = new_state

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
