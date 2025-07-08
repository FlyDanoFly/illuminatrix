import logging

from bases.InputSystem import InputSystem
from constants.constants import ControllerSwitchEnum, TowerEnum
from utils.KBHit import KBHit

logger = logging.getLogger(__name__)


TOWER_KEYMAP = {
    TowerEnum.Tower_1: str(TowerEnum.Tower_1.value),
    TowerEnum.Tower_2: str(TowerEnum.Tower_2.value),
    TowerEnum.Tower_3: str(TowerEnum.Tower_3.value),
    TowerEnum.Tower_4: str(TowerEnum.Tower_4.value),
    TowerEnum.Tower_5: str(TowerEnum.Tower_5.value),
    TowerEnum.Tower_6: str(TowerEnum.Tower_6.value),
    TowerEnum.Tower_7: str(TowerEnum.Tower_7.value),
}

CONTROLLER_KEYMAP = {
    ControllerSwitchEnum.START: "\n",
    ControllerSwitchEnum.NEXT_GAME: " ",
    ControllerSwitchEnum.RESET: '\x1b',  # ESC
    # ControllerSwitchEnum.NEXT_VARIATION: '\t',  # TAB
}

class KeyboardInputSystem(InputSystem):
    def __init__(self, **_):
        self._kbhit = KBHit()
        self._prev_switch_state: dict[str, bool] = {}
        self._switch_state: dict[str, bool] = {}

    def startup(self) -> None:
        self._kbhit.startup()
        return super().startup()

    def shutdown(self) -> None:
        self._kbhit.shutdown()
        return super().shutdown()

    def update(self, delta_secs: float) -> None: 
        self._prev_switch_state = self._switch_state
        self._switch_state = {}
        while self._kbhit.kbhit():
            c = self._kbhit.getch()
            self._switch_state[c] = True

    def render(self) -> None:
        return super().render()

    def is_switch_pressed(self, switch: str) -> bool:
        return self._switch_state.get(switch, False)

    def did_switch_transition_down(self, switch: str) -> bool:
        return (
            not self._prev_switch_state.get(switch, False)
            and self._switch_state.get(switch, False)
        )

    def did_switch_transition_up(self, switch: str) -> bool:
        return (
            self._prev_switch_state.get(switch, False)
            and not self._switch_state.get(switch, False)
        )            

    def is_tower_switch_pressed(self, tower_enum: TowerEnum) -> bool:
        return self.is_switch_pressed(TOWER_KEYMAP[tower_enum])

    def did_tower_switch_transition_down(self, tower_enum: TowerEnum) -> bool:
        return self.did_switch_transition_down(TOWER_KEYMAP[tower_enum])

    def did_tower_switch_transition_up(self, tower_enum: TowerEnum) -> bool:
        return self.did_switch_transition_up(TOWER_KEYMAP[tower_enum])

    def is_controller_switch_pressed(self, controller_switch_enum: ControllerSwitchEnum) -> bool:
        return self.is_switch_pressed(CONTROLLER_KEYMAP[controller_switch_enum])

    def did_controller_switch_transition_down(self, controller_switch_enum: ControllerSwitchEnum) -> bool:
        return self.did_switch_transition_down(CONTROLLER_KEYMAP[controller_switch_enum])

    def did_controller_switch_transition_up(self, controller_switch_enum: ControllerSwitchEnum) -> bool:
        return self.did_switch_transition_up(CONTROLLER_KEYMAP[controller_switch_enum])
