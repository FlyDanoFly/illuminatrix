import argparse
import faulthandler
import logging
import signal
import time
from copy import copy
from pprint import pprint

from bases.BaseSystem import BaseSystem
from components.GameController import GameController
from components.TowerController import TowerController
from constants.constants import (
    ENVIRONMENT_CONTEXT,
    Environment,
    TowerEnum,
)
from managers.ManagerSingletonFactory import ManagerSingletonFactory
from systems.SystemSingletonFactory import SystemSingletonFactory
from utils import find_game_classes

logger = logging.getLogger(__name__)
FORMAT = "[%(filename)s:%(lineno)s - %(funcName)15s() ] %(message)s"
logging.basicConfig(format=FORMAT, level=logging.WARNING)

# Set up catching the kill signal
# Makes SIGTERM behave like Ctrl-C: default_int_handler is the built-in that raises KeyboardInterrupt
signal.signal(signal.SIGTERM, signal.default_int_handler)

# While the loop is hung, `kill -USR1 $(pgrep -f play.py)` dumps every
# thread's stack to stderr (the journal, under systemd). The stall warnings
# in the game loop only fire after a stall ends; this sees inside a live one.
faulthandler.register(signal.SIGUSR1)


GAMES_TO_SKIP_IN_PRODUCTION: set[str] = {
    "PrintGame",
    "DanoWhackAMole",
    "Blink",
    "PopCycle",
    "ColorCycle",
}

AMBIENT_GAME: str = "ColorCycle"

def main():
    """Run an Illuminatrix game from the command line."""

    print("*"*80)
    print("*"*80)
    print("*"*80)

    available_games = {c.__name__: c for c in find_game_classes("./games")}

    parser = argparse.ArgumentParser(
        prog="play",
        description=main.__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("environment", choices=[x.value for x in Environment], help="specify what environment the game will be running on")

    parser.add_argument("--showgamesonly", action="store_true", help="pretty print the games and exit")

    parser.add_argument("--id", required=False, help="id of the simulator (required if using web simulator)")

    parser.add_argument("--num-towers", type=int, default=len(TowerEnum), help="number of towers to run")

    parser.add_argument("--framerate", type=int, default=30, help="force maximum framerate, use 0 to run at maximum possible")

    parser.add_argument("--allgames", default=False, action="store_true", help="make all games available, not just production games")

    parser.add_argument("--debug", action="append", default=[], metavar="LOGGER", help="set the named logger to DEBUG, e.g. systems.concrete.SwitchInputSystem (repeatable; '' debugs everything)")

    parser.add_argument("games", nargs="*", choices=sorted(available_games.keys()), help="game to run")

    options = parser.parse_args()

    for logger_name in options.debug:
        logging.getLogger(logger_name).setLevel(logging.DEBUG)

    # Get the ambient game out of the available games
    ambient_game = available_games[AMBIENT_GAME]
    del available_games[AMBIENT_GAME]

    if not options.allgames:
        for game_to_skip in GAMES_TO_SKIP_IN_PRODUCTION:
            if game_to_skip in available_games:
                del available_games[game_to_skip]

    if options.showgamesonly:
        pprint(available_games)
        return

    environment_context = ENVIRONMENT_CONTEXT[options.environment]
    context = copy(environment_context)
    if options.environment in {Environment.WEB}:
        if not options.id:
            parser.error("running a web simulation requires --id")
        context["light_system"]["client_id"] = options.id

    # Instantiate the systems; the factory owns the per-frame update
    # order (transports first, then the systems)
    systems = SystemSingletonFactory(options.environment, context)
    active_systems: list[BaseSystem] = systems.get_active_systems()

    managers: ManagerSingletonFactory = ManagerSingletonFactory(systems)
    active_managers: list[BaseSystem] = [
        managers.get_effect_manager(),
    ]

    tower_controller = TowerController(systems, managers)
    # TODO: this might pop, black will be better for production
    tower_controller.set_color((1.0, 1.0, 1.0))

    # Uncomment to see all the logger names available to --debug
    # logger_dict = logging.Logger.manager.loggerDict
    # for name in logger_dict:
    #     print("-->", name)

    # Start the systems
    for system in active_systems:
        system.startup()

    for manager in active_managers:
        manager.startup()

    print("Sleep 2 to warmup to wait for the serial system to init")
    time.sleep(2)

    # All games are available unless a subset is specificed on the command line
    games_to_play = available_games.values()
    if options.games:
        games_to_play = {v for v in available_games.values() if v.__name__ in options.games}

    if not games_to_play:
        print("No games selected, did you mean to specify --allgames?")
        return

    game_controller = GameController(
        systems,
        managers,
        tower_controller,
        list(games_to_play),
        ambient_game,
    )

    # A frame that blows way past the ~33ms budget is a stall; warn with the
    # phase that ate the time so the journal names the subsystem to point
    # SIGUSR1/py-spy at next time. These warnings fire only after a stall
    # ends — a wedged loop can't log — hence the faulthandler hook above.
    STALL_WARN_SECS = 0.25

    phase_secs: dict[str, float] = {}

    def timed(name: str, fn, *args):
        phase_start = time.monotonic()
        result = fn(*args)
        phase_secs[name] = phase_secs.get(name, 0.0) + (time.monotonic() - phase_start)
        return result

    # Enter the game loop
    # monotonic: wall-clock time can jump (e.g. NTP sync on a Pi with no RTC),
    # which would corrupt delta_secs and fast-forward every game timer.
    # Captured immediately before the loop so startup time (including the
    # serial warmup sleep above) doesn't land in the first frame's delta.
    prev_time = time.monotonic()
    prev_work_secs = 0.0
    try:
        while True:
            curr_time = time.monotonic()
            delta_secs = curr_time - prev_time
            prev_time = curr_time

            if delta_secs - prev_work_secs > STALL_WARN_SECS:
                # Last frame's phases don't account for the gap, so it was
                # spent between frames: the framerate sleep, the OS
                # scheduler, or a signal handler
                logger.warning(
                    "Frame delta %.3fs but last frame's work was only %.3fs — stalled between frames",
                    delta_secs,
                    prev_work_secs,
                )

            phase_secs.clear()
            shutdown_request = timed("GameController.update", game_controller.update, delta_secs)

            for manager in active_managers:
                timed(f"{type(manager).__name__}.update", manager.update, delta_secs)

            for system in active_systems:
                timed(f"{type(system).__name__}.update", system.update, delta_secs)

            for manager in active_managers:
                timed(f"{type(manager).__name__}.render", manager.render)

            for system in active_systems:
                timed(f"{type(system).__name__}.render", system.render)

            prev_work_secs = time.monotonic() - curr_time
            if prev_work_secs > STALL_WARN_SECS:
                slow_name, slow_secs = max(phase_secs.items(), key=lambda kv: kv[1])
                logger.warning(
                    "Frame work took %.3fs, slowest phase was %s at %.3fs",
                    prev_work_secs,
                    slow_name,
                    slow_secs,
                )

            if shutdown_request:
                break

            if options.framerate:
                i = 0
                while (time.monotonic() - prev_time) < (1.0 / options.framerate):
                    i += 1
                    time.sleep(0.001)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt, quitting")
        print("KeyboardInterrupt, quitting")
    finally:
        print("Shutting down gracefully")
        logger.info("Shutting down gracefully")
        time.sleep(0.1)
        for manager in active_managers:
            logger.info("    Shutting down manager: %s", manager)
            manager.shutdown()
        for system in active_systems:
            logger.info("    Shutting down system: %s", system)
            system.shutdown()
        time.sleep(0.1)


if __name__ == "__main__":
    main()
