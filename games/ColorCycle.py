import logging

from bases import BaseGame
from bases.SoundSystem import Sound
from components.TowerController import TowerController
from constants.constants import TowerEnum
from effects.BingFade import BingFade
from utils import hsv_to_rgb

logger = logging.getLogger(__name__)

# HERTZ = 1.0  # very fast to see it working
# HERTZ = 0.10  # pretty fast still
HERTZ = 0.02  # longer and mellow, pretty

COLOR_CYCLE_FADE_IN_TIME_SEC = 15.5
COLOR_CYCLE_SUSTAIN_TIME_SEC = 0.0

# How strongly the tower's speaker output whitens its cycle color:
# 0.0 ignores sound, 1.0 desaturates all the way to white at full level
# (values past 1.0 just reach full white at lower levels)
SOUND_LEVEL_WHITENING = 0.8

# How often to re-play an ambient loop whose Sound reports done. On JACK
# an infinite loop only "finishes" because the server dropped it (an
# outage clears every active sound), so this is what brings an unattended
# ambient night back after a reconnect. Throttled because the silent
# systems' sounds (Null/Print) are born done and must not retry every frame
LOOP_RETRY_SECS = 5.0

class ColorCycle(BaseGame):
    SOUND_BANK = "sound_banks/ambient"

    def __init__(self, tower_controller: TowerController) -> None:
        self._towers = tower_controller
        self.start_hue = 0.0
        self.hue_tower_step = 1.0 / len(TowerEnum)
        self.hertz = HERTZ
        self._loops: dict[TowerEnum, Sound] = {}
        self._loop_retry_secs = 0.0
        self._towers.load_sound_bank(self.SOUND_BANK)

    def first_frame_update(self) -> None:
        self.update(0.0)
        hue = self.start_hue
        for tower_enum, tower in self._towers.items():
            rgb = hsv_to_rgb(hue, 1.0, 1.0)
            bing_effect = BingFade(
                [tower_enum],
                start_color=(1.0, 1.0, 1.0),
                end_color=rgb,
                fade_time_sec=COLOR_CYCLE_FADE_IN_TIME_SEC,
                sustain_time_sec=COLOR_CYCLE_SUSTAIN_TIME_SEC,
            )
            self._towers.start_effect(bing_effect)
            hue = (hue + self.hue_tower_step) % 1.0
            self._play_loop(tower_enum, tower)

    def _play_loop(self, tower_enum: TowerEnum, tower) -> None:
        self._loops[tower_enum] = tower.play_sound(
            f"ambient_tower_{tower_enum.value}", volume=0.33, num_loops=-1)

    def update(self, delta_secs: float) -> bool | None:
        self._heal_loops(delta_secs)

        if self._towers.are_any_effects_playing():
            # If any effect is playing, we don't want to update the colors
            return None

        self.start_hue = (self.start_hue + self.hertz * delta_secs) % 1.0
        hue = self.start_hue
        levels = self._towers.get_sound_levels()
        for tower_enum, tower in self._towers.items():
            # Each tower's soundtrack whitens its color: the cycle hue is
            # the base, and the speaker's current level pulls saturation
            # down toward white so the light breathes with the audio.
            # Clamped so an overdriven whitening knob whites out instead
            # of handing hsv_to_rgb a negative saturation
            saturation = max(0.0, 1.0 - SOUND_LEVEL_WHITENING * levels[tower_enum])
            rgb = hsv_to_rgb(hue, saturation, 1.0)
            tower.set_color(rgb)
            hue = (hue + self.hue_tower_step) % 1.0

    def _heal_loops(self, delta_secs: float) -> None:
        """Re-play any ambient loop whose Sound has finished — on JACK
        that means the server dropped it (see LOOP_RETRY_SECS). Runs
        ahead of the intro-effect gate so an outage during the fade-in
        still heals."""
        self._loop_retry_secs += delta_secs
        if self._loop_retry_secs < LOOP_RETRY_SECS:
            return
        self._loop_retry_secs = 0.0
        for tower_enum, tower in self._towers.items():
            if tower_enum in self._loops and self._loops[tower_enum].is_done():
                self._play_loop(tower_enum, tower)
