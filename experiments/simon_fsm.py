import random
import time

from statemachine import State, StateMachine

from games import BaseGame

class BaseStateMachineGame(StateMachine, BaseGame):
    """Base class for games using a state machine."""
    
    def first_frame_update(self):
        """Override this to set up a first frame before updating"""
        pass

    def update(self, delta_ms: float) -> bool | None:
        """Returns: True if program should terminate, falsy to continue"""
        self.do_state()
        return True

    def do_state(self):
        if do_state := getattr(self, f'do_{self.current_state.value}', None):
            do_state()


class SimonGame(StateMachine):
    waiting: State = State('Waiting', initial=True)
    showing_sequence: State = State('Showing Sequence')
    getting_input: State = State('Getting Player Input')
    checking_input: State = State('Checking Player Input')
    game_over: State = State('Game Over')
    
    start_game = waiting.to(showing_sequence)
    sequence_shown = showing_sequence.to(getting_input)
    input_received = getting_input.to(checking_input)
    correct_input = checking_input.to(showing_sequence)
    wrong_input = checking_input.to(game_over)
    restart = game_over.to(showing_sequence)

    def __init__(self):
        super().__init__()
        self._sequence = []
        self._player_input = []

    def on_start_game(self):
        self._sequence = []
        self._add_random_color()
        print("\nGame started!\n")

    def on_sequence_shown(self):
        print("\nNow it's your turn to repeat the sequence:")
        self._player_input = self._get_player_input()

    def on_input_received(self):
        if self._player_input == self._sequence:
            print("Correct! Moving to the next round.\n")
            time.sleep(1)
            self._add_random_color()
            self.correct_input()
        else:
            self.wrong_input()

    def on_wrong_input(self):
        print("\nWrong input! Game Over.")
        print(f"The correct sequence was: {' '.join(self._sequence)}")

    def _add_random_color(self):
        color = random.choice(['Red', 'Green', 'Blue', 'Yellow'])
        self._sequence.append(color)

    def show_sequence(self):
        print("Watch the sequence:")
        for color in self._sequence:
            print(color)
            time.sleep(0.8)
        time.sleep(0.5)
        self.sequence_shown()

    def _get_player_input(self):
        return input("Enter the sequence (space-separated colors): ").strip().title().split()

    def do_showing_sequence(self):
        print("Showing sequence...")
        self.show_sequence()

    def update(self):
        if do_state := getattr(self, f'do_{self.current_state.value}', None):
            do_state()
        elif self.current_state == self.showing_sequence:
        # if self.showing_sequence.is_active:
            print("*"*80)
            self.show_sequence()
        elif self.current_state == self.getting_input:
            self.input_received()
        elif self.current_state == self.game_over:
            choice = input("\nDo you want to play again? (y/n): ").lower()
            if choice == 'y':
                self.restart()
            else:
                print("Thanks for playing Simon!")
                return False
        return True

if __name__ == "__main__":
    game = SimonGame()
    game.start_game()

    while True:
        if not game.update():
            break
