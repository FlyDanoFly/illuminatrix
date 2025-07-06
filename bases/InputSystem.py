from abc import abstractmethod

from bases.BaseSystem import BaseSystem
from constants.constants import TowerEnum


class InputSystem(BaseSystem):
    @abstractmethod
    def get_switch_state(self, tower_enum: TowerEnum) -> bool:
        pass

    @abstractmethod
    def get_switch_transition_down(self, tower_enum: TowerEnum) -> bool:
        pass

    @abstractmethod
    def get_switch_transition_up(self, tower_enum: TowerEnum) -> bool:
        pass
