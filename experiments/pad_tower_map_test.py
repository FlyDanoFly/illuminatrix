"""Which physical tower/pad shows which TowerEnum's color?

Sets a distinct static color per tower and holds it. An all-same-color
test (e.g. towers.set_color(RED)) cannot reveal an index permutation
between the enum order and the physical wiring — every pad looks right
no matter which byte block it reads. This can: each pad should match
its own tower, and each physical tower label should match the legend.

Stop the installation's play.py first (it owns the serial port and
olad), then:

    poetry run python experiments/pad_tower_map_test.py

^C to quit.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from constants.constants import LightPos, TowerEnum  # noqa: E402
from systems.concrete.dmx_controller import DmxController  # noqa: E402
from systems.concrete.EmbeddedLightSystem import EmbeddedLightSystem  # noqa: E402
from systems.concrete.serial_controller import SerialController  # noqa: E402

COLORS: dict[TowerEnum, tuple[str, tuple[float, float, float]]] = {
    TowerEnum.Tower_1: ("red", (1.0, 0.0, 0.0)),
    TowerEnum.Tower_2: ("green", (0.0, 1.0, 0.0)),
    TowerEnum.Tower_3: ("blue", (0.0, 0.0, 1.0)),
    TowerEnum.Tower_4: ("yellow", (1.0, 1.0, 0.0)),
    TowerEnum.Tower_5: ("cyan", (0.0, 1.0, 1.0)),
    TowerEnum.Tower_6: ("magenta", (1.0, 0.0, 1.0)),
    TowerEnum.Tower_7: ("white", (1.0, 1.0, 1.0)),
}

FRAME_SECS = 1.0 / 30.0


def main() -> None:
    serial_controller = SerialController()
    lights = EmbeddedLightSystem(
        dmx_controller=DmxController(),
        serial_controller=serial_controller,
    )
    lights.startup()  # refcounts the serial controller and starts DMX

    for tower_enum, (name, color) in COLORS.items():
        lights.set(tower_enum, color, LightPos.All)
        print(f"{tower_enum.name}: {name}")
    print("Each pad should match its own tower; each physical tower")
    print("label should match the legend above. ^C to quit.")

    try:
        while True:
            serial_controller.update(FRAME_SECS)
            time.sleep(FRAME_SECS)
    except KeyboardInterrupt:
        print("Exiting")
    finally:
        lights.shutdown()


if __name__ == "__main__":
    main()
