"""Serial transport to the switch/pad controller (the Arduino).

One physical peripheral serving two logical roles: a light sink (7 pad
RGBs + 3 control-LED bytes down) and an input source (switch bits up).
This module owns the wire — framing, CRC, reconnect, the post-connect
boot-quiet window, stale detection — and nothing game-facing. SwitchInputSystem reads switches through it;
EmbeddedLightSystem writes pad colors into it.

The transport rides the game loop as a system in its own right:
update() runs one exchange per frame (the request carries the staged
colors; whatever response has arrived is parsed and cached behind
pressed_switches). Because the loop and both sharing systems all manage
it, startup()/shutdown() are refcounted: the port is open exactly while
at least one of them is running.
"""

import logging
import os
import time

import serial

from bases.BaseSystem import BaseSystem
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
# Reads are non-blocking (we only consume in_waiting bytes); writes can
# block only if the OS buffers fill because the device stopped draining —
# the timeout turns that into a SerialException and the reconnect path
SERIAL_WRITE_TIMEOUT_SECS = 0.1
# Response frame: start byte + tower switches + control switches + CRC8
RESPONSE_FRAME_SIZE = 4
# Minimum time between attempts to (re)open the serial port
SERIAL_RECONNECT_INTERVAL_SECS = 1.0
# Opening the port DTR-resets the controller, and frames sent while it
# boots can land in its bootloader and wedge it — pads dark, switches
# dead, no error anywhere. Exchanges stay suppressed this long after
# every (re)connect
SERIAL_WARMUP_SECS = 2.0
# Poll cadence for wait_until_ready()
SERIAL_READY_POLL_SECS = 0.05
# After this long without a valid response the last known switch state is
# no longer trustworthy; consumers should treat switches as released
SERIAL_STALE_STATE_SECS = 2.0
# While disconnected, repeat an ERROR log at this interval so a dead
# controller is visible in the log stream, not just one line at startup
SERIAL_DISCONNECTED_LOG_INTERVAL_SECS = 30.0
# Pad colors ramp toward their targets instead of stepping: sound-reactive
# games can slam all 21 LED channels in one frame, and that load step on
# the pad controller board is suspected of glitching the switch sense
# lines into phantom presses (seen once on the bench, 2026-07-10). A full
# 0-255 swing takes this long; small changes still land in one frame
PAD_COLOR_SLEW_SECS = 0.25

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


