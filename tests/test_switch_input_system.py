"""Tests for SwitchInputSystem: protocol framing and fault handling.

Runs two ways, no hardware needed (serial is replaced with a fake):

    poetry run pytest tests/
    poetry run python tests/test_switch_input_system.py
"""

import sys
import time
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import serial as pyserial  # noqa: E402

import systems.concrete.stomp_pad_controller as spc_mod  # noqa: E402
from constants.constants import ControllerSwitchEnum, TowerEnum  # noqa: E402
from systems.concrete.stomp_pad_controller import (  # noqa: E402
    SERIAL_FRAME_START_BYTE,
    build_frame,
    compute_crc8,
    extract_latest_response,
)
from systems.concrete.SwitchInputSystem import SwitchInputSystem  # noqa: E402

DT = 0.033  # one 30fps frame


def framed(tower: int, control: int) -> bytes:
    """A valid controller response frame."""
    payload = bytes([tower, control])
    return bytes([SERIAL_FRAME_START_BYTE]) + payload + bytes([compute_crc8(payload)])


class FakeSerial:
    """Byte pipe standing in for the controller: feed() queues response
    bytes, the system under test drains them via in_waiting/read."""

    def __init__(self):
        self.rx = bytearray()
        self.write_count = 0
        self.last_written = b""
        self.fail_next_write = False

    @property
    def in_waiting(self):
        return len(self.rx)

    def feed(self, data: bytes):
        self.rx.extend(data)

    def read(self, n):
        data = bytes(self.rx[:n])
        del self.rx[:n]
        return data

    def write(self, frame):
        assert len(frame) == 26, f"request should be 26 bytes, got {len(frame)}"
        if self.fail_next_write:
            self.fail_next_write = False
            raise pyserial.SerialException("simulated cable yank")
        self.write_count += 1
        self.last_written = bytes(frame)

    def reset_input_buffer(self):
        self.rx.clear()

    def close(self):
        pass


def make_system() -> tuple[SwitchInputSystem, FakeSerial]:
    """A connected system with a fresh fake port. Patches only the controller
    module's view of pyserial; /dev/null satisfies the os.path.exists gate."""
    fake = FakeSerial()
    spc_mod.serial = types.SimpleNamespace(
        Serial=lambda *a, **k: fake,
        SerialException=pyserial.SerialException,
    )
    system = SwitchInputSystem(serial_port="/dev/null")
    system.startup()
    assert system.stomp_pads._serial is fake
    return system, fake


def make_settled_system() -> tuple[SwitchInputSystem, FakeSerial]:
    """A system past first contact: baseline all-released state established,
    so the startup press-suppression rule is out of the way."""
    system, fake = make_system()
    system.update(DT)  # first request goes out, nothing to read yet
    fake.feed(framed(0, 0))
    system.update(DT)
    assert not system.is_tower_switch_pressed(TowerEnum.Tower_1)
    return system, fake


# ---------------------------------------------------------------------------
# Request frame / CRC

def test_build_frame_shape():
    frame = build_frame([0, 0, 0] * 7, [0, 0, 0])
    assert len(frame) == 26
    assert frame[0] == SERIAL_FRAME_START_BYTE
    assert frame[25] == compute_crc8(frame[1:25])


def test_build_frame_rejects_wrong_lengths():
    for rgb, leds in [([0] * 20, [0] * 3), ([0] * 21, [0] * 2)]:
        try:
            build_frame(rgb, leds)
            raise AssertionError("expected ValueError")
        except ValueError:
            pass


# ---------------------------------------------------------------------------
# Response parser (pure function)

def test_parser_valid_frame():
    buf = bytearray(framed(0b1, 0b1))
    assert extract_latest_response(buf) == (1, 1)
    assert not buf


def test_parser_skips_garbage_prefix():
    buf = bytearray(b"\x00\x37" + framed(0b10, 0))
    assert extract_latest_response(buf) == (2, 0)
    assert not buf


