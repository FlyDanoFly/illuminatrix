import logging
import time
from pathlib import Path
from typing import Sequence

from statemachine import State, StateMachine

from bases.BaseGame import BaseGame
from bases.InputSystem import InputSystem
from bases.LightSystem import LightSystem
from bases.SoundSystem import SoundSystem
from bases.StateMachineMixin import StateMachineMixin
from components.ShowProfile import NORMAL_PROFILE, QUIET_PROFILE, ShowProfile
from components.TowerController import TowerController
from constants.colors import WHITE
from constants.constants import ControllerSwitchEnum, ShouldStop
from managers.EffectManager import EffectManager
from managers.ManagerSingletonFactory import ManagerSingletonFactory
from systems.SystemSingletonFactory import SystemSingletonFactory
from utils.utils import cycle

logger = logging.getLogger(__name__)

# If no input is received in this time frame, the game is cancelled
GAME_CONTROLLER_GAME_IDLE_TIMEOUT_SECS = 5 * 60
# If no input is received in this time frame, go into ambient mode
GAME_CONTROLLER_SELECT_IDLE_TIMEOUT_SECS = 2 * 60
# Holding NEXT_GAME and RESET together this long toggles the quiet-hours
# profile; both must be released before another toggle can arm
QUIET_HOURS_HOLD_SECS = 10.0


