import logging
import random

from bases import BaseGame
from components.TowerController import TowerController
from constants.colors import DULL_RAINBOW, RAINBOW
from constants.constants import TowerEnum

logger = logging.getLogger(__name__)


class LucyMagic8Ball(BaseGame):
    def __init__(self, tower_controller: TowerController):
        super().__init__()
        self._towers = tower_controller
        self._towers.load_sound_bank("sound_banks/lucy_magic_8_ball/")

        self.light_elapsed_time = 0.0
        self.dark_elapsed_time = 0.0
        self.time_between_new_light = 0.1
        self.time_between_new_dark = self.time_between_new_light
        self.towers = list(x for x in self._towers.values())
        self.magic_8_ball_answers = ("It is certain.", "Very doubtful.", "You may rely on it.", "Cannot predict now.", "My answer is no.", "Most likely.", "Not a chance.")
        self.stage = "waiting"
        self.newest_lit_tower = 0
        self.last_lit_tower = 0
        self.final_tower = 0
        self.random_int = random.choice(range(50,57))
        self.ticks = 0
        self.blink_on_time = 1.0
        self.blink_off_time = 0.2
        self.current_blink_state_time = 0.0
        self.is_blink_on = True
        self.blink_count = 0

    def first_frame_update(self) -> None:
        for idx, tower in enumerate(self._towers.values()):
            self.rgb = DULL_RAINBOW[idx]
            tower.set_color(self.rgb)
        print("Ask your question, mortal! Then spin the wheel.")

    def update(self, delta_secs: float) -> bool:
        logger.debug("LucyTest.update()", delta_secs)
        self.light_elapsed_time += delta_secs
        self.dark_elapsed_time += delta_secs
        if self.stage == "done":
            if self._towers.are_any_sounds_playing():
                return False
            return True
        if self.stage == "waiting":
            if self._towers.is_any_switch_pressed():
                for idx, tower in enumerate(self._towers.values()):
                    if tower.is_switch_pressed():
                        self.newest_lit_tower = idx
                        self.last_lit_tower = idx - 2
                        self.light_elapsed_time = 0.0
                        self.dark_elapsed_time = 0.0
                        self.stage = "spinning"
            return False
        if self.stage == "spinning":
            if self.light_elapsed_time >= self.time_between_new_light:
                self.light_elapsed_time -= self.time_between_new_light
                self.towers[self.newest_lit_tower].set_color((0.0, 1.0, 0.0))
                self.newest_lit_tower += 1
                if self.newest_lit_tower == 7:
                    self.newest_lit_tower = 0
                self.ticks += 1
                self.towers[self.newest_lit_tower].play_sound("tick")
                if (self.random_int + 5) > self.ticks >= self.random_int:
                    self.time_between_new_light *= 1.3
                    self.time_between_new_dark *= 1.25
                if self.ticks >= (self.random_int + 5):
                    self.time_between_new_light *= 1.3
                    self.time_between_new_dark *= 1.3
                if self.ticks >= (self.random_int + 10):
                    self.stage = "stopping"
                    self.final_tower = self.newest_lit_tower - 1
        if self.stage == "spinning" or self.stage == "stopping":
            if self.dark_elapsed_time >= self.time_between_new_dark:
                self.dark_elapsed_time -= self.time_between_new_dark
                self.towers[self.last_lit_tower].set_color(DULL_RAINBOW[self.last_lit_tower])
                self.last_lit_tower += 1
                if self.last_lit_tower == 7:
                    self.last_lit_tower = 0
                self.towers[self.newest_lit_tower].play_sound("tick")
                if self.last_lit_tower == self.newest_lit_tower:
                    self.stage = "blinking"
                    # self.towers[self.final_tower].play_sound("gong")
                    self.towers[self.last_lit_tower].play_sound(f"answer_{self.final_tower+1}")
            return False
        if self.stage == "blinking":
            if self.light_elapsed_time >= self.current_blink_state_time:
                if self.is_blink_on:
                    self.towers[self.final_tower].set_color(DULL_RAINBOW[self.final_tower])
                    self.is_blink_on = False
                    self.current_blink_state_time = self.blink_off_time
                    return False
                else:
                    self.towers[self.final_tower].set_color((0.0, 1.0, 0.0))
                    self.is_blink_on = True
                    self.current_blink_state_time = self.blink_on_time
                    self.blink_count += 1
                    if self.blink_count == 3:
                        self.stage = "answering"
                    return False
        if self.stage == "answering":
            print(self.magic_8_ball_answers[self.final_tower])
            self.stage = "done"
            

        return False
