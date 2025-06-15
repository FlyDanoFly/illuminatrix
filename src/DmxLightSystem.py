import logging

from LightSystem import LightSystem

logger = logging.getLogger(__name__)


class DmxLightSystem(LightSystem):
    def update(self, delta_ms: float):
        logger.debug("DMX update")

    def render(self):
        logger.debug("DMX render")
