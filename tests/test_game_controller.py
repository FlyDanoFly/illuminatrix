"""Tests for GameController's state flow: selection cycling, the
instructions gate, idle timeouts (selection idles into ambient, games
idle back to selection — but ambient itself never times out), and the
button paths out of games and ambient. No hardware — the light, sound,
and input systems are fakes; TowerController and EffectManager are the
real ones wired on top.

Runs two ways:

    poetry run pytest tests/
    poetry run python tests/test_game_controller.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import components.GameController as gc_mod  # noqa: E402
from bases.BaseGame import BaseGame  # noqa: E402
from bases.InputSystem import InputSystem  # noqa: E402
from bases.LightSystem import LightSystem  # noqa: E402
from components.GameController import GameController  # noqa: E402
from components.TowerController import TowerController  # noqa: E402
from constants.constants import (  # noqa: E402
    ColorType,
    ControllerSwitchEnum,
    LightPos,
    TowerEnum,
)
from managers.EffectManager import EffectManager  # noqa: E402
from systems.concrete.NullSoundSystem import NullSoundSystem  # noqa: E402

FRAME_SECS = 1 / 30
# Small so tests don't have to simulate two minutes frame by frame
SELECT_IDLE_TIMEOUT_SECS = 1.0
# One frame that overshoots the in-game idle timeout in a single step
GAME_IDLE_OVERSHOOT_SECS = gc_mod.GAME_CONTROLLER_GAME_IDLE_TIMEOUT_SECS + 1.0


class FakeLightSystem(LightSystem):
    def set(self, tower_enum: TowerEnum, color: ColorType, light_pos: LightPos = LightPos.All) -> None:
        pass

    def startup(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def update(self, delta_secs: float) -> None:
        pass

    def render(self) -> None:
        pass


class FakeInputSystem(InputSystem):
    """Switches read from `pressed`, a set the test mutates per frame."""

    def __init__(self):
        super().__init__()
        self.pressed: set = set()

    def _read_switches(self, delta_secs: float) -> None:
        for switch in self.pressed:
            self._switch_state[switch] = True

    def startup(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def render(self) -> None:
        pass


class FakeSoundSystem(NullSoundSystem):
    """Silent, but records what was asked of it, and lets a test hold
    are_any_sounds_playing() high to keep the instructions gate closed."""

    def __init__(self):
        super().__init__()
        self.played: list[str] = []
        self.loaded_banks: list[str] = []
        self.playing = False

    def load_sound_bank(self, path: str) -> None:
        self.loaded_banks.append(path)

    def play(self, sound, tower_enums=None, volume=1.0, num_loops=0):
        self.played.append(sound)
        return super().play(sound, tower_enums, volume, num_loops)

    def are_any_sounds_playing(self) -> bool:
        return self.playing


class FakeSystemFactory:
    def __init__(self):
        self.light = FakeLightSystem()
        self.sound = FakeSoundSystem()
        self.input = FakeInputSystem()

    def get_light_system(self):
        return self.light

    def get_sound_system(self):
        return self.sound

    def get_input_system(self):
        return self.input


class FakeManagerFactory:
    def __init__(self, systems: FakeSystemFactory):
        self._effects = EffectManager(systems)

    def get_effect_manager(self):
        return self._effects


class ScriptedGame(BaseGame):
    """Counts its lifecycle calls; ends when the test flips `done`."""

    def __init__(self, towers):
        self.first_frames = 0
        self.updates = 0
        self.done = False

    def first_frame_update(self) -> None:
        self.first_frames += 1

    def update(self, delta_secs: float):
        self.updates += 1
        return self.done


class GameA(ScriptedGame):
    pass


class GameB(ScriptedGame):
    pass


class Ambient(ScriptedGame):
    pass


class Rig:
    """A GameController on fake systems, stepped like play.py steps it:
    input system first, then the controller."""

    def __init__(self, game_classes, ambient_class=Ambient):
        self.systems = FakeSystemFactory()
        self.inputs = self.systems.input
        self.sounds = self.systems.sound
        managers = FakeManagerFactory(self.systems)
        towers = TowerController(self.systems, managers)
        self.controller = GameController(
            self.systems,
            managers,
            towers,
            game_classes,
            ambient_class,
            select_idle_timeout_secs=SELECT_IDLE_TIMEOUT_SECS,
        )

    def step(self, pressed=(), secs=FRAME_SECS):
        self.inputs.pressed = set(pressed)
        self.inputs.update(secs)
        return self.controller.update(secs)

    @property
    def state(self) -> str:
        return self.controller.current_state.id

    @property
    def game(self):
        return self.controller._current_game

    def start_selected_game(self):
        """Press START and let the (silent) instructions finish."""
        self.step({ControllerSwitchEnum.START})
        self.step()
        assert self.state == "playing_game"


def test_selection_announces_and_cycles_with_next():
    rig = Rig([GameA, GameB])
    assert rig.state == "await_input"
    assert rig.sounds.loaded_banks == [GameController.INTRO_SOUND_BANK]
    assert rig.sounds.played == ["GameA"], "selection starts on the first game"

    rig.step({ControllerSwitchEnum.NEXT_GAME})
    assert rig.sounds.played[-1] == "GameB", "NEXT_GAME moves to the next game"
    rig.step()  # release the button
    rig.step({ControllerSwitchEnum.NEXT_GAME})
    assert rig.sounds.played[-1] == "GameA", "two games wrap around"


def test_start_plays_instructions_then_starts_game():
    rig = Rig([GameA, GameB])
    selected = rig.controller._selected_game
    rig.step({ControllerSwitchEnum.START})
    assert rig.state == "instructions"
    assert rig.sounds.played[-1] == f"{selected.__name__}__instructions"
    rig.step()  # silence: the gate opens immediately
    assert rig.state == "playing_game"
    assert isinstance(rig.game, selected)
    assert rig.game.first_frames == 1


def test_instructions_wait_for_the_sound_to_finish():
    rig = Rig([GameA, GameB])
    rig.sounds.playing = True
    rig.step({ControllerSwitchEnum.START})
    rig.step()
    rig.step()
    assert rig.state == "instructions", "gate holds while the sound plays"
    rig.sounds.playing = False
    rig.step()
    assert rig.state == "playing_game"


def test_select_idle_starts_ambient():
    rig = Rig([GameA, GameB])
    rig.step(secs=SELECT_IDLE_TIMEOUT_SECS + 0.1)
    assert rig.state == "playing_game"
    assert isinstance(rig.game, Ambient)


def test_held_tower_switch_defers_ambient():
    rig = Rig([GameA, GameB])
    rig.step({TowerEnum.Tower_3}, secs=SELECT_IDLE_TIMEOUT_SECS * 5)
    assert rig.state == "await_input", "someone on a pad is activity"
    rig.step(secs=SELECT_IDLE_TIMEOUT_SECS + 0.1)
    assert isinstance(rig.game, Ambient), "idle resumes once they step off"


def test_game_idle_timeout_cancels_game():
    rig = Rig([GameA, GameB])
    rig.start_selected_game()
    rig.step(secs=GAME_IDLE_OVERSHOOT_SECS)
    assert rig.state == "cancel"
    rig.step()
    assert rig.state == "await_input"


def test_held_tower_switch_keeps_game_alive():
    rig = Rig([GameA, GameB])
    rig.start_selected_game()
    rig.step({TowerEnum.Tower_1}, secs=GAME_IDLE_OVERSHOOT_SECS)
    assert rig.state == "playing_game"


def test_ambient_survives_idle_timeout():
    rig = Rig([GameA, GameB])
    rig.step(secs=SELECT_IDLE_TIMEOUT_SECS + 0.1)
    assert isinstance(rig.game, Ambient)
    for _ in range(3):
        rig.step(secs=GAME_IDLE_OVERSHOOT_SECS)
    assert rig.state == "playing_game", "ambient never idles out"
    assert isinstance(rig.game, Ambient)
    assert rig.game.updates == 3, "ambient keeps getting updates"


def test_controller_button_exits_ambient():
    rig = Rig([GameA, GameB])
    rig.step(secs=SELECT_IDLE_TIMEOUT_SECS + 0.1)
    assert isinstance(rig.game, Ambient)
    rig.step({ControllerSwitchEnum.NEXT_GAME})
    assert rig.state == "cancel"
    rig.step()
    assert rig.state == "await_input"


def test_reset_returns_to_selection():
    rig = Rig([GameA, GameB])
    rig.start_selected_game()
    rig.step({ControllerSwitchEnum.RESET})
    assert rig.state == "cancel"
    rig.step()
    assert rig.state == "await_input"
    assert rig.sounds.loaded_banks[-1] == GameController.INTRO_SOUND_BANK


def test_game_done_returns_to_selection():
    rig = Rig([GameA, GameB])
    rig.start_selected_game()
    rig.step()
    assert rig.state == "playing_game"
    rig.game.done = True
    rig.step()
    assert rig.state == "cancel"
    rig.step()
    assert rig.state == "await_input"


def test_single_game_done_stops_the_program():
    rig = Rig([GameA])
    assert rig.state == "playing_game", "one game skips selection"
    assert not rig.step(), "a running game does not stop the program"
    assert rig.game.updates == 1
    rig.game.done = True
    assert rig.step(), "the game finishing stops the program"


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items())
             if name.startswith("test_") and callable(fn)]
    for fn in tests:
        fn()
        print(f"{fn.__name__} OK")
    print(f"\nAll {len(tests)} tests passed")
