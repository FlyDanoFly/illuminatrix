import time
from typing import Sequence

from statemachine import State, StateMachine

from bases.BaseGame import BaseGame
from bases.InputSystem import InputSystem
from bases.LightSystem import LightSystem
from bases.SoundSystem import SoundSystem
from bases.StateMachineMixin import StateMachineMixin
from components.TowerController import TowerController
from constants.colors import WHITE
from constants.constants import ControllerSwitchEnum, ShouldStop
from managers.EffectManager import EffectManager
from managers.ManagerSingletonFactory import ManagerSingletonFactory
from systems.SystemSingletonFactory import SystemSingletonFactory
from utils.utils import cycle


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
    """
    initial_state = State("initial_state", initial=True)
    await_input = State("await_input")
    instructions = State("instructions")
    playing_game = State("playing_game")
    cancel = State("cancel")

    start_selection = initial_state.to(await_input) | playing_game.to(await_input) | cancel.to(await_input)
    next_option = await_input.to(await_input)
    give_instructions = await_input.to(instructions)
    start_game = initial_state.to(playing_game) | instructions.to(playing_game)
    cancel_game = playing_game.to(cancel)

    def __init__(
        self,
        system_singleton_factory: SystemSingletonFactory,
        manager_singleton_factory: ManagerSingletonFactory,
        tower_controller: TowerController,
        game_classes: Sequence[type[BaseGame]],
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

        self._game_classes: Sequence[type[BaseGame]] = game_classes
        self._game_cycler = cycle(self._game_classes)
        self._selected_game: type[BaseGame] = self._game_cycler.__next__()

        # Special case: if there is only one game passed in just use that, don't choose
        if len(game_classes) == 1:
            self._single_game = True
            self.start_game()
        else:
            self._single_game = False
            self.start_selection()

    # ------------------------------------------------------------
    # State: initial_state

    def on_start_selection(self) -> None:
        self._towers.set_color(WHITE)
        self._game_cycler = cycle(self._game_classes)
        self._selected_game = self._game_cycler.__next__()
        self._towers.load_sound_bank("sound_banks/intro_and_instructions")

    # ------------------------------------------------------------
    # State: await_input

    def on_enter_await_input(self) -> None:
        self._selected_game = self._game_cycler.__next__()
        print("Currently selected game:", self._selected_game)
        self._towers.play_sound(self._selected_game.__name__, volume=0.25)

    def do_await_input(self, delta_secs: float) -> ShouldStop:
        if self._inputs.did_controller_switch_transition_down(ControllerSwitchEnum.START):
            self.give_instructions()
        elif self._inputs.did_controller_switch_transition_down(ControllerSwitchEnum.NEXT_GAME):
            # TODO: feedback another option has been selected
            self.next_option()

    # ------------------------------------------------------------
    # State: instructions

    def on_enter_instructions(self) -> None:
        self._towers.play_sound(f"{self._selected_game.__name__}__instructions", volume=0.25)

    def do_instructions(self, delta_ms: float) -> ShouldStop:
        if self._towers.are_any_sounds_playing():
            # Presume it is playing the instructions or finishing the game, skip
            time.sleep(0.01)
            return
        else:
            self.start_game()

    # ------------------------------------------------------------
    # State: playing_game

    def on_enter_playing_game(self) -> None:
        self._current_game = self._selected_game(self._towers)
        self._current_game.first_frame_update()
        print("Starting game:", self._current_game.__class__)

    def do_playing_game(self, delta_ms: float) -> ShouldStop:
        is_done = False

        if self._inputs.did_controller_switch_transition_down(ControllerSwitchEnum.RESET):
            is_done = True
        else:
            is_done = self._current_game.update(delta_ms)

        if self._single_game:
            # Single game, can exit the program
            return is_done
        elif is_done:
            # Multiple games specified, loop forever
            self.cancel_game()

    # ------------------------------------------------------------
    # State: cancel
    
    def do_cancel(self, delta_secs: float):
        print("Cancel, changing fresh to getting input")
        del self._current_game
        self._sounds.stop_all()
        self._effects.stop_all()
        self.start_selection()
