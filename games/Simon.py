import random

from statemachine import State

from bases.BaseStateMachineGame import BaseStateMachineGame
from components.TowerController import TowerController
from constants.colors import DULL_RAINBOW, RAINBOW
from constants.constants import ShouldStop, TowerEnum
from effects.BingFade import BingFade

SIMON_TIME_BETWEEN_SEQUENCE_BEATS_SECS = 1.0
SIMON_TIME_WRONG_SECS = 0.25
SIMON_SEQUENCES_PER_LEVEL = 5
SIMON_BING_FATE_TIME_SEC = 0.75
SIMON_BING_SUSTAIN_TIME_SEC = 0.25
# Level up factor will be used (time_between * progressive_fator ^ level)
SIMON_LEVEL_UP_PROGRESSIVE_FACTOR = 0.9
# Level up factor will be used time_beteen * (1.0 - linear_fator * level)
SIMON_LEVEL_UP_LINEAR_FACTOR = 0.1
# Level up minimum factor, (time_between * factor) will no go below this value
SIMON_LEVEL_UP_FACTOR_MINIMUM = 0.05

random.seed()

class Simon(BaseStateMachineGame):
    SOUND_BANK = "sound_banks/simon"

    # Game states
    start = State("Start", initial=True)
    introduction = State("Introduction")
    showing_sequence = State("Showing Sequence")
    input_sequence = State("Input Sequence")
    pad_showing_sequence = State("Pad Showing Sequence")
    coast_to_done = State("Coast to Done")
    done = State("Done", final=True)


    # Game state transitions
    begin = start.to(introduction)
    start_game = introduction.to(showing_sequence)
    await_input = showing_sequence.to(input_sequence)
    next_sequence = input_sequence.to(pad_showing_sequence)
    padding_done = pad_showing_sequence.to(showing_sequence)
    go_to_coast_to_done = input_sequence.to(coast_to_done)
    end_game = coast_to_done.to(done)

    def __init__(self, tower_controller: TowerController) -> None:
        super().__init__()

        self._towers = tower_controller
        self._towers.load_sound_bank(self.SOUND_BANK)

        self._tower_color_low = dict(zip(tower_controller, DULL_RAINBOW, strict=True))
        self._tower_color_high = dict(zip(tower_controller, RAINBOW, strict=True))

        self._sequence = []
        self._time_between_sequency_beats = SIMON_TIME_BETWEEN_SEQUENCE_BEATS_SECS
        self._level = 1
        self._level_factor = 1.0

    def first_frame_update(self) -> None:
        super().first_frame_update()
        for tower in self._towers:
            self._towers[tower].set_color(self._tower_color_low[tower])
        self.begin()

    def _add_to_sequence(self):
        """Add a random tower to the sequence."""
        self._sequence.append(random.choice(list(TowerEnum)))
        q, r = divmod(len(self._sequence), SIMON_SEQUENCES_PER_LEVEL)
        if r == 0 and q > 0:
            # If we have completed a sequence, increase the level
            self._level += 1
            self._level_factor = max(
                    SIMON_LEVEL_UP_FACTOR_MINIMUM,
                    1.0 - (SIMON_LEVEL_UP_LINEAR_FACTOR * self._level)
            )
            print(f"Level up! Now at level {self._level}.")
            # self._time_between_sequency_beats *= 0.9
            self._towers.play_sound("level_up")

    def on_enter_introduction(self):
        self._add_to_sequence()
        self.start_game()

    def on_enter_showing_sequence(self):
        """Show the sequence of towers."""
        self._add_to_sequence()
        self._time_left = self._time_between_sequency_beats * self._level_factor
        self._sequence_iterator = iter(self._sequence)
        self._towers.stop_effects()

    def do_showing_sequence(self, dt: float):
        """Display the sequence of towers."""
        self._time_left -= dt
        if self._time_left <= 0.0:
            # Play the next sound and tower
            # TODO: Stop playing the sound if it is already playing
            next_tower = next(self._sequence_iterator, None)
            if next_tower is None:
                self.await_input()
                return
            print(next_tower)
            for tower_enum, tower in self._towers.items():
                if tower_enum == next_tower:
                    # self._towers[tower].play_sound()
                    tower.set_color(self._tower_color_high[tower_enum])
                    tower.play_sound(f"simon_sequence_sound_{tower_enum.value}")
                else:
                    tower.set_color(self._tower_color_low[tower_enum])

            self._time_left = self._time_between_sequency_beats * self._level_factor

    def on_enter_input_sequence(self):
        for tower in self._towers:
            self._towers[tower].set_color(self._tower_color_low[tower])
        self._sequence_iterator = iter(self._sequence)
        self._current_sequence_item = next(self._sequence_iterator, None)

    def do_input_sequence(self, dt: float):
        """Handle user input for the sequence."""
        if not self._towers.did_switch_transition_down():
            # No tower pressed, continue waiting for input
            return

        # only way to be here if something is pressed, either there is 1 right answer or 6 possible wrong answers
        right = False
        wrong = False
        for tower_enum, tower in self._towers.items():
            if tower.did_switch_transition_down():
                bing_effect = BingFade(
                        [tower_enum],
                        start_color=self._tower_color_high[tower_enum],
                        end_color=self._tower_color_low[tower_enum],
                        fade_time_sec=SIMON_BING_FATE_TIME_SEC * self._level_factor,
                        sustain_time_sec=SIMON_BING_SUSTAIN_TIME_SEC * self._level_factor,
                    )
                self._towers.start_effect(bing_effect)
                # bing_effect.start()

                tower.play_sound(f"simon_sequence_sound_{tower_enum.value}")
                if tower_enum == self._current_sequence_item:
                    right = True  # noqa: F841
                else:
                    # Wrong tower pressed, reset the sequence
                    print("Wrong tower pressed, resetting sequence")
                    wrong = True
                    break
        if wrong:
            # Reset the sequence
            self.go_to_coast_to_done()
            self._time_left = SIMON_TIME_WRONG_SECS
            return

        self._current_sequence_item = next(self._sequence_iterator, None)
        if self._current_sequence_item is None:
            # Completed the sequence
            self.next_sequence()
            return

    def on_enter_pad_showing_sequence(self):
        self._time_left = SIMON_TIME_BETWEEN_SEQUENCE_BEATS_SECS

    def do_pad_showing_sequence(self, dt: float) -> ShouldStop:
        """Handle the pad showing sequence."""
        self._time_left -= dt
        if self._time_left <= 0.0:
            # Time to show the next sequence
            print("Changing to Showing Sequence")
            self.padding_done()

    def on_enter_coast_to_done(self):
        self._time_left = SIMON_TIME_BETWEEN_SEQUENCE_BEATS_SECS

    def do_coast_to_done(self, dt: float) -> ShouldStop:
        """Handle the end of the game."""
        self._time_left -= dt
        if self._time_left <= 0.0:
            print("Changing to Game Over")
            self._towers.fade_out()
            self.end_game()
           
    def on_enter_done(self):
        """Handle the end of the game."""
        print("Game Over, yoyoyo")
        self._towers.play_sound("game_over")
        self._towers.set_color((1.0, 0.0, 0.0))
        self._time_left = SIMON_TIME_WRONG_SECS
        self._towers.stop_effects()
        # Reset the game state

    def do_done(self, dt: float) -> ShouldStop:
        """Wait for the game to finish."""
        self._time_left -= dt
        return not self._towers.are_any_sounds_playing()
