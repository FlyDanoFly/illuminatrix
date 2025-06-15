from BaseGame import BaseGame
from colors import PRIMARY_COLORS
from TowerController import TowerController
from utils import cycle


class Blink(BaseGame):
    def __init__(self, tower_controller: TowerController):
        self._towers = tower_controller
        self._flash_rate = 1.0 / 2.0
        self._color_cycle = cycle(PRIMARY_COLORS)
        self._color = self._color_cycle.__next__()

    def first_frame_update(self) -> None:
        """Override this to set up a first frame before updating"""
        self._towers.set_color(self._color)
        self._next_flash = self._flash_rate

    def update(self, delta_ms: float) -> bool:
        """Returns: True if program should terminate, falsy to continue"""
        self._next_flash -= delta_ms
        if self._next_flash > 0.0:
            return False

        while self._next_flash < 0.0:
            self._next_flash += self._flash_rate
        self._color = self._color_cycle.__next__()
        self._towers.set_color(self._color)
        return False
