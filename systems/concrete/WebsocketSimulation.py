"""A synchronous client for the Simulation."""

import json
import logging
import ssl
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from websockets.sync.client import connect

from bases.LightSystem import LightSystem
from constants.constants import ColorType, IlluminatrixError, LightPos, SystemIdentifier


class IlluminatrixClientError(IlluminatrixError):
    pass

logger = logging.getLogger(__name__)

# TODO: Remove all mention of the towers in this

# TODO: The right way to do this is to intall the correct signing certificate
# but I'm not quite sure how to do that, seems involved. This makes the
# websocket connect insecurely. This is OK provided this really is limited
# to the houseofsucky.xyz server, but better is to figure out how to
# validate the server's certificate. Sidestepping for now, otherwise it
# would mean figuring it out on Linux, Windows, Chromebook, and maybe
# even OSX. That's a bit much right now, maybe later.
SSL_CONTEXT = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE


class ACK(Enum):
    NONE = 0
    ON_MESSAGE = 1
    ON_UPDATE = 2


class WebsocketSimulation(LightSystem):
    DEFAULT_ACK = ACK.ON_UPDATE
    DEFAULT_PATH = "ws2"
    DEFAULT_PREFIX = "illuminatrix_simulation_server"

    def setup(
            self,
            server_address: str,
            client_id:str,
            num_towers: int,
            ack: ACK=DEFAULT_ACK):
        self.server_address = server_address
        self.client_id = client_id
        self.ack = ack
        self.websocket = None
        self._tower_colors: dict[SystemIdentifier, ColorType] = {}
        self._prev_tower_colors: dict[SystemIdentifier, ColorType|None] = {
            system_id: None for system_id in range(num_towers)
        }

    def startup(self) -> None:
        self.connect()
        return super().startup()

    def shutdown(self) -> None:
        self.disconnect()
        return super().shutdown()

    def connect(self):
        parts = urlparse(self.server_address)
        path = Path(parts.path, self.DEFAULT_PATH, self.client_id)
        url = urlunparse((
            parts.scheme,
            parts.netloc,
            str(path),
            parts.params,
            parts.query,
            parts.fragment,
        ))
        logger.info("connecting to %s", url)
        if self.server_address.startswith("wss"):
            self.websocket = connect(str(url), ssl_context=SSL_CONTEXT)
        else:
            self.websocket = connect(str(url))
        return self

    def disconnect(self):
        if self.websocket:
            self.websocket.close()
        self.websocket = None

    def set(self, system_id: SystemIdentifier, color: ColorType, light_pos: LightPos = LightPos.All):
        """
        Set one or more towers the same color

        Arguments:
        towers = either a single TowerLight enum or a list of TowerLight enums
        red = how much red [0.0-1.0]
        green = how much green [0.0-1.0]
        blue = how much blue [0.0-1.0]
        """
        # if not self.websocket:
        #     raise IlluminatrixClientError("not connected, call .connect() first")
        red, green, blue = color
        if not (0.0 <= red <= 1.0 and
            0.0 <= green <= 1.0 and
            0.0 <= blue <= 1.0):
            raise IlluminatrixClientError()
        self._tower_colors[system_id] = (red, green, blue)

    def update(self, delta_ms: float) -> None:
        pass

    def render(self) -> None:
        if not self.websocket:
            raise IlluminatrixClientError("not connected, call .connect() first")
        tower_dict = {}
        message = {
            "ack": self.ack.value,
            "towers": tower_dict,
        }
        for tower_id in self._tower_colors:
            color = self._tower_colors[tower_id]
            if color == self._prev_tower_colors[tower_id]:
                # Only transmit color changes
                continue
            if not color:
                # Only put changing colors in the message
                continue
            if not (0.0 <= color[0] <= 1.0 and
                0.0 <= color[1] <= 1.0 and
                0.0 <= color[2] <= 1.0):
                raise IlluminatrixClientError("Color out of bounds: %s", color)
            tower_dict[tower_id] = color

        # Update the previous state
        self._prev_tower_colors.update(self._tower_colors)

        if not tower_dict:
            # No updates to do
            return
        
        logger.debug(json.dumps(message))
        self.websocket.send(json.dumps(message))

        # I think this is to recieve the ACK
        self.websocket.recv()
