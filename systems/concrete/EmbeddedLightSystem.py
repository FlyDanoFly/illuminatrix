"""Light system for the embedded installation.

Tower fixtures hang off a DmxController; pad LEDs ride the serial link
to the switch/pad controller. Both controllers are injected (the
SystemSingletonFactory wires them up); either may be None, and that
link's lights are simply skipped.
"""

import logging

from bases.LightSystem import LightSystem
from constants.constants import ColorType, LightPos, TowerEnum

from .dmx_controller import DmxController
from .dmx_fixture import DmxFixture
from .serial_controller import SerialController

logger = logging.getLogger(__name__)

TOWER_POSITIONS = LightPos.Tower_top | LightPos.Tower_bottom
# The stomp pads have one physical RGB each today, so Pad_top and
# Pad_bottom address the same LED until the hardware distinguishes them
PAD_POSITIONS = LightPos.Pad_top | LightPos.Pad_bottom


class EmbeddedLightSystem(LightSystem):
    def update(self, delta_secs: float):
        logger.debug("EmbeddedLightSystem update")
        # Colors are set instantly on set(); this could batch into update
        # to cut down on traffic if the links seem saturated

    def render(self):
        logger.debug("EmbeddedLightSystem render")

    def __init__(
            self,
            dmx_controller: DmxController | None = None,
            serial_controller: SerialController | None = None,
            **_,
        ):
        # The serial controller is shared with the input system (same
        # link carries pad colors down and switch states up) and updated
        # by the game loop; its lifecycle is refcounted, so each
        # participant runs it independently
        self._serial_controller = serial_controller
        self._dmx_controller = dmx_controller
        self.fixtures: dict[TowerEnum, list[DmxFixture]] = {} if dmx_controller is None else {
                tower_enum: [
                    DmxFixture(id=2*(tower_enum.value-1), controller=dmx_controller),
                    DmxFixture(id=2*(tower_enum.value-1) + 1, controller=dmx_controller),
                ]
            for tower_enum in TowerEnum
        }
        self.colors: dict[TowerEnum, ColorType] = {
            tower_enum: (0.0, 0.0, 0.0)
            for tower_enum in TowerEnum
        }

    def startup(self):
        if self._dmx_controller is not None:
            self._dmx_controller.start()
        if self._serial_controller is not None:
            self._serial_controller.startup()

    def shutdown(self):
        if self._dmx_controller is not None:
            self._dmx_controller.stop()
        if self._serial_controller is not None:
            self._serial_controller.shutdown()

    def set(self, tower_enum: TowerEnum, color: ColorType, light_pos: LightPos = LightPos.All):
        """
        Set the color of one tower's lights.

        Arguments:
        tower_enum -- which tower to set
        color -- (r, g, b) floats in 0.0..1.0
        light_pos -- which of the tower's lights to set (default all)
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
        if light_pos & TOWER_POSITIONS and self._dmx_controller is not None and self.colors[tower_enum] != vamped_color:
            self.colors[tower_enum] = vamped_color
            for fixture in self.fixtures[tower_enum]:
                fixture.set_colour(vamped_color)
        if light_pos & PAD_POSITIONS and self._serial_controller is not None:
            self._serial_controller.set_pad_color(tower_enum, vamped_color)
