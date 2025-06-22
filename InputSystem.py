from abc import abstractmethod
from BaseSystem import BaseSystem
from constants import SystemIdentifier


class InputSystem(BaseSystem):
    @abstractmethod
    def get_switch_state(self, system_id: SystemIdentifier) -> bool:
        pass