class SerialController(BaseSystem):
    def __init__(self, serial_port: str = SERIAL_PORT, baudrate: int = SERIAL_BAUDRATE):
        self._port: str = serial_port
        self._baudrate: int = baudrate
        self._active_systems: int = 0
        self._latest_pressed: set[TowerEnum | ControllerSwitchEnum] | None = None
        self._serial: serial.Serial | None = None
        self._rx_buffer: bytearray = bytearray()
        self._connected_secs: float = float("-inf")
        self._last_connect_attempt_secs: float = float("-inf")
        self._last_valid_response_secs: float = float("-inf")
        self._last_disconnected_log_secs: float = float("-inf")
        # _pad_colors is what rides the wire; set_pad_color() writes
        # _pad_targets and update() slews the wire colors toward them
        self._pad_colors: dict[TowerEnum, tuple[int, int, int]] = {
            tower_enum: (0, 0, 0) for tower_enum in TowerEnum
        }
        self._pad_targets: dict[TowerEnum, tuple[int, int, int]] = {
            tower_enum: (0, 0, 0) for tower_enum in TowerEnum
        }
        self._control_leds: list[int] = [0, 0, 0]

    def startup(self) -> None:
        """Refcounted with shutdown(): the port opens on the first startup
        and closes on the last shutdown, so the game loop and both systems
        sharing the link can each run the lifecycle in any order."""
        self._active_systems += 1
        if self._active_systems > 1:
            return
        self._try_connect()
        if self._serial is None:
            logger.error("Could not open %s at startup, will keep retrying", self._port)

    def shutdown(self) -> None:
        if self._active_systems == 0:
            logger.warning("SerialController.shutdown() without a matching startup(), ignoring")
            return
        self._active_systems -= 1
        if self._active_systems == 0:
            self._disconnect()

    def update(self, delta_secs: float) -> None:
        """One frame of serial traffic, driven by the game loop like any
        other system — ordered before the others so anything reading
        pressed_switches later in the frame sees this frame's exchange."""
        if self._active_systems == 0:
            return
        self._slew_pad_colors(delta_secs)
        self._latest_pressed = self._exchange()

    def render(self) -> None:
        pass

    @property
    def pressed_switches(self) -> set[TowerEnum | ControllerSwitchEnum] | None:
        """The pressed set from the newest update()'s exchange, or None if
        it produced no valid response (or no exchange has happened yet)."""
        return self._latest_pressed

    def set_pad_color(self, tower_enum: TowerEnum, rgb: tuple[int, int, int]) -> None:
        """Set a pad's RGB target (0-255 per channel); the wire ramps
        toward it over PAD_COLOR_SLEW_SECS."""
        self._pad_targets[tower_enum] = (rgb[0], rgb[1], rgb[2])

    def _slew_pad_colors(self, delta_secs: float) -> None:
        """Move the wire colors toward their targets, bounded per frame —
        see PAD_COLOR_SLEW_SECS."""
        step = max(1, round(255 * delta_secs / PAD_COLOR_SLEW_SECS))
        for tower_enum, target in self._pad_targets.items():
            current = self._pad_colors[tower_enum]
            if current == target:
                continue
            self._pad_colors[tower_enum] = tuple(
                min(c + step, t) if t > c else max(c - step, t)
                for c, t in zip(current, target, strict=True)
            )

    def set_control_led(self, controller_switch_enum: ControllerSwitchEnum, brightness: int) -> None:
        """Queue a control-button LED brightness (0-255) for the next exchange."""
        self._control_leds[controller_switch_enum.value - 1] = brightness

    @property
    def is_ready(self) -> bool:
        """True once the port is open and the controller has had its
        boot-quiet window (SERIAL_WARMUP_SECS after connect). Until then
        update() exchanges nothing and switches read released, the same
        degrade as a brief disconnect."""
        return (
            self._serial is not None
            and time.monotonic() - self._connected_secs >= SERIAL_WARMUP_SECS
        )

    def wait_until_ready(self) -> None:
        """Block until is_ready, retrying the connection meanwhile — for
        bench scripts that must not start until the pads are live (a
        stomp check that began during the boot-quiet window would read
        as a dead pad). The game loop must never call this: it rides the
        degrade path through update() instead. ^C escapes; a missing
        controller repeats the usual disconnected ERROR while we wait."""
        while not self.is_ready:
            if self._serial is None:
                self._try_connect()
                if self._serial is None:
                    self._log_disconnected()
            time.sleep(SERIAL_READY_POLL_SECS)

    @property
    def is_stale(self) -> bool:
        """True when no valid response has arrived for long enough that the
        last known switch state is no longer trustworthy."""
        return time.monotonic() - self._last_valid_response_secs > SERIAL_STALE_STATE_SECS

    def _exchange(self) -> set[TowerEnum | ControllerSwitchEnum] | None:
        """One frame's worth of serial traffic: consume whatever response
        bytes have arrived, send the current colors, and return the set of
        pressed switches from the newest valid response — or None if no
        valid response landed this frame (disconnected, I/O error, silence,
        or corruption; reconnection is handled internally, rate-limited).
        """
        if self._serial is None:
            self._try_connect()
            if self._serial is None:
                self._log_disconnected()
                return None

        if not self.is_ready:
            # Boot-quiet window: the controller is still rebooting from
            # the DTR reset the open caused; see SERIAL_WARMUP_SECS
            return None

        rgb_data = [
            channel
            for tower_enum in TowerEnum
            for channel in self._pad_colors[tower_enum]
        ]
        request = build_frame(rgb_data, list(self._control_leds))
        try:
            # Non-blocking: consume whatever has arrived (normally last
            # frame's response — measured round trip is 4-11ms, well inside
            # a 33ms frame), then send this frame's request. The loop never
            # waits on the wire, so a silent device costs nothing.
            if self._serial.in_waiting:
                self._rx_buffer.extend(self._serial.read(self._serial.in_waiting))
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("recv %s", self._rx_buffer.hex())
                logger.debug("send %s", request.hex())
            self._serial.write(request)
        except (serial.SerialException, OSError) as e:
            logger.error("Serial I/O to %s failed, reconnecting: %s", self._port, e)
            self._disconnect()
            return None

        if len(self._rx_buffer) > 16 * RESPONSE_FRAME_SIZE:
            # A babbling device must not grow the buffer without bound
            del self._rx_buffer[:-RESPONSE_FRAME_SIZE]

        payload = extract_latest_response(self._rx_buffer)
        if payload is None:
            logger.debug("No valid switch response this frame")
            return None

        self._last_valid_response_secs = time.monotonic()
        pressed: set[TowerEnum | ControllerSwitchEnum] = set()
        tower_switches, control_switches, *_ = payload
        for tower_enum, bitmask in TOWER_TO_BITMASK.items():
            if tower_switches & bitmask:
                pressed.add(tower_enum)
        for controller_enum, bitmask in SWITCH_TO_BITMASK.items():
            if control_switches & bitmask:
                pressed.add(controller_enum)
        return pressed

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
                # The kernel allows concurrent opens, and two writers
                # interleave garbage the CRC silently eats (pads freeze,
                # switches go quiet). Fail the second claimant loudly
                # instead — e.g. a bench rig while play.py is running
                exclusive=True,
            )
            self._serial.reset_input_buffer()
            self._rx_buffer.clear()
            # Starts the boot-quiet window: the open just DTR-reset the
            # controller, so exchanges hold off while it boots
            self._connected_secs = time.monotonic()
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
