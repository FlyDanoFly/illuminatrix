from constants import SystemIdentifier
from InputSystem import InputSystem
from KBHit import KBHit

# TODO: more modes? INSTANT vs HIGH UNTIL READ vs THIS_FRAME vs ??


class PrintInputSystem(InputSystem):
    def __init__(self, num_towers: int):
        self._num_towers = num_towers
        self._switch_state: dict[int, bool] = {d: False for d in range(num_towers)}
        self._kbhit = KBHit()

    def startup(self) -> None:
        print("PrintInputSystem: startup")
        return super().startup()

    def shutdown(self) -> None:
        print("PrintInputSystem: shutdown")
        return super().shutdown()

    def update(self, delta_ms: float) -> None: 
        print("PrintInputSystem: update", delta_ms)

    def render(self) -> None:
        print("PrintInputSystem: render")
        return super().render()

    def get_switch_state(self, system_id: SystemIdentifier) -> bool:
        print("PrintInputSystem: get_switch_state")
        return self._switch_state[system_id]
