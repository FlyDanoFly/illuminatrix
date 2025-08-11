from bases.BaseSystem import BaseSystem
from constants.constants import ControllerSwitchEnum, TowerEnum


class InputSystem(BaseSystem):
    def __init__(self, **_):
        self._prev_switch_state: dict[TowerEnum | ControllerSwitchEnum, bool] = {}
        self._switch_state: dict[TowerEnum | ControllerSwitchEnum, bool] = {}
        self._time_since_last_input = 0.0
        self._time_since_last_switch_input = 0.0
        self._time_since_last_tower_input = 0.0

    def is_switch_pressed(self, switch: TowerEnum | ControllerSwitchEnum) -> bool:
        return self._switch_state.get(switch, False)

    def did_switch_transition_down(self, switch: TowerEnum | ControllerSwitchEnum) -> bool:
        return (
            not self._prev_switch_state.get(switch, False)
            and self._switch_state.get(switch, False)
        )

    def did_switch_transition_up(self, switch: TowerEnum | ControllerSwitchEnum) -> bool:
        return (
            self._prev_switch_state.get(switch, False)
            and not self._switch_state.get(switch, False)
        )            

    def is_tower_switch_pressed(self, tower_enum: TowerEnum) -> bool:
        return self.is_switch_pressed(tower_enum)

    def did_tower_switch_transition_down(self, tower_enum: TowerEnum) -> bool:
        return self.did_switch_transition_down(tower_enum)

    def did_tower_switch_transition_up(self, tower_enum: TowerEnum) -> bool:
        return self.did_switch_transition_up(tower_enum)

    def is_controller_switch_pressed(self, controller_switch_enum: ControllerSwitchEnum) -> bool:
        return self.is_switch_pressed(controller_switch_enum)

    def did_controller_switch_transition_down(self, controller_switch_enum: ControllerSwitchEnum) -> bool:
        return self.did_switch_transition_down(controller_switch_enum)

    def did_controller_switch_transition_up(self, controller_switch_enum: ControllerSwitchEnum) -> bool:
        return self.did_switch_transition_up(controller_switch_enum)
