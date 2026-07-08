import logging

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


class KeyboardInputSystem(InputSystem):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._kbhit = KBHit()

    def startup(self) -> None:
        self._kbhit.startup()
        return super().startup()

    def shutdown(self) -> None:
        self._kbhit.shutdown()
        return super().shutdown()

    def _read_switches(self, delta_secs: float) -> None:
        while self._kbhit.kbhit():
            c = self._kbhit.getch()
            switch = TOWER_KEYMAP.get(c) or CONTROLLER_KEYMAP.get(c)
            if switch is not None:
                self._switch_state[switch] = True

    def render(self) -> None:
        return super().render()
