"""Walk every tower, saying its number and pulsing it its number of times.

Each tower gets a 2-second slot: its speaker says the tower's number
(the `test` sound bank) while its lights pulse tower-number times —
tower 1 holds solid, tower 2 pulses twice, and so on, so a wiring
permutation shows up as a light whose pulse count doesn't match the
number you hear (or the tower it's on). Pulses run from the tower's
full color down to about 1/3 intensity, with each low segment 1/3 the
length of a high; lows separate the highs, which is what lets tower 1
stay lit for its whole slot. Hues are spaced equidistantly around the
color wheel, tower 1 at red.

Stop the installation's play.py first (it owns the serial port, olad,
and the JACK server's ports), then:

    poetry run python experiments/tower_hardware_check.py

Cycles until ^C.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from constants.constants import LightPos, TowerEnum  # noqa: E402
from systems.concrete.dmx_controller import DmxController  # noqa: E402
from systems.concrete.EmbeddedLightSystem import EmbeddedLightSystem  # noqa: E402
from systems.concrete.JackSoundSystem import JackMixer, JackSoundSystem  # noqa: E402
from systems.concrete.serial_controller import SerialController  # noqa: E402
from utils import hsv_to_rgb  # noqa: E402

SOUND_BANK = "sound_banks/test"
# Opening the serial port resets the pad controller (DTR toggle), and
# traffic during its boot window can wedge it in the bootloader — pads
# dark, switches dead. play.py observes the same quiet period
SERIAL_WARMUP_SECS = 2.0
SLOT_SECS = 2.0  # each tower's turn: one spoken number, tower-number pulses
LOW_INTENSITY = 1.0 / 3.0  # pulse trough, as a fraction of the tower's full color
DOWN_TO_UP_RATIO = 1.0 / 3.0  # each low segment vs. the highs it separates
FRAME_SECS = 1.0 / 30.0

TOWERS = list(TowerEnum)
# Equidistant around the color wheel, wrap included: 1/7th apart
HUES = {tower_enum: i / len(TOWERS) for i, tower_enum in enumerate(TOWERS)}


def pulse_intensity(tower_number: int, secs_into_slot: float) -> float:
    """Intensity (LOW_INTENSITY..1.0) at secs_into_slot into a tower's slot.

    The slot holds tower_number highs separated by tower_number - 1
    lows, each low DOWN_TO_UP_RATIO the length of a high. The final
    high lands exactly on the end of the slot, so tower 1 (one high,
    no lows) is solid for the whole 2 seconds.
    """
    up_secs = SLOT_SECS / (tower_number + (tower_number - 1) * DOWN_TO_UP_RATIO)
    down_secs = up_secs * DOWN_TO_UP_RATIO
    return 1.0 if secs_into_slot % (up_secs + down_secs) < up_secs else LOW_INTENSITY


def main() -> None:
    serial_controller = SerialController()
    lights = EmbeddedLightSystem(
        dmx_controller=DmxController(),
        serial_controller=serial_controller,
    )
    sound = JackSoundSystem(mixer=JackMixer())
    lights.startup()  # refcounts the serial controller and starts DMX
    sound.startup()

    try:
        # The bank load counts toward the warmup, like play.py's preload
        warmup_start_secs = time.monotonic()
        sound.load_sound_bank(SOUND_BANK)
        warmup_remaining_secs = SERIAL_WARMUP_SECS - (time.monotonic() - warmup_start_secs)
        if warmup_remaining_secs > 0:
            print(f"Sleeping {warmup_remaining_secs:.1f}s to finish the serial warmup")
            time.sleep(warmup_remaining_secs)

        print("Each tower in turn says its number and pulses that many")
        print("times (tower 1 stays solid). Colors run red around the")
        print("wheel from tower 1. ^C to quit.")

        start_secs = time.monotonic()
        current_tower = None
        while True:
            cycle_secs = (time.monotonic() - start_secs) % (SLOT_SECS * len(TOWERS))
            tower_enum = TOWERS[int(cycle_secs // SLOT_SECS)]

            if tower_enum is not current_tower:
                current_tower = tower_enum
                number = tower_enum.value
                print(f"{tower_enum.name}: saying {number}, {number} pulse(s)")
                sound.play(f"say_the_number_{number}", [tower_enum])

            intensity = pulse_intensity(tower_enum.value, cycle_secs % SLOT_SECS)
            for other_enum in TOWERS:
                color = (
                    hsv_to_rgb(HUES[other_enum], 1.0, intensity)
                    if other_enum is tower_enum
                    else (0.0, 0.0, 0.0)
                )
                lights.set(other_enum, color, LightPos.All)

            serial_controller.update(FRAME_SECS)
            sound.update(FRAME_SECS)
            time.sleep(FRAME_SECS)
    except KeyboardInterrupt:
        print("Exiting")
    finally:
        sound.shutdown()
        lights.shutdown()


if __name__ == "__main__":
    main()
