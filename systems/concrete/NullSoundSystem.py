from typing import Any

from bases.SoundSystem import Sound, SoundSystem
from constants.constants import TowerEnum


class NullSound(Sound):
    """A silent sound that is already over."""

    def is_done(self) -> bool:
        return True

    def start_fade_out(self, duration_sec: float) -> None:
        pass

    def stop(self) -> None:
        pass

    def mix_into(self, output_buffers: list[Any], channel_map: list[TowerEnum]) -> None:
        pass


class NullSoundSystem(SoundSystem):
    """Fully silent sound system — run the installation without audio
    (e.g. hardware debugging) with no JACK server and no console noise."""

    def load_sound_bank(self, path: str) -> None:
        pass

    def play(self, sound: str, tower_enums: list[TowerEnum] | None = None, volume: float = 1.0, num_loops: int = 0) -> Sound | None:
        return NullSound()

    def stop_all(self, fade_secs: float = 0.25) -> None:
        pass

    def are_any_sounds_playing(self) -> bool:
        return False

    def update(self, delta_secs: float) -> None:
        pass

    def render(self) -> None:
        pass

    def startup(self) -> None:
        pass

    def shutdown(self) -> None:
        pass
