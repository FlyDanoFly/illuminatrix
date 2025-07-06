from abc import ABC, abstractmethod

from constants.constants import ShouldStop


class BaseGame(ABC):
    @abstractmethod
    def first_frame_update(self) -> None:
        """Override this to set up a first frame before updating"""
        pass

    @abstractmethod
    def update(self, delta_secs: float) -> ShouldStop:
        """Returns: True if program should terminate, falsy to continue"""
        pass
