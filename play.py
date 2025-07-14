import argparse
import logging
import time
from copy import copy

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


GAMES_TO_SKIP_IN_PRODUCTION: set[str] = {
    "PrintGame",
    "DanoWhackAMole",
    "Blink",
    "PopCycle",
    "ColorCycle",
}


def main():
    """Run an Illuminatrix game from the command line."""

    available_games = {c.__name__: c for c in find_game_classes("./games")}

    parser = argparse.ArgumentParser(
        prog="play",
        description=main.__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("environment", choices=[x.value for x in Environment], help="specify what environment the game will be running on")

    parser.add_argument("--id", required=False, help="id of the simulator (required if using web simulator)")

    parser.add_argument("--num-towers", type=int, default=len(TowerEnum), help="number of towers to run")

    parser.add_argument("--framerate", type=int, default=30, help="force maximum framerate, use 0 to run at maximum possible")

    parser.add_argument("--allgames", default=False, action="store_true", help="make all games available, not just production games")

    parser.add_argument("games", nargs="*", choices=sorted(available_games.keys()), help="game to run")

    options = parser.parse_args()

    if not options.allgames:
        print(available_games)
        print("==")
        for game_to_skip in GAMES_TO_SKIP_IN_PRODUCTION:
            if game_to_skip in available_games:
                del available_games[game_to_skip]
        print(available_games)

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

    prev_time = time.time()

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

    print("sleep 2 to warmup")
    time.sleep(2)

    # All games are available unless a subset is specificed on the command line
    games_to_play = available_games.values()
    if options.games:
        games_to_play = {v for v in available_games.values() if v.__name__ in options.games}
    else:
        print("*"*80)
        print("Going into controller mode with all games available")
        print("*"*80)

    game_controller = GameController(
        systems,
        managers,
        tower_controller,
        list(games_to_play),
    )

    # Enter the game loop
    try:
        while True:
            shutdown_request = False

            curr_time = time.time()
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
                # print("BREA")
                i = 0
                while (time.time() - prev_time) < (1.0 / options.framerate):
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
