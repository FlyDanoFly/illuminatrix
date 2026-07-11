import logging
import sys

from bases.InputSystem import InputSystem
from constants.constants import ControllerSwitchEnum, TowerEnum
from utils.KBHit import KBHit

logger = logging.getLogger(__name__)


# Keystrokes normalize to enums at read time, so this system stores the
# same enum-keyed state as the hardware SwitchInputSystem
TOWER_KEYMAP: dict[str, TowerEnum] = {
    str(tower_enum.value): tower_enum for tower_enum in TowerEnum
}

CONTROLLER_KEYMAP: dict[str, ControllerSwitchEnum] = {
    "\n": ControllerSwitchEnum.START,
    " ": ControllerSwitchEnum.NEXT_GAME,
    "\x1b": ControllerSwitchEnum.RESET,  # ESC
    # "\t": ControllerSwitchEnum.NEXT_VARIATION,  # TAB
}

# A terminal can't hold two keys down, so the quiet-hours combo (NEXT_GAME
# + RESET held together) gets a latch: press once to hold both, again to
# release. Holding it 10s toggles the quiet-hours profile, like the
# physical buttons
COMBO_LATCH_KEY = "q"


class KeyboardInputSystem(InputSystem):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._kbhit = KBHit()
        # KBHit needs termios; under a pipe or systemd there is no
        # terminal, so degrade to all-switches-released instead of dying
        self._tty_available: bool = sys.stdin.isatty()
        self._combo_latched: bool = False

    def startup(self) -> None:
        if self._tty_available:
            self._kbhit.startup()
        else:
            logger.warning("stdin is not a TTY — keyboard input disabled, all switches read released")
        return super().startup()

    def shutdown(self) -> None:
        if self._tty_available:
            self._kbhit.shutdown()
        return super().shutdown()

    def _read_switches(self, delta_secs: float) -> None:
        if not self._tty_available:
            return
        while self._kbhit.kbhit():
            c = self._kbhit.getch()
            if c in (COMBO_LATCH_KEY, COMBO_LATCH_KEY.upper()):
                self._combo_latched = not self._combo_latched
                if self._combo_latched:
                    print("Combo latch ON — holding NEXT_GAME + RESET")
                else:
                    print("Combo latch off — buttons released")
                continue
            switch = TOWER_KEYMAP.get(c) or CONTROLLER_KEYMAP.get(c)
            if switch is not None:
                self._switch_state[switch] = True
        if self._combo_latched:
            self._switch_state[ControllerSwitchEnum.NEXT_GAME] = True
            self._switch_state[ControllerSwitchEnum.RESET] = True

    def render(self) -> None:
        return super().render()
