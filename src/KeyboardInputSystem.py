from constants import SystemIdentifier
from InputSystem import InputSystem
from KBHit import KBHit

# TODO: more modes? INSTANT vs HIGH UNTIL READ vs THIS_FRAME vs ??


class KeyboardInputSystem(InputSystem):
    def __init__(self, num_towers: int):
        self._num_towers = num_towers
        self._switch_state: dict[int, bool] = {d: False for d in range(num_towers)}
        self._kbhit = KBHit()

    def startup(self) -> None:
        self._kbhit.startup()
        return super().startup()

    def shutdown(self) -> None:
        self._kbhit.shutdown()
        return super().shutdown()

    def update(self, delta_ms: float) -> None: 
        self._switch_state = {d: False for d in range(self._num_towers)}
        while self._kbhit.kbhit():
            c = self._kbhit.getch()
            switch_id = ord(c) - ord("1")
            if switch_id in self._switch_state:
                self._switch_state[switch_id] = True

    def render(self) -> None:
        return super().render()

    def get_switch_state(self, system_id: SystemIdentifier) -> bool:
        return self._switch_state[system_id]
