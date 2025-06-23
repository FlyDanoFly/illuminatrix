import logging

from BaseGame import BaseGame

from components.TowerController import TowerController
from constants.constants import TowerEnum
from utils.utils import hsv_to_rgb

logger = logging.getLogger(__name__)

# HERTZ = 1.0  # very fast to see it working
HERTZ = 0.10  # pretty fast still
# HERTZ = 0.005  # longer and mellow, pretty


class ColorCycle(BaseGame):
    def __init__(self, tower_controller: TowerController, hertz: float = HERTZ):
        # TODO: generic parameters from the command line
        super().__init__()
        print("ColorCycle.__init__()", hertz)
        self._towers = tower_controller
        self.start_hue = 0.0
        self.hue_tower_step = 1.0 / len(TowerEnum)
        self.hertz = hertz

    def first_frame_update(self) -> None:
        self.update(0.0)
        return super().first_frame_update()

    def update(self, delta_ms: float) -> bool | None:
        # print("ColorCycle.update()", delta_ms)
        self.start_hue = (self.start_hue + self.hertz * delta_ms) % 1.0
        hue = self.start_hue
        for tower in self._towers:
            hsv = hsv_to_rgb(hue, 1.0, 1.0)
            tower.set_color(hsv)
            hue = (hue + self.hue_tower_step) % 1.0