def test_parser_keeps_partial_frame_for_later():
    resp = framed(0b1, 0)
    buf = bytearray(resp[:2])
    assert extract_latest_response(buf) is None
    assert len(buf) == 2, "partial frame must be kept"
    buf.extend(resp[2:])
    assert extract_latest_response(buf) == (1, 0)


def test_parser_discards_corrupt_frame_and_resyncs():
    corrupt = bytearray(framed(0b1, 0))
    corrupt[3] ^= 0xFF
    buf = bytearray(bytes(corrupt) + framed(0b11, 0b1))
    assert extract_latest_response(buf) == (3, 1)
    assert not buf


def test_parser_newest_of_multiple_frames_wins():
    buf = bytearray(framed(0b1, 0) + framed(0b100, 0))
    assert extract_latest_response(buf) == (4, 0)


# ---------------------------------------------------------------------------
# System behavior

def test_first_contact_suppresses_already_held_switch():
    # A pad already held when the program first hears from the controller
    # (startup, or recovery after an outage) must not register as a press
    system, fake = make_system()
    system.update(DT)
    fake.feed(framed(0b1, 0))
    system.update(DT)
    assert system.is_tower_switch_pressed(TowerEnum.Tower_1)
    assert not system.did_tower_switch_transition_down(TowerEnum.Tower_1)


def test_press_and_release_transitions():
    system, fake = make_settled_system()
    fake.feed(framed(0b1, 0b001))
    system.update(DT)
    assert system.is_tower_switch_pressed(TowerEnum.Tower_1)
    assert system.did_tower_switch_transition_down(TowerEnum.Tower_1)
    assert system.is_controller_switch_pressed(ControllerSwitchEnum.START)
    fake.feed(framed(0, 0))
    system.update(DT)
    assert system.did_tower_switch_transition_up(TowerEnum.Tower_1)
    assert system.did_controller_switch_transition_up(ControllerSwitchEnum.START)


def test_missed_response_holds_state_and_keeps_requesting():
    system, fake = make_settled_system()
    fake.feed(framed(0b1, 0))
    system.update(DT)
    writes_before = fake.write_count
    system.update(DT)  # nothing on the wire this frame
    assert fake.write_count == writes_before + 1, "requests keep flowing during a miss"
    assert system.is_tower_switch_pressed(TowerEnum.Tower_1), "state held"
    assert not system.did_tower_switch_transition_down(TowerEnum.Tower_1)
    assert not system.did_tower_switch_transition_up(TowerEnum.Tower_1)


def test_corrupt_response_holds_state():
    system, fake = make_settled_system()
    fake.feed(framed(0b1, 0))
    system.update(DT)
    bad = bytearray(framed(0, 0))
    bad[3] ^= 0xFF
    fake.feed(bytes(bad))
    system.update(DT)
    assert system.is_tower_switch_pressed(TowerEnum.Tower_1), "corrupt frame must not change state"


def test_split_frame_reassembled_across_updates():
    system, fake = make_settled_system()
    resp = framed(0b1, 0)
    fake.feed(resp[:2])
    system.update(DT)
    assert not system.is_tower_switch_pressed(TowerEnum.Tower_1), "not parsed yet"
    fake.feed(resp[2:])
    system.update(DT)
    assert system.is_tower_switch_pressed(TowerEnum.Tower_1)
    assert system.did_tower_switch_transition_down(TowerEnum.Tower_1), "single press event"


def test_response_burst_resolves_to_newest():
    system, fake = make_settled_system()
    fake.feed(framed(0b1, 0) + framed(0b10, 0))
    system.update(DT)
    assert system.is_tower_switch_pressed(TowerEnum.Tower_2)
    assert not system.is_tower_switch_pressed(TowerEnum.Tower_1)


