import argparse
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

    parser.add_argument("games", nargs="*", choices=sorted(available_games.keys()), help="game to run")

    options = parser.parse_args()

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

    # Instantiate the systems
    systems = SystemSingletonFactory(options.environment, context)
    active_systems: list[BaseSystem] = [
        systems.get_light_system(),
        systems.get_sound_system(),
        systems.get_input_system(),
    ]

    managers: ManagerSingletonFactory = ManagerSingletonFactory(systems)
    active_managers: list[BaseSystem] = [
        managers.get_effect_manager(),
    ]

    tower_controller = TowerController(systems, managers)
    # TODO: this might pop, black will be better for production
    tower_controller.set_color((1.0, 1.0, 1.0))

    # Uncomment to see all the loggers, the long term intent is to learn
    # how to set individual logging levels on different parts of the code
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

    # Enter the game loop
    # monotonic: wall-clock time can jump (e.g. NTP sync on a Pi with no RTC),
    # which would corrupt delta_secs and fast-forward every game timer.
    # Captured immediately before the loop so startup time (including the
    # serial warmup sleep above) doesn't land in the first frame's delta.
    prev_time = time.monotonic()
    try:
        while True:
            shutdown_request = False

            curr_time = time.monotonic()
            delta_secs = curr_time - prev_time
            prev_time = curr_time

            shutdown_request = game_controller.update(delta_secs)

            for manager in active_managers:
                manager.update(delta_secs)

            for system in active_systems:
                system.update(delta_secs)

            for manager in active_managers:
                manager.render()

            for system in active_systems:
                system.render()

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
