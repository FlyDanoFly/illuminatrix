import argparse
import faulthandler
import logging
import signal
import time
from copy import copy
from pathlib import Path
from pprint import pprint

from bases.BaseSystem import BaseSystem
from components.GameController import (
    GAME_CONTROLLER_SELECT_IDLE_TIMEOUT_SECS,
    GameController,
)
from components.ShowProfile import (
    DEFAULT_QUIET_BRIGHTNESS,
    DEFAULT_QUIET_GAMES,
    DEFAULT_QUIET_VOLUME,
    ShowProfile,
)
from components.TowerController import TowerController
from constants.constants import (
    ENVIRONMENT_CONTEXT,
    Environment,
    TowerEnum,
)
from managers.ManagerSingletonFactory import ManagerSingletonFactory
from systems.concrete.NullSoundSystem import NullSoundSystem
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

# Outside the repo so a desk checkout and the live install don't share
# it through git; presence of the file means quiet hours is active
QUIET_HOURS_STATE_FILE = Path.home() / ".illuminatrix_quiet_hours"

def main():
    """Run an Illuminatrix game from the command line."""

    print("*"*80)
    print("*"*80)
    print("*"*80)

    available_games = {c.__name__: c for c in find_game_classes("./games")}
    # Every discovered game, captured before the ambient/production
    # filters below whittle available_games down
    all_game_names = set(available_games)

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

    parser.add_argument("--debug", action="append", default=[], metavar="LOGGER", help="set the named logger to DEBUG (repeatable; '' debugs everything; see --list-loggers for names)")

    parser.add_argument("--list-loggers", action="store_true", help="print the logger names available to --debug and exit")

    parser.add_argument("--no-sound", action="store_true", help="disable audio entirely (no JACK server needed)")

    parser.add_argument("--ambient-idle-secs", type=float, default=GAME_CONTROLLER_SELECT_IDLE_TIMEOUT_SECS, help="seconds without input in selection mode before dropping to the ambient game")

    parser.add_argument("--quiet-volume", type=float, default=DEFAULT_QUIET_VOLUME, help="master volume (0.0-1.0) while the quiet-hours profile is active")

    parser.add_argument("--quiet-brightness", type=float, default=DEFAULT_QUIET_BRIGHTNESS, help="master light brightness (0.0-1.0) while the quiet-hours profile is active")

    parser.add_argument("--quiet-games", nargs="*", default=list(DEFAULT_QUIET_GAMES), metavar="GAME", help="games selectable while the quiet-hours profile is active; no names disables all games (ambient only, pads and control panel ignored)")

    parser.add_argument("games", nargs="*", choices=sorted(available_games.keys()), help="game to run")

    options = parser.parse_args()

    if options.list_loggers:
        # Everything is imported by now, so the registry is complete.
        # Before the --debug loop: getLogger() CREATES missing loggers,
        # so listing afterwards would show a typo'd --debug name as real
        for name in sorted(logging.Logger.manager.loggerDict):
            print(name)
        return

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

    # All games are available unless a subset is specified on the command
    # line. Validated before any system starts up, so a typo'd game name
    # doesn't leave started systems behind
    games_to_play = available_games.values()
    if options.games:
        games_to_play = {v for v in available_games.values() if v.__name__ in options.games}

    if not games_to_play:
        print("No games selected, did you mean to specify --allgames?")
        return

    # Same deal as game names: catch a typo'd quiet flag before any
    # system starts up. Names are checked against every discovered game
    # (not just this run's) so a dev run with a subset still accepts the
    # production quiet roster
    if not 0.0 <= options.quiet_volume <= 1.0:
        parser.error(f"--quiet-volume must be 0.0-1.0, got {options.quiet_volume}")
    if not 0.0 <= options.quiet_brightness <= 1.0:
        parser.error(f"--quiet-brightness must be 0.0-1.0, got {options.quiet_brightness}")
    unknown_quiet_games = set(options.quiet_games) - all_game_names
    if unknown_quiet_games:
        parser.error(f"unknown --quiet-games: {', '.join(sorted(unknown_quiet_games))}")

    quiet_profile = ShowProfile(
        name="quiet hours",
        master_volume=options.quiet_volume,
        master_brightness=options.quiet_brightness,
        allowed_games=frozenset(options.quiet_games),
    )

    # Instantiate the systems; the factory owns the per-frame update
    # order (transports first, then the systems)
    systems = SystemSingletonFactory(
        options.environment,
        context,
        sound_system_override=NullSoundSystem if options.no_sound else None,
    )
    active_systems: list[BaseSystem] = systems.get_active_systems()

    managers: ManagerSingletonFactory = ManagerSingletonFactory(systems)
    active_managers: list[BaseSystem] = [
        managers.get_effect_manager(),
    ]

    tower_controller = TowerController(systems, managers)
    # TODO: this might pop, black will be better for production
    tower_controller.set_color((1.0, 1.0, 1.0))

    # Start the systems
    for system in active_systems:
        system.startup()

    for manager in active_managers:
        manager.startup()

    # Preload every sound bank this run's games declare (plus the game
    # controller's own selection sounds), so entering a game switches
    # banks from cache instead of stalling the loop on a multi-second
    # decode — the ambient bank measured 4.3s
    sound_banks = {
        game.SOUND_BANK
        for game in [*games_to_play, ambient_game]
        if game.SOUND_BANK
    }
    sound_banks.add(GameController.INTRO_SOUND_BANK)
    systems.get_sound_system().preload_sound_banks(sorted(sound_banks))
    # No serial warmup here: SerialController holds its own boot-quiet
    # window after connect, riding the disconnect degrade path — with a
    # multi-second preload it has usually expired before the first frame

    game_controller = GameController(
        systems,
        managers,
        tower_controller,
        list(games_to_play),
        ambient_game,
        select_idle_timeout_secs=options.ambient_idle_secs,
        quiet_profile=quiet_profile,
        quiet_state_file=QUIET_HOURS_STATE_FILE,
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
