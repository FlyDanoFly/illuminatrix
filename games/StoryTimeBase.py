
import csv
import logging
from collections import defaultdict, namedtuple

from statemachine import State

from bases import BaseStateMachineGame
from components.TowerController import TowerController
from constants.colors import DULL_RAINBOW, RAINBOW
from constants.constants import ShouldStop, TowerEnum
from effects.BlinkEffect import BlinkEffect

logger = logging.getLogger(__name__)

MASTER_VOLUME = 1.0

INTRO_TIME_BETWEEN_FLASHES_SEC = 0.5
INTRO_NUM_FLASHES = 7  # This should be odd
STORY_BIT = namedtuple("STORY_BIT", ("flash_tower_enum", "sound_key", "story_text"))
PAUSE_TIME_BETWEEN_SPEAKERS_SEC = 0.5
DEBUG_SKIP_BEATS = 0 # 16


class StoryTimeBase(BaseStateMachineGame):
    # TODO: Make the proxy class cleaner than this hack
    PROXY: bool = True

    # These should be overridden in the derived class
    STORY_SPEC_CSV: str = ""
    SOUND_BANK: str | None = None

    # Game states
    start = State("Start", initial=True)
    introduction = State("Introduction")
    speaking = State("Speaking")
    pause_between_speaking = State("pause_between_speaking")
    waiting_for_input = State("Waiting for Input")
    done = State("Done", final=True)

    # Game state transitions
    begin = start.to(introduction)
    start_game = introduction.to(waiting_for_input)
    start_speaking = waiting_for_input.to(speaking) | pause_between_speaking.to(speaking)
    start_pause = speaking.to(pause_between_speaking)
    get_input = pause_between_speaking.to(waiting_for_input)
    story_done = waiting_for_input.to(done)

    def __init__(self, tower_controller: TowerController) -> None:
        super().__init__()

        self.towers_in_use, self.story = self._read_file(self.STORY_SPEC_CSV)
        # self.towers_in_use, self.story = self._read_file("sound_banks/story_time/gremoryland/Story mode_ Stories - GremoryLand (Sonya - in progress).csv")

        self._towers = tower_controller
        self._towers.load_sound_bank(self.SOUND_BANK)
        # self._towers.load_sound_bank("sound_banks/story_time/gremoryland")

        self._tower_color_low = dict(zip(tower_controller, DULL_RAINBOW, strict=True))
        self._tower_color_high = dict(zip(tower_controller, RAINBOW, strict=True))

        self._time_between_moles_popping_up_sec = INTRO_TIME_BETWEEN_FLASHES_SEC
        self._elapsed_time_secs = 0.0

    def _read_file(self, filename: str) -> tuple[set[TowerEnum], list[dict[TowerEnum, list[STORY_BIT]]]]:
        """
        [
            # index is odrer of story beats
            {
                TowerEnum: [  # Chosen tower
                    # index is order of steps
                    STORY_BIT(
                        TowerEnum

                    )
                ]
            }
        ]
        """
        towers_in_use: set[TowerEnum] = set()
        with open(filename, "r") as file:
            dict_reader_no = csv.DictReader(file)
   
            fieldnames = dict_reader_no.fieldnames
            assert fieldnames is not None, "Error reading file"

            # Make a set of TowerEnums of all the towers preset
            tower_field_start = "Switch Tower #"
            towers_in_use = set()
            for field in fieldnames:
                if field.startswith(tower_field_start):
                    tower_num = int(field[len(tower_field_start):])
                    towers_in_use.add(TowerEnum(tower_num))

            # First get all the rows: {beat1:[row, row, row]}
            raw_beats = defaultdict(list)
            for row in dict_reader_no:
                beat = row["Story Beat"]
                if beat.startswith("-"):
                    # This is for humans, no the machine
                    continue
                beat = int(beat)
                raw_beats[beat].append(row)

            # Convert to a list in story beat order
            # [[{row}, {row}, {row}]]
            sorted_beats = [beat for _, beat in sorted(raw_beats.items(), key=lambda x: x[0])]

            # Sort the steps within each beat
            for beat in sorted_beats:
                beat.sort(key=lambda x: x["Step"])

            # Sort the steps with each beat
            done_story = []
            for beat_num, beat in enumerate(sorted_beats, start=1):
                beat_dict = defaultdict(list)
                for step_num, row in enumerate(beat, start=1):
                    for tower in towers_in_use:
                        text = row[f"{tower_field_start}{tower.value}"].strip()
                        flash_tower_num = row[f"Tower #{tower.value} Flash"].strip()
                        if flash_tower_num.startswith("-"):
                            continue
                        flasher = TowerEnum(int(flash_tower_num))
                        sound_key = f"tower_{tower.value}__{beat_num}__{step_num}"
                        beat_dict[tower].append(STORY_BIT(flasher, sound_key, text))
                done_story.append(beat_dict)

            # raise RuntimeError("-"*80)
            return towers_in_use, done_story

    def iter_story_beat(self):
        for beat in self.story:
            yield beat

    def iter_story_step(self, beat, chosen_tower):
        for step in beat[chosen_tower]:
            yield step

    def first_frame_update(self) -> None:
        """Override this to set up a first frame before updating"""
        for tower_enum, tower in self._towers.items():
            tower.set_color(self._tower_color_low[tower_enum])
        self.begin()

    # ----------------------------------------------------------------------
    # State: introduction

    def on_enter_introduction(self) -> None:
        """Handle the introduction state."""
        logger.debug("Switching to the introduction state.")
        self._effects = [
            BlinkEffect(
                [tower_enum],
                low_color=DULL_RAINBOW[tower_enum.value - 1],
                high_color=RAINBOW[tower_enum.value - 1],
                low_time_sec=0.25,
                high_time_sec=0.5,
                num_loops=1,
            ) for tower_enum in self._towers
        ]
        for effect in self._effects:
            self._towers.start_effect(effect)
            effect.begin()

    def do_introduction(self, delta_secs) -> ShouldStop:
        """Handle the introduction state."""
        any_playing = any(effect.is_playing() for effect in self._effects)
        if not any_playing:
            self.start_game()
 
    def on_exit_introduction(self) -> None:
        """Handle the playing state."""
        logger.debug("Switching to the playing state.")
        self.beat_iter = self.iter_story_beat()
        if DEBUG_SKIP_BEATS:
            for _ in range(DEBUG_SKIP_BEATS):
                self.beat_iter.__next__()
        # TODO: make loader (or a util) assert that there is always at least 1 beat

    # ----------------------------------------------------------------------
    # State: waiting_for_input

    def on_enter_waiting_for_input(self) -> None:
        self.selected_tower = None
        self.sound_playing = None
        try:
            self.my_beat = self.beat_iter.__next__()
        except StopIteration:
            # No more beats, done!
            self.story_done()

        for tower_enum, tower in self._towers.items():
            if tower_enum in self.towers_in_use:
                tower.set_color(RAINBOW[tower_enum.value - 1])
            else:
                tower.set_color(DULL_RAINBOW[tower_enum.value - 1])

    def do_waiting_for_input(self, delta_secs: float) -> ShouldStop:
        self._elapsed_time_secs += delta_secs
        for tower_enum in self.towers_in_use:
            if self._towers[tower_enum].did_switch_transition_down():
                self.selected_tower = tower_enum
                self.start_speaking()

    def on_exit_waiting_for_input(self) -> None:
        self.step_iter = self.iter_story_step(self.my_beat, self.selected_tower)
        # TODO: make loader assert that every beat and selected tower has at least 1 step, better yet make a validation tool
        try:
            self.step = self.step_iter.__next__()
        except StopIteration:
            # TODO: Programatically ensure that we are transitioning to "done", we probably are and can pass
            pass

    # ----------------------------------------------------------------------
    # State: speaking

    def on_enter_speaking(self) -> None:
        for tower_enum, tower in self._towers.items():
            tower.set_color(DULL_RAINBOW[tower_enum.value - 1])
        self.flash_tower = None
        self.sound_playing = None
        assert self.selected_tower is not None, "Tower selection not present"
        to_flash, sound_key, text = self.step
        self.sound_playing = self._towers[to_flash].play_sound(sound_key, volume=MASTER_VOLUME)
        self.effect = BlinkEffect([to_flash], DULL_RAINBOW[to_flash.value-1], RAINBOW[to_flash.value-1], 0.05, 0.05, num_loops=0)
        self._towers.start_effect(self.effect)
        self.effect.begin()
        logger.info("Speaking: %s", text)

    def do_speaking(self, delta_secs: float) -> ShouldStop:
        # play_sound always returns a Sound (failures come back already
        # finished); the None check only covers this attribute's initial
        # state, not the play contract
        if self.sound_playing is None or self.sound_playing.is_done():
            self.start_pause()
            self.effect.finish()

    # ----------------------------------------------------------------------
    # State: pause_between_speaking

    def on_enter_pause_between_speaking(self) -> None:
        logger.debug("on_enter_pause_between_speaking")
        self._elapsed_time_secs = 0.0
        self.pause_time_secs = PAUSE_TIME_BETWEEN_SPEAKERS_SEC

    def do_pause_between_speaking(self, delta_secs: float) -> ShouldStop:
        self._elapsed_time_secs += delta_secs
        if self._elapsed_time_secs < self.pause_time_secs:
            return
        try:
            self.step = self.step_iter.__next__()
            self.start_speaking()
        except StopIteration:
            self.get_input()

    # ----------------------------------------------------------------------
    # State: done
    def do_done(self, delta_secs: float) -> ShouldStop:
        return True
