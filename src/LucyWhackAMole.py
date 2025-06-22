#!/usr/bin/env poetry run python

import logging
import random

from BaseGame import BaseGame
from colors import DULL_RAINBOW, RAINBOW
from constants import TowerEnum
from TowerController import TowerController

logger = logging.getLogger(__name__)


class LucyWhackAMole(BaseGame):
    def __init__(self, tower_controller: TowerController):
        super().__init__()
        self._towers = tower_controller
        self.elapsed_time = 0.0
        self.time_between_moles_popping_up = 1
        self.towers = list(range(len(TowerEnum)))
        self.int_to_tower = {x: y for x, y in enumerate(TowerEnum)}
        self.towers_that_are_off = list(range(len(TowerEnum)))
        self.new_mole_number = 0
        self.failed = False

    def first_frame_update(self) -> None:
        for idx, tower in enumerate(self._towers):
            self.rgb = DULL_RAINBOW[idx]
            tower.set_color(self.rgb)
        return super().first_frame_update()

    def update(self, delta_ms: float) -> bool:
        logger.debug("LucyTest.update()", delta_ms)
        self.elapsed_time += delta_ms
        if self.failed:
            if self._towers.are_any_sounds_playing():
                return False
            return True
        if self.elapsed_time >= self.time_between_moles_popping_up:
            self.elapsed_time -= self.time_between_moles_popping_up
            self.new_mole_number = random.choice(self.towers_that_are_off)
            tower = self._towers[self.int_to_tower[self.new_mole_number]]
            tower.set_color(RAINBOW[self.new_mole_number])
            tower.play_sound("boom")
            self.towers_that_are_off.remove(self.new_mole_number)
            if len(self.towers_that_are_off) == 0:
                for tower in self._towers:
                    tower.set_color((1.0, 0.0, 0.0))
                print("Wrong!")
                self.failed = True
                self._towers.play_sound("siren")
        return False
