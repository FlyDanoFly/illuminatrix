from abc import ABC, abstractmethod

from constants.constants import ShouldStop


class BaseGame(ABC):
    # The sound bank this game plays from, or None for a silent game.
    # Declared as a class attribute so play.py can preload every bank the
    # run's games will ask for before the game loop starts; the game
    # itself still requests it (load_sound_bank(self.SOUND_BANK)), which
    # hits the warm cache — or loads on the spot in an unpreloaded context
    SOUND_BANK: str | None = None

    @abstractmethod
    def first_frame_update(self) -> None:
        """Override this to set up a first frame before updating"""
        pass

    @abstractmethod
    def update(self, delta_secs: float) -> ShouldStop:
        """Returns: True if program should terminate, falsy to continue"""
        pass
