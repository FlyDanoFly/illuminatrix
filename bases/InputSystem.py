from abc import abstractmethod

from bases.BaseSystem import BaseSystem
from constants.constants import ControllerSwitchEnum, TowerEnum

SwitchKey = TowerEnum | ControllerSwitchEnum


class InputSystem(BaseSystem):
    """Base for input systems: owns the enum-keyed switch state, the
    press/transition queries, and idle-time tracking.

    Subclasses implement _read_switches() to fill _switch_state with the
    switches currently pressed; update() handles the frame-to-frame state
    rotation and idle timers.
    """

    def __init__(self, **_):
        self._prev_switch_state: dict[SwitchKey, bool] = {}
        self._switch_state: dict[SwitchKey, bool] = {}
        self._secs_since_last_input = 0.0
        self._secs_since_last_tower_input = 0.0
        self._secs_since_last_controller_input = 0.0

    @abstractmethod
    def _read_switches(self, delta_secs: float) -> None:
        """Populate _switch_state with the switches currently pressed."""

    def update(self, delta_secs: float) -> None:
        self._prev_switch_state = self._switch_state
        self._switch_state = {}
        self._read_switches(delta_secs)
        self._update_idle_timers(delta_secs)

    def _update_idle_timers(self, delta_secs: float) -> None:
        # A held switch counts as activity: someone is still standing there
        tower_active = any(
            isinstance(switch, TowerEnum) and pressed
            for switch, pressed in self._switch_state.items()
        )
        controller_active = any(
            isinstance(switch, ControllerSwitchEnum) and pressed
            for switch, pressed in self._switch_state.items()
        )
        self._secs_since_last_input += delta_secs
        self._secs_since_last_tower_input += delta_secs
        self._secs_since_last_controller_input += delta_secs
        if tower_active:
            self._secs_since_last_input = 0.0
            self._secs_since_last_tower_input = 0.0
        if controller_active:
            self._secs_since_last_input = 0.0
            self._secs_since_last_controller_input = 0.0

    @property
    def secs_since_last_input(self) -> float:
        return self._secs_since_last_input

    @property
    def secs_since_last_tower_input(self) -> float:
        return self._secs_since_last_tower_input

    @property
    def secs_since_last_controller_input(self) -> float:
        return self._secs_since_last_controller_input

    def is_switch_pressed(self, switch: SwitchKey) -> bool:
        return self._switch_state.get(switch, False)

    def did_switch_transition_down(self, switch: SwitchKey) -> bool:
        return (
            not self._prev_switch_state.get(switch, False)
            and self._switch_state.get(switch, False)
        )

    def did_switch_transition_up(self, switch: SwitchKey) -> bool:
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
