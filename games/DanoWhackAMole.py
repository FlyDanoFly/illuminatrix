import logging

from BaseGame import BaseStatemachineGame, ShouldStop
from statemachine import State

from components.TowerController import TowerController
from constants.colors import DULL_RAINBOW, RAINBOW

logger = logging.getLogger(__name__)

MOLES_TIME_BETWEEN_POPS_SEC = 1.0
MOLES_NUM_INTRODUCTION_FLASHES = 3  # This should be odd
MOLES_FAIL_FADE_SEC = 2.5


class DanoWhackAMoleGame(BaseStatemachineGame):
    # Game states
    introduction = State('Introduction', initial=True)
    playing = State('Playing')
    lost = State('Lost', final=True)

    # Game state transitions
    start_game = introduction.to(playing)
    add_mole = playing.to(playing) | playing.to(lost)  # This would be a loop to keep adding moles
    lost_game = playing.to(lost)

    def __init__(self, tower_controller: TowerController) -> None:
        super().__init__()

        self._towers = tower_controller
        self._available_towers = set(tower_controller)

        self._tower_color_low = dict(zip(tower_controller, DULL_RAINBOW, strict=True))
        self._tower_color_high = dict(zip(tower_controller, RAINBOW, strict=True))

        self._time_between_moles_popping_up_sec = MOLES_TIME_BETWEEN_POPS_SEC
        self._elapsed_time_secs = 0.0

    def first_frame_update(self) -> None:
        """Override this to set up a first frame before updating"""
        for tower_enum, tower in self._towers.items():
            tower.set_color(self._tower_color_low[tower_enum])

    def on_enter_introduction(self) -> None:
        """Handle the introduction state."""
        logger.info("Switching to the introduction state.")
        self._flashes_remaining = MOLES_NUM_INTRODUCTION_FLASHES
        self._elapsed_time_secs = 0.0
        logger.info("Welcome to Dano Whack-A-Mole! Press any tower to start.")

    def do_introduction(self, delta_ms) -> ShouldStop:
        """Handle the introduction state."""
        self._elapsed_time_secs += delta_ms
        if self._elapsed_time_secs < self._time_between_moles_popping_up_sec:
            return

        self._elapsed_time_secs -= self._time_between_moles_popping_up_sec
        if self._flashes_remaining == 0:
            self.start_game()
            return

        # Flash all towers
        self._flashes_remaining -= 1
        for tower_enum, tower in self._towers.items():
            if self._flashes_remaining % 2:
                tower.set_color(self._tower_color_low[tower_enum])
            else:
                tower.set_color(self._tower_color_high[tower_enum])

    def on_exit_introduction(self) -> None:
        """Handle the playing state."""
        logger.info("Switching to the playing state.")
        self._elapsed_time_secs = 0.0
        self._available_towers = set(self._towers)
        for tower_enum, tower in self._towers.items():
            tower.set_color(self._tower_color_low[tower_enum])

    def on_add_mole(self) -> None:
        """Handle adding a mole."""
        if not self._available_towers:
            logger.info("No more moles available. You lost!")
            self.lost_game()
            return

        # Randomly select a tower to pop a mole
        tower_enum = self._available_towers.pop()
        tower = self._towers[tower_enum]
        tower.set_color(self._tower_color_high[tower_enum])
        # tower.play_sound("boom")
        logger.info(f"Mole popped at {tower_enum.name}!")

    def do_playing(self, delta_ms) -> ShouldStop:
        """Handle the playing state."""
        self._elapsed_time_secs += delta_ms

        if self._towers.any_switch_pressed():
            for tower_enum, tower in self._towers.items():
                if tower.is_switch_pressed():
                    if tower_enum not in self._available_towers:
                        tower.set_color(self._tower_color_low[tower_enum])
                        self._available_towers.add(tower_enum)
                        logger.info(f"Whacked mole at {tower_enum.name}!")
                    else:
                        # TODO: need to detect switch transitions, not just "on-ness", for ignore bad presses
                        pass
                        # logger.warning(f"Whack failed at {tower_enum.name}!")
                        # self.lost_game()

        if self._elapsed_time_secs >= self._time_between_moles_popping_up_sec:
            self._elapsed_time_secs -= self._time_between_moles_popping_up_sec
            self.add_mole()
            return

    def on_enter_lost(self) -> None:
        """Handle the lost state."""
        logger.info("You lost! Game over.")
        for tower in self._towers.values():
            tower.set_color((1.0, 0.0, 0.0))
        self._elapsed_time_secs = 0.0

    def do_lost(self, delta_ms: float) -> ShouldStop:
        """Handle the lost state."""
        self._elapsed_time_secs += delta_ms
        red = max(0.0, 1.0 - (self._elapsed_time_secs / (MOLES_FAIL_FADE_SEC)))
        self._towers.set_color((red, 0.0, 0.0))
        return self._elapsed_time_secs >= MOLES_FAIL_FADE_SEC
