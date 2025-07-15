import logging
import random

from bases import BaseGame
from components.TowerController import TowerController
from constants.colors import DULL_RAINBOW, RAINBOW
from constants.constants import TowerEnum

logger = logging.getLogger(__name__)


class Music(BaseGame):
    def __init__(self, tower_controller: TowerController):
        super().__init__()
        self._towers = tower_controller
        self._towers.load_sound_bank("sound_banks/music/")

        self.elapsed_time = 0.0
        self.fade_time = 0.1
        self.towers = list(x for x in self._towers.values())
        self.towers_that_are_on = list()
        self.dull_rainbow = list(list(x) for x in DULL_RAINBOW)
        self.rbg_for_each_tower = dict(zip(range(len(self.towers)), self.dull_rainbow))

    def first_frame_update(self) -> None:
        for idx, tower in enumerate(self._towers.values()):
            self.rgb = DULL_RAINBOW[idx]
            tower.set_color(self.rgb)

    def update(self, delta_secs: float) -> bool:
        logger.debug("LucyTest.update()", delta_secs)
        self.elapsed_time += delta_secs
        if self.elapsed_time >= self.fade_time:
            self.elapsed_time -= self.fade_time
            for tower in range(len(self.towers)):
                for i in range(3):
                    if self.rbg_for_each_tower[tower][i] > self.dull_rainbow[tower][i]:
                        self.rbg_for_each_tower[tower][i] *= 0.66
                self.towers[tower].set_color(tuple(self.rbg_for_each_tower[tower]))
        if self._towers.is_any_switch_pressed():
            for tower_enum, tower in self._towers.items():
                if tower.did_switch_transition_down():
                    tower.set_color(RAINBOW[tower_enum.value - 1])
                    self.rbg_for_each_tower[tower_enum.value - 1] = list(RAINBOW[tower_enum.value - 1])
                    tower.play_sound("note-"+str(tower_enum.value))
        return False
