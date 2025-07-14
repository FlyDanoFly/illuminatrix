"""Light system to connect with a DMX interface."""

import logging

from bases.LightSystem import LightSystem
from constants.constants import ColorType, LightPos, TowerEnum

from .dmx_controller import DmxController
from .fixture import Fixture

logger = logging.getLogger(__name__)


class DmxLightSystem(LightSystem):
    def update(self, delta_secs: float):
        logger.debug("DMX update")
        # DMX sets lights instantly, it could move to the update to cut down on updates if it seems saturated

    def render(self):
        logger.debug("DMX render")

    def __init__(
            self,
        ):
        self.dmx_controller: DmxController = DmxController()
        self.fixtures: dict[TowerEnum, list[Fixture]] = {
                tower_enum: [
                    Fixture(id=2*(tower_enum.value-1), controller=self.dmx_controller),
                    Fixture(id=2*(tower_enum.value-1) + 1, controller=self.dmx_controller),
                ]
            for tower_enum in TowerEnum
        }
        self.colors: dict[TowerEnum, ColorType] = {
            tower_enum: (0.0, 0.0, 0.0)
            for tower_enum in TowerEnum
        }

    # def __enter__(self):
    #     """DMX client context manager"""
    #     return self
    #
    # def __exit__(self, *_):
    #     """DMX client context manager"""
    #     pass
    #
    # def connect(self):
    #     pass
    #
    # def disconnect(self):
    #     pass


    def startup(self):
        pass

    def shutdown(self):
        pass

    def set(self, tower_enum: TowerEnum, color: ColorType, light_pos: LightPos = LightPos.All):
    # def set_colors(self, towers: dict[TowerLight, Sequence[float]]) -> None:
        """
        Set the colors for multiple towers

        Arguments:
        towers = dict of TowerLight enums pointing to the color to set it to, ex:
            {
                TowerLight.TOWER_0_LIGHT_TOTAL: (1.0, 1.0, 1.0),
                TowerLight.TOWER_3_LIGHT_TOTAL: (0.3, 0.4, 0.5),
            }
        """
        if not (0.0 <= color[0] <= 1.0 and
            0.0 <= color[1] <= 1.0 and
            0.0 <= color[2] <= 1.0):
            # TODO: Replace with assert to remove from production code
            raise RuntimeError("IlluminatrixClientError(): Color out of bounds")
        vamped_color = (
            int(color[0] * 255),
            int(color[1] * 255),
            int(color[2] * 255),
        )
        if self.colors[tower_enum] != vamped_color:
            self.colors[tower_enum] = vamped_color
            for fixture in self.fixtures[tower_enum]:
                fixture.set_colour(vamped_color)
        self.dmx_controller._send_dmx_frame()
