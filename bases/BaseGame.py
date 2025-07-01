from abc import ABC, abstractmethod

from statemachine import StateMachine

from components.TowerController import TowerController

type ShouldStop = bool | None  # Type alias for clarity in return types

class AbstractBaseGame(ABC):
    @abstractmethod
    def first_frame_update(self) -> None:
        """Override this to set up a first frame before updating"""
        pass

    @abstractmethod
    def update(self, delta_secs: float) -> ShouldStop:
        """Returns: True if program should terminate, falsy to continue"""
        pass


class BaseGame:
    def __init__(self, tower_controller: TowerController) -> None:
        """Classes should accept a TowerController"""
        raise NotImplementedError("Subclasses should implement this method")

    def first_frame_update(self) -> None:
        """Override this to set up a first frame before updating"""
        raise NotImplementedError("Subclasses should implement this method")

    def update(self, delta_secs: float) -> ShouldStop:
        """Returns: True if program should terminate, falsy to continue"""
        raise NotImplementedError("Subclasses should implement this method")


class BaseStatemachineGame(BaseGame, StateMachine):
    """Base class for games using a state machine."""

    def first_frame_update(self) -> None:
        """Override this to set up a first frame before updating"""
        pass

    def update(self, delta_secs: float) -> ShouldStop:
        """Returns: True if program should terminate, falsy to continue"""
        return self.do_state(delta_secs)

    def do_state(self, delta_secs: float) -> ShouldStop:
        if do_state := getattr(self, f'do_{self.current_state.value}', None):
            return do_state(delta_secs)
