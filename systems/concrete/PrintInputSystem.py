from bases.InputSystem import InputSystem
from constants.constants import TowerEnum
from utils.KBHit import KBHit

# TODO: more modes? INSTANT vs HIGH UNTIL READ vs THIS_FRAME vs ??


class PrintInputSystem(InputSystem):
    def __init__(self):
        self._switch_state: dict[TowerEnum, bool] = {d: False for d in TowerEnum}
        self._kbhit = KBHit()

    def startup(self) -> None:
        print("PrintInputSystem: startup")
        return super().startup()

    def shutdown(self) -> None:
        print("PrintInputSystem: shutdown")
        return super().shutdown()

    def update(self, delta_secs: float) -> None: 
        print("PrintInputSystem: update", delta_secs)

    def render(self) -> None:
        print("PrintInputSystem: render")
        return super().render()

    def get_switch_state(self, tower_enum: TowerEnum) -> bool:
        print("PrintInputSystem: get_switch_state")
        return self._switch_state[tower_enum]
