from abc import abstractmethod

from bases.BaseSystem import BaseSystem
from constants.constants import ControllerSwitchEnum, TowerEnum


class InputSystem(BaseSystem):
    @abstractmethod
    def is_switch_pressed(self, switch: str) -> bool:
        pass

    @abstractmethod
    def did_switch_transition_down(self, switch: str) -> bool:
        pass

    @abstractmethod
    def did_switch_transition_up(self, switch: str) -> bool:
        pass
    @abstractmethod
    def is_tower_switch_pressed(self, tower_enum: TowerEnum) -> bool:
        pass

    @abstractmethod
    def did_tower_switch_transition_down(self, tower_enum: TowerEnum) -> bool:
        pass

    @abstractmethod
    def did_tower_switch_transition_up(self, tower_enum: TowerEnum) -> bool:
        pass

    @abstractmethod
    def is_controller_switch_pressed(self, controller_switch_enum: ControllerSwitchEnum) -> bool:
        pass

    @abstractmethod
    def did_controller_switch_transition_down(self, controller_switch_enum: ControllerSwitchEnum) -> bool:
        pass

    @abstractmethod
    def did_controller_switch_transition_up(self, controller_switch_enum: ControllerSwitchEnum) -> bool:
        pass
