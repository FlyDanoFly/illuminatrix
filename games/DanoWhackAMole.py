import logging

from statemachine import State

from bases import BaseStateMachineGame
from components.TowerController import TowerController
from constants.colors import DULL_RAINBOW, RAINBOW
from constants.constants import ShouldStop

logger = logging.getLogger(__name__)

MASTER_VOLUME = 1.0

MOLES_TIME_BETWEEN_POPS_SEC = 1.0
MOLES_NUM_INTRODUCTION_FLASHES = 3  # This should be odd
MOLES_FAIL_FADE_SEC = 2.5


class DanoWhackAMole(BaseStateMachineGame):
    # Game states
    start = State("Start", initial=True)
    introduction = State('Introduction')
    playing = State('Playing')
    lost = State('Lost', final=True)

    # Game state transitions
    begin = start.to(introduction)
    start_game = introduction.to(playing)
    add_mole = playing.to(playing) | playing.to(lost)  # This would be a loop to keep adding moles
    lost_game = playing.to(lost)

    def __init__(self, tower_controller: TowerController) -> None:
        super().__init__(tower_controller)

        self._towers = tower_controller
        self._towers.load_sound_bank("sound_banks/dano_whack_a_mole_1/")

        self._available_towers = set(tower_controller)

        self._tower_color_low = dict(zip(tower_controller, DULL_RAINBOW, strict=True))
        self._tower_color_high = dict(zip(tower_controller, RAINBOW, strict=True))

        self._time_between_moles_popping_up_sec = MOLES_TIME_BETWEEN_POPS_SEC
        self._elapsed_time_secs = 0.0

    def first_frame_update(self) -> None:
        """Override this to set up a first frame before updating"""
        for tower_enum, tower in self._towers.items():
            tower.set_color(self._tower_color_low[tower_enum])
        self.begin()

    def on_enter_introduction(self) -> None:
        """Handle the introduction state."""
        logger.info("Switching to the introduction state.")
        self._flashes_remaining = MOLES_NUM_INTRODUCTION_FLASHES
        self._elapsed_time_secs = 0.0
        logger.info("Welcome to Dano Whack-A-Mole! Press any tower to start.")
        for tower_enum, tower in self._towers.items():
            sound_key = f"simon_intro_c{tower_enum.value}"
            tower.play_sound(sound_key)
            print("*"*20, sound_key)

    def do_introduction(self, delta_secs) -> ShouldStop:
        """Handle the introduction state."""
        if self._towers.are_any_sounds_playing():
            return

        self._elapsed_time_secs += delta_secs
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
        tower.play_sound("squeal1", volume=MASTER_VOLUME)
        logger.info("Mole popped at %s!", tower_enum.name)

    def do_playing(self, delta_secs) -> ShouldStop:
        """Handle the playing state."""
        self._elapsed_time_secs += delta_secs

        for tower_enum, tower in self._towers.items():
            if tower.did_switch_transition_down():
                if tower_enum not in self._available_towers:
                    tower.set_color(self._tower_color_low[tower_enum])
                    self._available_towers.add(tower_enum)
                    logger.info("Whacked mole at %s!", tower_enum.name)
                else:
                    logger.info("Whack failed at %s!", tower_enum.name)
                    self.lost_game()

        if self._elapsed_time_secs >= self._time_between_moles_popping_up_sec:
            self._elapsed_time_secs -= self._time_between_moles_popping_up_sec
            self.add_mole()
            return

    def on_enter_lost(self) -> None:
        """Handle the lost state."""
        logger.info("You lost! Game over.")
        self._towers.play_sound("long_siren", volume=MASTER_VOLUME)
        for tower in self._towers.values():
            tower.set_color((1.0, 0.0, 0.0))
        self._elapsed_time_secs = 0.0

    def do_lost(self, delta_secs: float) -> ShouldStop:
        """Handle the lost state."""
        self._elapsed_time_secs += delta_secs
        red = max(0.0, 1.0 - (self._elapsed_time_secs / (MOLES_FAIL_FADE_SEC)))
        self._towers.set_color((red, 0.0, 0.0))
        return (
            self._elapsed_time_secs >= MOLES_FAIL_FADE_SEC
            and not self._towers.are_any_sounds_playing()
        )
