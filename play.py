import argparse
import logging
import time

from bases.BaseSystem import BaseSystem
from components.TowerController import TowerController
from constants.constants import (
    ENVIRONMENT_CONTEXT,
    Environment,
    TowerEnum,
)
from systems.SystemFactory import SystemFactory
from utils.utils import find_game_classes

logger = logging.getLogger(__name__)
FORMAT = "[%(filename)s:%(lineno)s - %(funcName)15s() ] %(message)s"
logging.basicConfig(format=FORMAT, level=logging.WARNING)


def main():
    """Run an Illuminatrix game from the command line."""

    games = {c.__name__: c for c in find_game_classes("./games")}

    parser = argparse.ArgumentParser(
        prog="play",
        description=main.__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("environment", choices=[x.value for x in Environment], help="specify what environment the game will be running on")

    parser.add_argument("--id", required=False, help="id of the simulator (required if using web simulator)")

    parser.add_argument("--num-towers", type=int, default=len(TowerEnum), help="number of towers to run")

    parser.add_argument("--framerate", type=int, default=30, help="force maximum framerate, use 0 to run at maximum possible")

    parser.add_argument("game", choices=sorted(games.keys()), help="game to run")

    options = parser.parse_args()

    generic_context = {
        "num_towers": options.num_towers,
    }

    environment_context = ENVIRONMENT_CONTEXT[options.environment]
    context = {**generic_context, **environment_context}
    if options.environment in {Environment.WEB}:
        if not options.id:
            parser.error("running a web simulation requires --id")
        context["client_id"] = options.id

    systems: list[BaseSystem] = []

    # Instantiate the systems
    system_factory = SystemFactory(options.environment, context)
    systems = [
        system_factory.get_light_system(),
        system_factory.get_sound_system(),
        system_factory.get_input_system(),
    ]

    tower_controller = TowerController(system_factory)
    # TODO: this might pop, black will be better for production
    tower_controller.set_color((1.0, 1.0, 1.0))

    game_class = games[options.game]
    game = game_class(tower_controller)

    prev_time = time.time()
    game.first_frame_update()

    # Uncomment to see all the loggers, the long term intent is to learn
    # how to set individual logging levels on different parts of the code
    # logger_dict = logging.Logger.manager.loggerDict
    # for name in logger_dict:
    #     print("-->", name)

    # Start the systems
    for system in systems:
        system.startup()

    # Enter the game loop
    try:
        while True:
            shutdown_request = False

            curr_time = time.time()
            delta_ms = curr_time - prev_time
            prev_time = curr_time

            shutdown_request = game.update(delta_ms)

            for system in systems:
                system.update(delta_ms)

            for system in systems:
                system.render()

            if shutdown_request:
                break

            if options.framerate:
                i = 0
                while (time.time() - prev_time) < (1.0 / options.framerate):
                    i += 1
                    logger.debug("sleeping num times this frame: %d", i)
                    time.sleep(0.001)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt, quitting")
    finally:
        logger.info("Shutting down gracefully")
        time.sleep(0.1)
        for system in systems:
            logger.info("    Shutting down: %s", system)
            system.shutdown()
        time.sleep(0.1)


if __name__ == "__main__":
    main()
