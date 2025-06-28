from abc import abstractmethod

from bases.BaseSystem import BaseSystem
from constants.constants import SystemIdentifier


class InputSystem(BaseSystem):
    @abstractmethod
    def get_switch_state(self, system_id: SystemIdentifier) -> bool:
        pass

    @abstractmethod
    def get_switch_transition_down(self, system_id: SystemIdentifier) -> bool:
        pass

    @abstractmethod
    def get_switch_transition_up(self, system_id: SystemIdentifier) -> bool:
        pass
