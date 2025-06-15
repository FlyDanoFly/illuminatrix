import argparse
import logging
import time

from BaseSystem import BaseSystem
from constants import (
    ENVIRONMENT_CONTEXT,
    Environment,
    TowerEnum,
    tower_to_system_identifier,
)
from SystemFactory import SystemFactory
from Tower import Tower
from TowerController import TowerController
from utils import find_game_classes

logger = logging.getLogger(__name__)
FORMAT = "[%(filename)s:%(lineno)s - %(funcName)15s() ] %(message)s"
logging.basicConfig(format=FORMAT, level=logging.INFO)

def main():
    """Run an Illuminatrix game from the command line."""

    games = {c.__name__: c for c in find_game_classes(".")}

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
    if options.environment in {Environment.EXTERNAL, Environment.LOCAL}:
        if not options.id:
            parser.error("running a web simulation requires --id")
            return
        context["client_id"] = options.id

    systems: list[BaseSystem] = []

    # Instantiate the stuff
    system_factory = SystemFactory(options.environment, context)
    light_system = system_factory.get_light_system()
    systems.append(light_system)
    sound_system = system_factory.get_sound_system()
    systems.append(sound_system)

    # TODO: Turn the tower generator into a factory
    towers = [
        Tower(tower_id, tower_to_system_identifier[tower_id], light_system, sound_system)
        for tower_id in TowerEnum
    ]
    tower_controller = TowerController(towers)
    tower_controller.set_color((1.0, 1.0, 1.0))

    # TODO: instantiate the game
    game_class = games[options.game]
    game = game_class(tower_controller)

    prev_time = time.time()
    game.first_frame_update()

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

            light_system.update(delta_ms)
            sound_system.update(delta_ms)

            light_system.render()
            sound_system.render()

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
        for system in systems:
            logger.info("    Shutting down: %s", system)
            system.shutdown()


if __name__ == "__main__":
    main()
