"""Input-system facade over the switch/pad serial link.

The wire itself (framing, CRC, reconnect) lives in SerialController,
which the game loop updates once per frame before this system; this
class turns its cached per-frame responses into the InputSystem state
contract: hold briefly through glitches, read released during outages,
and never fire phantom transitions at either edge of an outage.
"""

from bases.InputSystem import InputSystem, SwitchKey
from systems.concrete.serial_controller import (
    SERIAL_BAUDRATE,
    SERIAL_PORT,
    SerialController,
)


class SwitchInputSystem(InputSystem):
    def __init__(
            self,
            serial_port: str = SERIAL_PORT,
            baudrate: int = SERIAL_BAUDRATE,
            serial_controller: SerialController | None = None,
            **_,
        ):
        super().__init__(**_)
        self._serial_controller = serial_controller or SerialController(serial_port, baudrate)
        self._state_was_cleared: bool = False

    @property
    def serial_controller(self) -> SerialController:
        """The serial link, shared with the light system (it sets pad
        colors through it) and updated by the game loop. Its lifecycle is
        refcounted, so each participant runs it independently."""
        return self._serial_controller

    def startup(self) -> None:
        self._serial_controller.startup()
        return super().startup()

    def shutdown(self) -> None:
        self._serial_controller.shutdown()
        return super().shutdown()

    def _read_switches(self, delta_secs: float) -> None:
        pressed = self._serial_controller.pressed_switches
        if pressed is None:
            self._handle_missed_response()
            return
        new_state: dict[SwitchKey, bool] = {switch: True for switch in pressed}
        if self._state_was_cleared:
            # First response after an outage cleared the state: a switch
            # held across the whole outage is not a fresh press
            self._prev_switch_state = dict(new_state)
            self._state_was_cleared = False
        self._switch_state = new_state

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
        if self._serial_controller.is_stale:
            self._prev_switch_state = {}
            self._switch_state = {}
            self._state_was_cleared = True
        else:
            # Hold the last known state. Explicit copy: aliasing prev and
            # current to one dict would let a future in-place mutation
            # corrupt both
            self._switch_state = dict(self._prev_switch_state)

    def render(self) -> None:
        return super().render()
