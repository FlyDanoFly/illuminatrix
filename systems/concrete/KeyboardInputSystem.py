from bases.InputSystem import InputSystem
from constants.constants import SystemIdentifier
from utils.KBHit import KBHit


class KeyboardInputSystem(InputSystem):
    def __init__(self, num_towers: int, **_):
        self._num_towers = num_towers
        self._prev_switch_state: dict[int, bool] = {d: False for d in range(num_towers)}
        self._switch_state: dict[int, bool] = {d: False for d in range(num_towers)}
        self._kbhit = KBHit()

    def startup(self) -> None:
        self._kbhit.startup()
        return super().startup()

    def shutdown(self) -> None:
        self._kbhit.shutdown()
        return super().shutdown()

    def update(self, delta_ms: float) -> None: 
        self._prev_switch_state = self._switch_state.copy()
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

    def get_switch_transition_down(self, system_id: SystemIdentifier) -> bool:
        return not self._prev_switch_state[system_id] and self._switch_state[system_id]

    def get_switch_transition_up(self, system_id: SystemIdentifier) -> bool:
        return self._prev_switch_state[system_id] and not self._switch_state[system_id]
