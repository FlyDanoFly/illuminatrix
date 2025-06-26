from abc import abstractmethod

from bases.BaseSystem import BaseSystem
from constants.constants import SystemIdentifier


class InputSystem(BaseSystem):
    @abstractmethod
    def get_switch_state(self, system_id: SystemIdentifier) -> bool:
        pass