class GameController(StateMachineMixin, StateMachine):
    """
    A simple controller for the Illumintrix games.

    The controller has three buttons: Start, Select, Reset.

    It starts out await input from the Start or Select button.
    Select will cycle through the available games
    Start will start the game
    When the game is done it will go back to await input

    While the game is going, only the reset butten is active. If it is pressed
    for x time it will stop the current game and go back to await input mode.

    Holding NEXT_GAME and RESET together for QUIET_HOURS_HOLD_SECS toggles
    the quiet-hours show profile (lower master volume/brightness, restricted
    game roster); the active profile persists across restarts via a marker
    file.
    """
    # The selection/instructions sounds are the controller's own bank,
    # not any game's; play.py includes it in the boot preload
    INTRO_SOUND_BANK = "sound_banks/intro_and_instructions"

    initial_state = State("initial_state", initial=True)
    await_input = State("await_input")
    instructions = State("instructions")
    playing_game = State("playing_game")
    cancel = State("cancel")

    start_selection = initial_state.to(await_input) | playing_game.to(await_input) | cancel.to(await_input)
    next_option = await_input.to(await_input)
    give_instructions = await_input.to(instructions)
    start_game = initial_state.to(playing_game) | instructions.to(playing_game) | await_input.to(playing_game)
    cancel_game = playing_game.to(cancel)

    def __init__(
        self,
        system_singleton_factory: SystemSingletonFactory,
        manager_singleton_factory: ManagerSingletonFactory,
        tower_controller: TowerController,
        game_classes: Sequence[type[BaseGame]],
        ambient_class: type[BaseGame],
        select_idle_timeout_secs: float = GAME_CONTROLLER_SELECT_IDLE_TIMEOUT_SECS,
        normal_profile: ShowProfile = NORMAL_PROFILE,
        quiet_profile: ShowProfile = QUIET_PROFILE,
        quiet_state_file: Path | None = None,
    ):
        """
        Args
            game_classes: game controller will instantiate them as needed
        """
        super().__init__()

        self._system_singleton_factory: SystemSingletonFactory = system_singleton_factory
        self._lights: LightSystem = system_singleton_factory.get_light_system()
        self._inputs: InputSystem = system_singleton_factory.get_input_system()
        self._sounds: SoundSystem = system_singleton_factory.get_sound_system()

        self._manager_singleton_factory: ManagerSingletonFactory = manager_singleton_factory
        self._effects: EffectManager = manager_singleton_factory.get_effect_manager()

        self._towers: TowerController = tower_controller

        self._all_game_classes: list[type[BaseGame]] = list(game_classes)
        self._normal_profile: ShowProfile = normal_profile
        self._quiet_profile: ShowProfile = quiet_profile
        self._quiet_state_file: Path | None = quiet_state_file
        self._quiet_hours: bool = self._read_quiet_hours_state()
        self._quiet_hold_secs: float = 0.0
        self._quiet_hold_armed: bool = True

        # Sets _game_classes (the profile's roster) and the master
        # volume/brightness before any state announces or lights up
        self._apply_profile(self._active_profile)
        self._game_cycler = cycle(self._game_classes)
        self._selected_game: type[BaseGame] = self._game_cycler.__next__()

        self._ambient_class: type[BaseGame] = ambient_class
        self._playing_ambient: bool = False

        self._game_idle_secs: float = 0.0
        self._controller_input_idle_secs: float = 0.0
        self._select_idle_timeout_secs: float = select_idle_timeout_secs

        # Special case: if there is only one game passed in just use that, don't choose
        if len(game_classes) == 1:
            self._single_game = True
            self.start_game()
        else:
            self._single_game = False
            self.start_selection()

    def update(self, delta_secs: float) -> ShouldStop:
        # The quiet-hours hold is watched here, above the state machine,
        # so it works from selection, instructions, a game, or ambient
        self._update_quiet_hours_hold(delta_secs)
        return super().update(delta_secs)

    # ------------------------------------------------------------
    # Quiet hours

    @property
    def _active_profile(self) -> ShowProfile:
        return self._quiet_profile if self._quiet_hours else self._normal_profile

    def _update_quiet_hours_hold(self, delta_secs: float) -> None:
        both_held = (
            self._inputs.is_controller_switch_pressed(ControllerSwitchEnum.NEXT_GAME)
            and self._inputs.is_controller_switch_pressed(ControllerSwitchEnum.RESET)
        )
        if not both_held:
            self._quiet_hold_secs = 0.0
            self._quiet_hold_armed = True
            return
        self._quiet_hold_secs += delta_secs
        if self._quiet_hold_armed and self._quiet_hold_secs >= QUIET_HOURS_HOLD_SECS:
            # Disarm until both buttons release, so a 20-second hold
            # toggles once instead of bouncing straight back
            self._quiet_hold_armed = False
            self._toggle_quiet_hours()

    def _toggle_quiet_hours(self) -> None:
        self._quiet_hours = not self._quiet_hours
        self._apply_profile(self._active_profile)
        self._persist_quiet_hours()
        # The buttons' single-press actions have already run at the start
        # of the hold (RESET cancels a game, NEXT_GAME ejects ambient), so
        # this normally fires from await_input with the intro bank loaded
        # and the cue plays; from another bank it degrades to a WARNING
        self._towers.play_sound(
            "quiet_hours_on" if self._quiet_hours else "quiet_hours_off",
            volume=0.25,
        )
        if self.current_state == self.await_input:
            # Re-announce from the new roster, so START can't launch a
            # selection the profile no longer allows
            self.next_option()
        elif self.current_state == self.playing_game and not self._playing_ambient:
            # Reachable only when the hold began before the game did
            # (e.g. held through the instructions); ambient stays up
            self.cancel_game()

    def _apply_profile(self, profile: ShowProfile) -> None:
        allowed = profile.allowed_games
        if allowed is None:
            games = list(self._all_game_classes)
        else:
            games = [g for g in self._all_game_classes if g.__name__ in allowed]
            if not games:
                logger.error(
                    "Profile '%s' allows none of this run's games (%s) — keeping the full roster",
                    profile.name, ", ".join(sorted(allowed)),
                )
                games = list(self._all_game_classes)
        self._game_classes: Sequence[type[BaseGame]] = games
        self._game_cycler = cycle(self._game_classes)
        self._sounds.set_master_volume(profile.master_volume)
        self._lights.set_master_brightness(profile.master_brightness)
        logger.info(
            "Show profile '%s': volume %.2f, brightness %.2f, games: %s",
            profile.name, profile.master_volume, profile.master_brightness,
            ", ".join(g.__name__ for g in games),
        )

    def _read_quiet_hours_state(self) -> bool:
        if self._quiet_state_file is None:
            return False
        try:
            return self._quiet_state_file.exists()
        except OSError:
            logger.exception(
                "Couldn't read quiet-hours state %s — booting in the normal profile",
                self._quiet_state_file,
            )
            return False

    def _persist_quiet_hours(self) -> None:
        """Marker file: present means quiet hours, absent means normal —
        so a restart (systemd, power blip) comes back in the same profile.
        Failures cost persistence, never the show."""
        if self._quiet_state_file is None:
            return
        try:
            if self._quiet_hours:
                self._quiet_state_file.write_text(
                    "Quiet-hours profile is active; delete this file to boot into the normal profile.\n"
                )
            else:
                self._quiet_state_file.unlink(missing_ok=True)
        except OSError:
            logger.exception(
                "Couldn't persist quiet-hours state to %s — a restart will boot in the normal profile",
                self._quiet_state_file,
            )

    # ------------------------------------------------------------
    # State: initial_state

    def on_start_selection(self) -> None:
        self._towers.set_color(WHITE)
        # Fresh cycler only — entering await_input advances it, so
        # consuming one here would skip the first game
        self._game_cycler = cycle(self._game_classes)
        self._towers.load_sound_bank(self.INTRO_SOUND_BANK)

    # ------------------------------------------------------------
    # State: await_input

    def on_enter_await_input(self) -> None:
        self._selected_game = self._game_cycler.__next__()
        logger.info("Selected game: %s", self._selected_game.__name__)
        self._towers.play_sound(self._selected_game.__name__, volume=0.25)
        self._controller_input_idle_secs = 0.0

    def do_await_input(self, delta_secs: float) -> ShouldStop:
        if self._towers.is_any_switch_pressed():
            self._controller_input_idle_secs = 0.0
        else:
            self._controller_input_idle_secs += delta_secs
            if self._controller_input_idle_secs > self._select_idle_timeout_secs:
                logger.info(
                    "No input for %.0f secs — starting ambient %s",
                    self._controller_input_idle_secs, self._ambient_class.__name__)
                self._selected_game = self._ambient_class
                self.start_game()
                return

        if self._inputs.did_controller_switch_transition_down(ControllerSwitchEnum.START):
            self.give_instructions()
        elif self._inputs.did_controller_switch_transition_down(ControllerSwitchEnum.NEXT_GAME):
            # TODO: feedback another option has been selected
            self.next_option()

    # ------------------------------------------------------------
    # State: instructions

    def on_enter_instructions(self) -> None:
        self._towers.play_sound(f"{self._selected_game.__name__}__instructions", volume=0.25)

    def do_instructions(self, delta_secs: float) -> ShouldStop:
        if self._towers.are_any_sounds_playing():
            # Presume it is playing the instructions or finishing the game, skip
            time.sleep(0.01)
            return
        else:
            self.start_game()

    # ------------------------------------------------------------
    # State: playing_game

    def on_enter_playing_game(self) -> None:
        # Identity, not isinstance: a future selectable game subclassing
        # the ambient class must not inherit ambient semantics (no idle
        # timeout, buttons eject to selection)
        self._playing_ambient = self._selected_game is self._ambient_class
        self._current_game = self._selected_game(self._towers)
        self._current_game.first_frame_update()
        logger.info("Starting game: %s", type(self._current_game).__name__)

        self._game_idle_secs = 0.0

    def do_playing_game(self, delta_secs: float) -> ShouldStop:
        is_done = False

        if self._towers.is_any_switch_pressed():
            self._game_idle_secs = 0.0
        else:
            self._game_idle_secs += delta_secs
            if self._game_idle_secs > GAME_CONTROLLER_GAME_IDLE_TIMEOUT_SECS and not self._playing_ambient:
                logger.info("No player input for %.0f secs — cancelling game", self._game_idle_secs)
                self.cancel_game()
                return

        if self._inputs.did_controller_switch_transition_down(ControllerSwitchEnum.RESET):
            logger.info("Reset pressed")
            is_done = True
        elif self._playing_ambient and (
                self._inputs.did_controller_switch_transition_down(ControllerSwitchEnum.START) or
                self._inputs.did_controller_switch_transition_down(ControllerSwitchEnum.NEXT_GAME)
            ):
            # Any controller button in ambient mode returns to selection
            logger.info("Controller button pressed — leaving ambient")
            is_done = True
        else:
            is_done = self._current_game.update(delta_secs)

        if self._single_game:
            # Single game, can exit the program
            return is_done
        elif is_done:
            # Multiple games specified, loop forever
            self.cancel_game()

    # ------------------------------------------------------------
    # State: cancel

    def do_cancel(self, delta_secs: float):
        logger.info("Stopping %s — returning to selection", type(self._current_game).__name__)
        del self._current_game
        self._sounds.stop_all()
        self._effects.stop_all()
        self.start_selection()
