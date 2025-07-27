"""An asynchronous client for the Simulation."""
from __future__ import annotations

from collections.abc import Sequence
from enum import Enum
import json
import logging
from pathlib import Path
from urllib.parse import urlunparse

import ssl
from websockets.client import connect

from constants import IlluminatrixClientError, TowerLight


logger = logging.getLogger(__file__)


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


class AsynchronousClient:
    DEFAULT_ACK = ACK.ON_UPDATE
    DEFAULT_PATH = "ws2"
    DEFAULT_PREFIX = "illuminatrix_simulation_server"

    def __init__(
            self,
            server_address: str,
            client_id:str,
            prefix:str=DEFAULT_PREFIX,
            secure:bool=False,
            ack: ACK=DEFAULT_ACK):
        self.server_address = server_address
        self.client_id = client_id
        self.prefix = prefix.strip("/")
        self.secure = secure
        self.ack = ack
        self.websocket = None

    # This is tricky with ASYNC, the del can't be async, if you want to get fancy try:
    #    https://stackoverflow.com/questions/54770360/how-can-i-wait-for-an-objects-del-to-finish-before-the-async-loop-closes
    # async def __del__(self):
    #     await self.disconnect()

    async def __enter__(self):
        """Experimental non-async context manager"""
        print("## __enter__")
        x = self.connect()
        print("## __enter__")
        return x
        # return await self.connect()

    async def __exit__(self, *_):
        """Experimental non-async context manager"""
        print("## __exit__")
        # TODO: should there be an await here? the static chcecker complains if not
        await self.disconnect()
        print("## __exit__")

    async def __aenter__(self):
        return await self.connect()

    async def __aexit__(self, *_):
        await self.disconnect()

    def url(self):
        path = Path("/") / Path(self.prefix) / Path(self.DEFAULT_PATH) / Path(self.client_id)
        protocol = "wss" if self.secure else "ws"
        url = urlunparse((protocol, self.server_address, str(path), "", "", "")) 
        return url

    async def connect(self):
        url = self.url()
        logger.info("connecting to %s", url)
        if self.secure:
            self.websocket = await connect(url, ssl=SSL_CONTEXT)
        else:
            self.websocket = await connect(url)
        return self

    async def disconnect(self):
        if self.websocket:
            await self.websocket.close()
        self.websocket = None

    async def set_colors(self, towers: dict[TowerLight, Sequence[float]]) -> None:
        """
        Set the colors for multiple towers

        Arguments:
        towers = dict of TowerLight enums pointing to the color to set it to, ex:
            {
                TowerLight.TOWER_0_LIGHT_TOTAL: (1.0, 1.0, 1.0),
                TowerLight.TOWER_3_LIGHT_TOTAL: (0.3, 0.4, 0.5),
            }
        """
        if not self.websocket:
            raise IlluminatrixClientError("not connected, call .connect() first")
        if not towers:
            return
        tower_dict = {}
        message = {
            "ack": self.ack.value,
            "towers": tower_dict,
        }
        for tower, color in towers.items():
            if not (0.0 <= color[0] <= 1.0 and
                0.0 <= color[1] <= 1.0 and
                0.0 <= color[2] <= 1.0):
                raise IlluminatrixClientError()
            tower_dict[tower.value] = color
        await self.websocket.send(json.dumps(message))

    async def set_color(self, towers: list | TowerLight, red: float, green: float, blue: float):
        """
        Set one or more towers the same color

        Arguments:
        towers = either a single TowerLight enum or a list of TowerLight enums
        red = how much red [0.0-1.0]
        green = how much green [0.0-1.0]
        blue = how much blue [0.0-1.0]
        """
        if not self.websocket:
            raise IlluminatrixClientError("not connected, call .connect() first")
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
        await self.websocket.send(json.dumps(message))
