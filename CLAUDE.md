# Illuminatrix

Interactive art installation: 7 towers with DMX lights, JACK audio, and
stomp-pad switches on a serial link, driven by a 30fps game loop
(play.py) on a Raspberry Pi 5. This repo is often checked out on the
live installation Pi itself.

## Commands

- Tests: `poetry run pytest tests/` (each test file also runs standalone:
  `python tests/test_x.py`)
- Lint: `ruff check .`
- Run: `python play.py {embedded|web|print} [--allgames] [--no-sound]
  [--debug LOGGER] [Game ...]`
- Desk simulator (no hardware): `python play.py print --allgames <Game>` —
  keys 1-7 are towers, enter/space/esc the controller buttons, q latches
  the quiet-hours combo (next+reset held) since a terminal can't hold keys
- Bench rigs (need hardware): `python systems/concrete/dmx_controller.py`,
  `python systems/concrete/JackSoundSystem.py [bank_dir] [sound]`,
  `python experiments/pad_tower_map_test.py` (tower/pad wiring check)

## Hard rules

- Never touch hardware from tests or ad-hoc commands: no `/dev/ttyACM0`,
  no JACK server, no olad. Use the established fakes: `FakeSerial`
  (test_switch_input_system.py), `FakeJack` (test_jack_mixer.py),
  `FakeLoader` (test_sound_bank_cache.py).
- The installation may be running under systemd on this Pi. Don't run
  `play.py embedded`, restart services, or claim the serial port without
  asking.
- Commit only what the task changed — no blanket `git add -A` (a swept-in
  desk-test tweak once shipped a 3-second idle timeout).
- PRs merge with merge commits, not squash.
- TODO.md is the canonical task list; groom it as work lands.

## Architecture

- `SystemSingletonFactory` owns all construction and wiring: transports
  (`DmxController`, `SerialController`, `JackMixer`) are built from
  `ENVIRONMENT_CONTEXT` config dicts and injected. Systems never
  self-construct their transports. Factory type gates use `issubclass`.
- `get_active_systems()` defines the per-frame update order: transports
  first, then light/sound/input. play.py just iterates the list.
- Shared lifecycles are refcounted (`SerialController.startup/shutdown`
  is driven by the loop and both systems that use it, in any order).
- Games declare `SOUND_BANK` (class attribute, `None` = silent) and load
  it themselves via `load_sound_bank(self.SOUND_BANK)`; play.py derives
  the boot preload from the run's games. A mid-show "Loading sound bank"
  INFO line means a declaration drifted.

## Conventions

- Degrade, don't crash: missing hardware costs its subsystem, never the
  process. Self-heal from `update()` with rate-limited reconnects, and
  repeat an ERROR every ~30s while degraded so the journal shows it.
- `play()` always returns a `Sound`; failures (unknown key, mixer down)
  return an already-finished `NullSound` — never `None` the caller must
  guard, and never an object whose `is_done()` can't come true.
- `JackSound.mix_into` and `JackMixer.process` run on the JACK realtime
  thread: no logging, minimal allocation, and they must never block or
  loop unboundedly.
- Durations are named `*_secs`; timing uses `time.monotonic()` (wall
  clock jumps on a Pi with no RTC). Colors are 0.0-1.0 floats at the
  game layer, 0-255 ints at the transports.
- INFO is the operational journal (connects, health, preload timings).
  The console default is still WARNING pending the logging-overhaul TODO,
  so use `--debug <logger>` to see INFO/DEBUG for a module.
- Constructors fed from `ENVIRONMENT_CONTEXT` tolerate unknown keys;
  prefer warning about them like `DmxController` does.
