"""A synchronous DMX client for the "Simulation"."""
from __future__ import annotations

import json
import logging
from collections.abc import Sequence

from constants import IlluminatrixClientError, TowerLight

from .dmx_controller import DmxController
from .fixture import Fixture

logger = logging.getLogger(__file__)


class SynchronousDmxClient:
    def __init__(
            self,
        ):
        self.dmx_controller = DmxController()
        self.fixtures = {
                tower_light.value: [
                    Fixture(id=2*idx, controller=self.dmx_controller),
                    Fixture(id=2*idx + 1, controller=self.dmx_controller),
                ]
            for idx, tower_light in enumerate(TowerLight)
        }

    def __enter__(self):
        """DMX client context manager"""
        return self

    def __exit__(self, *_):
        """DMX client context manager"""
        pass

    def connect(self):
        pass

    def disconnect(self):
        pass

    def set_colors(self, towers: dict[TowerLight, Sequence[float]]) -> None:
        """
        Set the colors for multiple towers

        Arguments:
        towers = dict of TowerLight enums pointing to the color to set it to, ex:
            {
                TowerLight.TOWER_0_LIGHT_TOTAL: (1.0, 1.0, 1.0),
                TowerLight.TOWER_3_LIGHT_TOTAL: (0.3, 0.4, 0.5),
            }
        """
        if not towers:
            return
        for tower, color in towers.items():
            if not (0.0 <= color[0] <= 1.0 and
                0.0 <= color[1] <= 1.0 and
                0.0 <= color[2] <= 1.0):
                raise IlluminatrixClientError()
            for fixture in self.fixtures[tower.value]:
                vamped_color = [
                    int(color[0] * 255),
                    int(color[1] * 255),
                    int(color[2] * 255),
                ]
                fixture.set_colour(vamped_color)
        self.dmx_controller._send_dmx_frame()

    def set_color(self, towers: list | TowerLight, red: float, green: float, blue: float):
        """
        Set one or more towers the same color

        Arguments:
        towers = either a single TowerLight enum or a list of TowerLight enums
        red = how much red [0.0-1.0]
        green = how much green [0.0-1.0]
        blue = how much blue [0.0-1.0]
        """
        raise NotImplementedError()
        if not towers:
            return
        if isinstance(towers, TowerLight):
            towers = [towers]
        if not (0.0 <= red <= 1.0 and
            0.0 <= green <= 1.0 and
            0.0 <= blue <= 1.0):
            raise IlluminatrixClientError()
        
        message = {
            "ack": self.ack.value,
            "towers": {k.value: (red, green, blue) for k in towers},
        }
        self.websocket.send(json.dumps(message))