def test_stale_clear_is_transition_free_and_recovery_suppressed():
    system, fake = make_settled_system()
    fake.feed(framed(0b1, 0))
    system.update(DT)
    # Prolonged outage: no data past the stale threshold
    system.stomp_pads._last_valid_response_secs = time.monotonic() - (spc_mod.SERIAL_STALE_STATE_SECS + 1)
    system.update(DT)
    assert not system.is_tower_switch_pressed(TowerEnum.Tower_1), "stale state cleared"
    assert not system.did_tower_switch_transition_up(TowerEnum.Tower_1), "clear fires no transitions"
    # Recovery while the pad is still physically held: no phantom press...
    fake.feed(framed(0b1, 0))
    system.update(DT)
    assert system.is_tower_switch_pressed(TowerEnum.Tower_1)
    assert not system.did_tower_switch_transition_down(TowerEnum.Tower_1)
    # ...but genuine release + press transition normally afterwards
    fake.feed(framed(0, 0))
    system.update(DT)
    assert system.did_tower_switch_transition_up(TowerEnum.Tower_1)
    fake.feed(framed(0b1, 0))
    system.update(DT)
    assert system.did_tower_switch_transition_down(TowerEnum.Tower_1)


def test_io_error_reconnects_rate_limited():
    system, fake = make_settled_system()
    fake.rx.extend(b"\xaa\x01")  # leftover partial garbage from dying link
    fake.fail_next_write = True
    system.update(DT)
    assert system.stomp_pads._serial is None, "disconnected after I/O error"
    assert not system.stomp_pads._rx_buffer, "software rx buffer cleared on disconnect"
    system.update(DT)
    assert system.stomp_pads._serial is None, "reconnect is rate-limited"
    system.stomp_pads._last_connect_attempt_secs = time.monotonic() - (spc_mod.SERIAL_RECONNECT_INTERVAL_SECS + 1)
    fake.rx.clear()
    system.update(DT)  # reconnects and sends a request
    assert system.stomp_pads._serial is fake
    fake.feed(framed(0b10, 0))
    system.update(DT)
    assert system.is_tower_switch_pressed(TowerEnum.Tower_2)


def test_rx_buffer_capped_under_babble():
    system, fake = make_settled_system()
    fake.feed(b"\x55" * 500)
    system.update(DT)
    assert len(system.stomp_pads._rx_buffer) <= 16 * spc_mod.RESPONSE_FRAME_SIZE


def test_missing_port_degrades_gracefully():
    system = SwitchInputSystem(serial_port="/dev/definitely_not_a_port")
    system.startup()
    assert system.stomp_pads._serial is None
    system.update(DT)  # must not raise
    assert not system.is_tower_switch_pressed(TowerEnum.Tower_1)


# ---------------------------------------------------------------------------
# Pad colors and control LEDs (light sink side of the link)

def test_pad_colors_default_to_black():
    system, fake = make_settled_system()
    assert fake.last_written[1:22] == bytes(21)


def test_pad_color_rides_the_next_request_frame():
    system, fake = make_settled_system()
    system.stomp_pads.set_pad_color(TowerEnum.Tower_1, (255, 0, 7))
    system.stomp_pads.set_pad_color(TowerEnum.Tower_7, (1, 2, 3))
    system.update(DT)
    frame = fake.last_written
    assert frame[1:4] == bytes([255, 0, 7]), "Tower_1 RGB leads the payload"
    assert frame[19:22] == bytes([1, 2, 3]), "Tower_7 RGB ends the pad block"
    assert frame[25] == compute_crc8(frame[1:25]), "CRC covers the new colors"


def test_control_led_rides_the_next_request_frame():
    system, fake = make_settled_system()
    system.stomp_pads.set_control_led(ControllerSwitchEnum.START, 200)
    system.update(DT)
    frame = fake.last_written
    start_index = 22 + (ControllerSwitchEnum.START.value - 1)
    assert frame[start_index] == 200


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items())
             if name.startswith("test_") and callable(fn)]
    for fn in tests:
        fn()
        print(f"{fn.__name__} OK")
    print(f"\nAll {len(tests)} tests passed")
