"""Tests for GameController's state flow: selection cycling, the
instructions gate, idle timeouts (selection idles into ambient, games
idle back to selection — but ambient itself never times out), the
button paths out of games and ambient, the pad prompt (stomps in
selection/ambient answer from that pad's tower under one global
cooldown), and the quiet-hours profile (the NEXT_GAME+RESET hold,
master volume/brightness, roster restriction, and the persistence
marker file). No hardware — the
light, sound, and input systems are fakes; TowerController and
EffectManager are the real ones wired on top.

Runs two ways:

    poetry run pytest tests/
    poetry run python tests/test_game_controller.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from test_input_system import StubInputSystem  # noqa: E402

import components.GameController as gc_mod  # noqa: E402
from bases.BaseGame import BaseGame  # noqa: E402
from bases.LightSystem import LightSystem  # noqa: E402
from components.GameController import GameController  # noqa: E402
from components.ShowProfile import ShowProfile  # noqa: E402
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
    """Records the last color set per tower."""

    def __init__(self):
        self.colors: dict[TowerEnum, ColorType] = {}

    def _set(self, tower_enum: TowerEnum, color: ColorType, light_pos: LightPos = LightPos.All) -> None:
        self.colors[tower_enum] = color

    def startup(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def update(self, delta_secs: float) -> None:
        pass

    def render(self) -> None:
        pass


class FakeSoundSystem(NullSoundSystem):
    """Silent, but records what was asked of it, lets a test hold
    are_any_sounds_playing() high to keep the instructions gate closed,
    and reports whatever tower levels the test sets."""

    def __init__(self):
        super().__init__()
        self.played: list[str] = []
        self.played_at: list[tuple[str, tuple[TowerEnum, ...] | None]] = []
        self.loaded_banks: list[str] = []
        self.playing = False
        self.levels: dict[TowerEnum, float] = {t: 0.0 for t in TowerEnum}

    def load_sound_bank(self, path: str) -> None:
        self.loaded_banks.append(path)

    def play(self, sound, tower_enums=None, volume=1.0, num_loops=0):
        self.played.append(sound)
        self.played_at.append((sound, tuple(tower_enums) if tower_enums else None))
        return super().play(sound, tower_enums, volume, num_loops)

    def are_any_sounds_playing(self) -> bool:
        return self.playing

    def get_tower_levels(self) -> dict[TowerEnum, float]:
        return dict(self.levels)


class FakeSystemFactory:
    def __init__(self):
        self.light = FakeLightSystem()
        self.sound = FakeSoundSystem()
        self.input = StubInputSystem()

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

    def __init__(self, game_classes, ambient_class=Ambient, **controller_kwargs):
        self.systems = FakeSystemFactory()
        self.inputs = self.systems.input
        self.sounds = self.systems.sound
        managers = FakeManagerFactory(self.systems)
        towers = TowerController(self.systems, managers)
        controller_kwargs.setdefault("select_idle_timeout_secs", SELECT_IDLE_TIMEOUT_SECS)
        self.controller = GameController(
            self.systems,
            managers,
            towers,
            game_classes,
            ambient_class,
            **controller_kwargs,
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


def test_ambient_subclass_game_keeps_normal_game_rules():
    # Ambient semantics attach to how the session started (the idle
    # path), not the game's type — a selectable game subclassing the
    # ambient class must still idle out like any other game
    class AmbientChild(Ambient):
        pass

    rig = Rig([GameA, AmbientChild])
    rig.step({ControllerSwitchEnum.NEXT_GAME})  # select AmbientChild
    rig.start_selected_game()
    assert isinstance(rig.game, AmbientChild)
    rig.step(secs=GAME_IDLE_OVERSHOOT_SECS)
    assert rig.state == "cancel", "subclass of ambient still idles out"


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


# ------------------------------------------------------------
# Pad prompt ("go use the control panel")


def pad_prompts(rig):
    """The tower lists the pad prompt was played on, in order."""
    return [towers for sound, towers in rig.sounds.played_at
            if sound == gc_mod.PAD_PROMPT_SOUND]


def test_pad_stomp_in_selection_prompts_from_that_tower():
    rig = Rig([GameA, GameB])
    rig.step({TowerEnum.Tower_3})
    assert pad_prompts(rig) == [(TowerEnum.Tower_3,)]


def test_pad_prompt_cooldown_is_global_across_pads():
    rig = Rig([GameA, GameB])
    rig.step({TowerEnum.Tower_3})
    rig.step()  # release
    rig.step({TowerEnum.Tower_5})
    assert len(pad_prompts(rig)) == 1, "a different pad inside the cooldown stays silent"
    rig.step(secs=gc_mod.PAD_PROMPT_COOLDOWN_SECS)  # release; cooldown drains
    rig.step({TowerEnum.Tower_5})
    assert pad_prompts(rig)[-1] == (TowerEnum.Tower_5,), "prompts again after the cooldown"


def test_held_pad_prompts_once():
    rig = Rig([GameA, GameB])
    rig.step({TowerEnum.Tower_1})
    rig.step({TowerEnum.Tower_1}, secs=gc_mod.PAD_PROMPT_COOLDOWN_SECS * 2)
    rig.step({TowerEnum.Tower_1})
    assert len(pad_prompts(rig)) == 1, "standing on the pad is one stomp, not a repeat"


def test_pad_stomp_in_ambient_prompts():
    rig = Rig([GameA, GameB])
    rig.step(secs=SELECT_IDLE_TIMEOUT_SECS + 0.1)
    assert isinstance(rig.game, Ambient)
    rig.step({TowerEnum.Tower_2})
    assert pad_prompts(rig) == [(TowerEnum.Tower_2,)]


def test_pad_stomp_during_game_does_not_prompt():
    rig = Rig([GameA, GameB])
    rig.start_selected_game()
    rig.step({TowerEnum.Tower_4})
    rig.step()
    assert pad_prompts(rig) == [], "in a game the pads belong to the game"


# ------------------------------------------------------------
# Quiet hours

QUIET_HOLD = {ControllerSwitchEnum.NEXT_GAME, ControllerSwitchEnum.RESET}
QUIET_TEST_PROFILE = ShowProfile(
    name="quiet test",
    master_volume=0.5,
    master_brightness=0.65,
    allowed_games=frozenset({"GameB"}),
)
# The quiet tests hold buttons across multi-second steps; the tiny test
# select-idle timeout would drop into ambient mid-hold and muddy them
NO_AMBIENT_SECS = 60.0


def hold_quiet_combo(rig):
    """Press NEXT_GAME+RESET (single-press actions fire here), then keep
    holding past the toggle threshold."""
    rig.step(QUIET_HOLD)
    rig.step(QUIET_HOLD, secs=gc_mod.QUIET_HOURS_HOLD_SECS + 0.1)


def test_quiet_hold_toggles_profile():
    rig = Rig([GameA, GameB], quiet_profile=QUIET_TEST_PROFILE,
              select_idle_timeout_secs=NO_AMBIENT_SECS)
    assert rig.sounds._master_volume == 1.0
    hold_quiet_combo(rig)
    assert rig.sounds._master_volume == 0.5
    assert rig.systems.light._master_brightness == 0.65
    assert "quiet_hours_on" in rig.sounds.played
    assert rig.state == "await_input"
    assert rig.sounds.played[-1] == "GameB", "re-announces from the quiet roster"

    rig.step()  # release
    rig.step({ControllerSwitchEnum.NEXT_GAME})
    assert rig.sounds.played[-1] == "GameB", "restricted roster wraps to itself"


def test_quiet_hold_toggles_once_until_released():
    rig = Rig([GameA, GameB], quiet_profile=QUIET_TEST_PROFILE,
              select_idle_timeout_secs=NO_AMBIENT_SECS)
    hold_quiet_combo(rig)
    rig.step(QUIET_HOLD, secs=gc_mod.QUIET_HOURS_HOLD_SECS * 3)
    assert rig.sounds._master_volume == 0.5, "no second toggle without a release"


def test_quiet_hold_toggles_back_and_persists():
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        state_file = Path(tmp) / "quiet_state"
        rig = Rig([GameA, GameB], quiet_profile=QUIET_TEST_PROFILE,
                  quiet_state_file=state_file,
                  select_idle_timeout_secs=NO_AMBIENT_SECS)
        hold_quiet_combo(rig)
        assert state_file.exists(), "toggle writes the marker file"

        # A fresh controller on the same marker boots straight into quiet
        rig2 = Rig([GameA, GameB], quiet_profile=QUIET_TEST_PROFILE,
                   quiet_state_file=state_file,
                   select_idle_timeout_secs=NO_AMBIENT_SECS)
        assert rig2.sounds._master_volume == 0.5
        assert rig2.sounds.played == ["GameB"], "boot announces from the quiet roster"
        white = rig2.systems.light.colors[TowerEnum.Tower_1]
        assert white == (0.65, 0.65, 0.65), "selection white is brightness-scaled"

        # Release and hold again: back to normal, marker gone
        rig.step()
        hold_quiet_combo(rig)
        assert rig.sounds._master_volume == 1.0
        assert rig.systems.light._master_brightness == 1.0
        assert "quiet_hours_off" in rig.sounds.played
        assert not state_file.exists()


def test_quiet_profile_without_matching_games_keeps_full_roster():
    stranger = ShowProfile(name="quiet test", master_volume=0.5,
                           allowed_games=frozenset({"NotAGame"}))
    rig = Rig([GameA, GameB], quiet_profile=stranger,
              select_idle_timeout_secs=NO_AMBIENT_SECS)
    hold_quiet_combo(rig)
    assert rig.sounds._master_volume == 0.5, "the volume cap still applies"
    rig.step()
    rig.step({ControllerSwitchEnum.NEXT_GAME})
    rig.step()
    rig.step({ControllerSwitchEnum.NEXT_GAME})
    assert {"GameA", "GameB"} <= set(rig.sounds.played), "full roster still cycles"


def test_quiet_hold_during_game_resets_then_toggles():
    rig = Rig([GameA, GameB], quiet_profile=QUIET_TEST_PROFILE,
              select_idle_timeout_secs=NO_AMBIENT_SECS)
    rig.start_selected_game()
    rig.step(QUIET_HOLD)  # RESET's own press action cancels the game
    assert rig.state == "cancel"
    rig.step(QUIET_HOLD)
    assert rig.state == "await_input"
    rig.step(QUIET_HOLD, secs=gc_mod.QUIET_HOURS_HOLD_SECS)
    assert rig.sounds._master_volume == 0.5


def test_quiet_hold_during_ambient_ejects_then_toggles():
    rig = Rig([GameA, GameB], quiet_profile=QUIET_TEST_PROFILE)
    rig.step(secs=SELECT_IDLE_TIMEOUT_SECS + 0.1)
    assert isinstance(rig.game, Ambient)
    rig.step(QUIET_HOLD)  # NEXT_GAME's own press action ejects ambient
    assert rig.state == "cancel"
    rig.step(QUIET_HOLD)
    assert rig.state == "await_input"
    rig.step(QUIET_HOLD, secs=gc_mod.QUIET_HOURS_HOLD_SECS)
    assert rig.sounds._master_volume == 0.5


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items())
             if name.startswith("test_") and callable(fn)]
    for fn in tests:
        fn()
        print(f"{fn.__name__} OK")
    print(f"\nAll {len(tests)} tests passed")
