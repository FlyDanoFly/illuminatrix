from bases.InputSystem import InputSystem
from constants.constants import TowerEnum
from utils.KBHit import KBHit

TOWER_KEYMAP = {
    "1": TowerEnum.Tower_1,
    "2": TowerEnum.Tower_2,
    "3": TowerEnum.Tower_3,
    "4": TowerEnum.Tower_4,
    "5": TowerEnum.Tower_5,
    "6": TowerEnum.Tower_6,
    "7": TowerEnum.Tower_7,
}

class KeyboardInputSystem(InputSystem):
    def __init__(self, **_):
        self._prev_switch_state: dict[TowerEnum, bool] = {d: False for d in TowerEnum}
        self._switch_state: dict[TowerEnum, bool] = {d: False for d in TowerEnum}
        self._kbhit = KBHit()

    def startup(self) -> None:
        self._kbhit.startup()
        return super().startup()

    def shutdown(self) -> None:
        self._kbhit.shutdown()
        return super().shutdown()

    def update(self, delta_secs: float) -> None: 
        self._prev_switch_state = self._switch_state.copy()
        self._switch_state = {d: False for d in TowerEnum}
        while self._kbhit.kbhit():
            c = self._kbhit.getch()
            tower_switch = TOWER_KEYMAP.get(c)
            if tower_switch in self._switch_state:
                self._switch_state[tower_switch] = True

    def render(self) -> None:
        return super().render()

    def get_switch_state(self, tower_enum: TowerEnum) -> bool:
        return self._switch_state[tower_enum]

    def get_switch_transition_down(self, tower_enum: TowerEnum) -> bool:
        return not self._prev_switch_state[tower_enum] and self._switch_state[tower_enum]

    def get_switch_transition_up(self, tower_enum: TowerEnum) -> bool:
        return self._prev_switch_state[tower_enum] and not self._switch_state[tower_enum]
