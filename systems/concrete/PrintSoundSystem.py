from typing import Any

from bases.SoundSystem import Sound, SoundSystem
from constants.constants import TowerEnum


class PrintSound(Sound):
    """Debug stand-in for a playing sound; reports itself done immediately."""

    def __init__(self, name: str):
        self.name = name

    def is_done(self) -> bool:
        return True

    def start_fade_out(self, duration_sec: float) -> None:
        print(f"PrintSound: fading out {self.name} over {duration_sec}s")

    def stop(self) -> None:
        print(f"PrintSound: stopping {self.name}")

    def mix_into(self, output_buffers: list[Any], channel_map: list[TowerEnum]) -> None:
        pass


class PrintSoundSystem(SoundSystem):
    def load_sound_bank(self, path: str) -> None:
        print(f"PrintSoundSystem: Loading sound bank {path}")

    def play(self, sound: str, tower_enums: list[TowerEnum] | None = None, volume: float = 1.0, num_loops: int = 0) -> Sound | None:
        print(f"PrintSoundSystem: Playing {sound} on towers {tower_enums} at volume {volume}, {num_loops} loops")
        return PrintSound(sound)

    def stop_all(self, fade_secs: float = 0.25) -> None:
        print(f"PrintSoundSystem: Stopping all sounds over {fade_secs}s")

    def are_any_sounds_playing(self) -> bool:
        return False

    def update(self, delta_secs: float) -> None:
        pass

    def render(self) -> None:
        pass

    def startup(self) -> None:
        print("PrintSoundSystem: Starting up the sound system")

    def shutdown(self) -> None:
        print("PrintSoundSystem: Shutting down the sound system")
