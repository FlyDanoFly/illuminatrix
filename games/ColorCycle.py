import logging

from bases import BaseGame
from components.TowerController import TowerController
from constants.constants import TowerEnum
from effects.BingFade import BingFade
from utils import hsv_to_rgb

logger = logging.getLogger(__name__)

# HERTZ = 1.0  # very fast to see it working
# HERTZ = 0.10  # pretty fast still
HERTZ = 0.02  # longer and mellow, pretty

COLOR_CYCLE_FADE_IN_TIME_SEC = 20.5
COLOR_CYCLE_SUSTAIN_TIME_SEC = 0.0

class ColorCycle(BaseGame):
    def __init__(self, tower_controller: TowerController) -> None:
        self._towers = tower_controller
        self.start_hue = 0.0
        self.hue_tower_step = 1.0 / len(TowerEnum)
        self.hertz = HERTZ

    def first_frame_update(self) -> None:
        self.update(0.0)
        hue = self.start_hue
        for tower_enum in self._towers:
            rgb = hsv_to_rgb(hue, 1.0, 1.0)
            bing_effect = BingFade(
                [tower_enum],
                start_color=(1.0, 1.0, 1.0),
                end_color=rgb,
                fade_time_sec=COLOR_CYCLE_FADE_IN_TIME_SEC,
                sustain_time_sec=COLOR_CYCLE_FADE_IN_TIME_SEC,
            )
            self._towers.start_effect(bing_effect)
            hue = (hue + self.hue_tower_step) % 1.0


    def update(self, delta_secs: float) -> bool | None:
        if self._towers.are_any_effects_playing():
            # If any effect is playing, we don't want to update the colors
            return None

        self.start_hue = (self.start_hue + self.hertz * delta_secs) % 1.0
        hue = self.start_hue
        for _, tower in self._towers.items():
            rgb = hsv_to_rgb(hue, 1.0, 1.0)
            tower.set_color(rgb)
            hue = (hue + self.hue_tower_step) % 1.0
