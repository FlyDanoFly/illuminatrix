import argparse
import time

from PrintGame import PrintGame
from SystemFactory import SystemFactory
# from WebsocketSimulation import WebsocketSimulation
# from SimulationSpeaker import SimulationSpeaker
from constants import ENVIRONMENT_CONTEXT, Environment, TowerEnum, tower_to_system_identifier
from Tower import Tower
from TowerController import TowerController


def main():
    """Run an Illuminatrix game from the command line."""
    parser = argparse.ArgumentParser(
        prog="play",
        description=main.__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("environment", choices=[x.value for x in Environment], help="specify what environment the game will be running on")

    parser.add_argument("--id", required=False, help="id of the simulator (required if using web simulator)")

    parser.add_argument("--num-towers", type=int, default=len(TowerEnum), help="number of towers to run")

    parser.add_argument("--framerate", type=int, default=30, help="force maximum framerate, use 0 to run at maximum possible")
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
        # web_sim = WebsocketSimulation(*context)
        # web_speak = SimulationSpeaker(None, d)
        # for d in range(7):
            # Tower(d, web_sim, web_speak)
   

    # Instantiate the stuff
    system_factory = SystemFactory(options.environment, context)
    light_system = system_factory.get_light_system()
    print(type(light_system), light_system)
    sound_system = system_factory.get_sound_system()
    print(type(sound_system), sound_system)
    towers = [Tower(tower_id, tower_to_system_identifier[tower_id], light_system, sound_system) for tower_id in TowerEnum]
    tower_controller = TowerController(towers)
    tower_controller.set_color((1.0, 1.0, 1.0))

    # TODO: instantiate the game
    game = PrintGame()

    prev_time = time.time()
    game.first_frame_update()

    # Enter the game loop
    try:
        while True:
            curr_time = time.time()
            delta_ms = curr_time - prev_time
            prev_time = curr_time

            game.update(delta_ms)
            light_system.update(delta_ms)
            sound_system.update(delta_ms)
            
            light_system.render()
            sound_system.render()

            if options.framerate:
                i = 0
                while (time.time() - prev_time) < (1.0 / options.framerate):
                    i += 1
                    print("sleeping", i)
                    time.sleep(0.001)
    except KeyboardInterrupt:
        print("KeyboardInterrupt, quitting")


if __name__ == "__main__":
    main()
