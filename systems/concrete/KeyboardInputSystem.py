import logging

from bases.InputSystem import InputSystem
from constants.constants import ControllerSwitchEnum, TowerEnum
from utils.KBHit import KBHit

logger = logging.getLogger(__name__)


TOWER_KEYMAP: dict[str, TowerEnum] = {
    "1": TowerEnum.Tower_1,
    "2": TowerEnum.Tower_2,
    "3": TowerEnum.Tower_3,
    "4": TowerEnum.Tower_4,
    "5": TowerEnum.Tower_5,
    "6": TowerEnum.Tower_6,
    "7": TowerEnum.Tower_7,
}
# TOWER_KEYMAP_OLD = {
#     TowerEnum.Tower_1: str(TowerEnum.Tower_1.value),
#     TowerEnum.Tower_2: str(TowerEnum.Tower_2.value),
#     TowerEnum.Tower_3: str(TowerEnum.Tower_3.value),
#     TowerEnum.Tower_4: str(TowerEnum.Tower_4.value),
#     TowerEnum.Tower_5: str(TowerEnum.Tower_5.value),
#     TowerEnum.Tower_6: str(TowerEnum.Tower_6.value),
#     TowerEnum.Tower_7: str(TowerEnum.Tower_7.value),
# }

CONTROLLER_KEYMAP: dict[str, ControllerSwitchEnum] = {
    "\n": ControllerSwitchEnum.START,
    " ": ControllerSwitchEnum.NEXT_GAME,
    '\x1b': ControllerSwitchEnum.RESET,  # ESC
    # ControllerSwitchEnum.NEXT_VARIATION: '\t',  # TAB
}
# CONTROLLER_KEYMAP_OLD = {
#     ControllerSwitchEnum.START: "\n",
#     ControllerSwitchEnum.NEXT_GAME: " ",
#     ControllerSwitchEnum.RESET: '\x1b',  # ESC
#     # ControllerSwitchEnum.NEXT_VARIATION: '\t',  # TAB
# }

class KeyboardInputSystem(InputSystem):
    def __init__(self, **_):
        super().__init__(**_)
        self._kbhit = KBHit()
        # self._prev_switch_state: dict[TowerEnum | ControllerSwitchEnum, bool] = {}
        # self._switch_state: dict[TowerEnum | ControllerSwitchEnum, bool] = {}
        # self._prev_switch_state_old: dict[str, bool] = {}
        # self._switch_state_old: dict[str, bool] = {}
        # self._time_since_last_input = 0.0
        # self._time_since_last_switch_input = 0.0
        # self._time_since_last_tower_input = 0.0

    def startup(self) -> None:
        self._kbhit.startup()
        return super().startup()

    def shutdown(self) -> None:
        self._kbhit.shutdown()
        return super().shutdown()

    def update(self, delta_secs: float) -> None: 
        # self._prev_switch_state_old = self._switch_state_old
        self._prev_switch_state = self._switch_state
        # self._switch_state_old = {}
        self._switch_state = {}
        tower_switch_pressed = False
        controller_switch_pressed = False
        while self._kbhit.kbhit():
            c = self._kbhit.getch()
            # self._switch_state_old[c] = True
            if tower_enum := TOWER_KEYMAP.get(c):
                self._switch_state[tower_enum] = True
                tower_switch_pressed = True
            elif controller_switch_enum := CONTROLLER_KEYMAP.get(c):
                self._switch_state[controller_switch_enum] = True
                controller_switch_pressed = True

        # Keep track of how long since last input
        # TODO: make 3: any key, tower switch, or controller switch
        if tower_switch_pressed or controller_switch_pressed:
            self._time_since_last_switch_input = 0.0
            if tower_switch_pressed:
                self._time_since_last_tower_input = 0.0
            else:
                self._time_since_last_switch_input = 0.0
        else:
            self._time_since_last_tower_input += delta_secs

    def render(self) -> None:
        return super().render()

    # def is_switch_pressed(self, switch: str) -> bool:
    #     return self._switch_state_old.get(switch, False)

    # def did_switch_transition_down(self, switch: str) -> bool:
    #     return (
    #         not self._prev_switch_state_old.get(switch, False)
    #         and self._switch_state_old.get(switch, False)
    #     )

    # def did_switch_transition_up(self, switch: str) -> bool:
    #     return (
    #         self._prev_switch_state_old.get(switch, False)
    #         and not self._switch_state_old.get(switch, False)
    #     )            
    #
    # def is_tower_switch_pressed(self, tower_enum: TowerEnum) -> bool:
    #     return self.is_switch_pressed(TOWER_KEYMAP_OLD[tower_enum])
    #
    # def did_tower_switch_transition_down(self, tower_enum: TowerEnum) -> bool:
    #     return self.did_switch_transition_down(TOWER_KEYMAP_OLD[tower_enum])
    #
    # def did_tower_switch_transition_up(self, tower_enum: TowerEnum) -> bool:
    #     return self.did_switch_transition_up(TOWER_KEYMAP_OLD[tower_enum])
    #
    # def is_controller_switch_pressed(self, controller_switch_enum: ControllerSwitchEnum) -> bool:
    #     return self.is_switch_pressed(CONTROLLER_KEYMAP_OLD[controller_switch_enum])
    #
    # def did_controller_switch_transition_down(self, controller_switch_enum: ControllerSwitchEnum) -> bool:
    #     return self.did_switch_transition_down(CONTROLLER_KEYMAP_OLD[controller_switch_enum])
    #
    # def did_controller_switch_transition_up(self, controller_switch_enum: ControllerSwitchEnum) -> bool:
    #     return self.did_switch_transition_up(CONTROLLER_KEYMAP_OLD[controller_switch_enum])
