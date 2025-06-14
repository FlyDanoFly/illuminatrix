from abc import ABC, abstractmethod


class BaseGame(ABC):
    def first_frame_update(self) -> None:
        """Override this to set up a first frame before updating"""
        pass

    @abstractmethod
    def update(self, delta_ms: float) -> bool:
        """Returns: True if program should terminate, falsy to continue"""
        pass
