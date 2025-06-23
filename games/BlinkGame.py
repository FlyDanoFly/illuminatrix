from BaseGame import BaseGame

from components.TowerController import TowerController
from constants.colors import PRIMARY_COLORS, WHITE
from utils.utils import cycle


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
        # to test inputs, let's make it white if a key is pressed
        override = self._towers.any_switch_pressed()
        if override:
            self._towers.set_color(WHITE)

        self._next_flash -= delta_ms
        if self._next_flash > 0.0:
            return False

        while self._next_flash < 0.0:
            self._next_flash += self._flash_rate
        self._color = self._color_cycle.__next__()

        if not override:
            self._towers.set_color(self._color)
        return False
