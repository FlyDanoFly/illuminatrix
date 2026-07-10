# Illuminatrix TODO

Last groomed: 2026-07-08, with `sound-system-review` (PR #29) reviewed and
hardened: sound banks preload at boot from game declarations, JackMixer
self-heals, `play()` always returns a Sound (failures come back already
finished), and CLAUDE.md now records the project's rules.

## In flight

- [ ] Sound-reactive ambient lights — built 2026-07-08 (working tree):
      `JackMixer.process()` meters per-tower mean-square output energy,
      `JackSoundSystem.update()` smooths it into perceptual 0-1 levels
      (instant attack, ~0.25s release, -40dB floor), exposed via
      `SoundSystem.get_tower_levels()` (silent systems report zeros) /
      `Tower.get_sound_level()`. ColorCycle whitens each tower's cycle
      color by its speaker's level. Needs a hardware look-pass: the
      tuning knobs are `LEVEL_FLOOR_DB`, `LEVEL_RELEASE_SECS`
      (JackSoundSystem.py) and `SOUND_LEVEL_WHITENING` (ColorCycle.py)
- [ ] Soak test the DMX rewrite: the stall root cause is fixed in code but needs a
      long run to confirm (stall WARNINGs and the 5-minute "DMX health" INFO lines
      are the signal; `kill -USR1` for a live stack dump if anything wedges). The
      soak now also covers the reworked serial path — per-phase stall warnings
      name `SerialController.update` if the exchange ever eats the frame
- [x] Real game-driven stomp-pad RGB — merged to `main` in PR #28
      (`inputsystem-unify`). Hardware check passed 2026-07-07 with one light
      wired: pads follow tower colors through the ColorCycle ambient, including
      per-tower hues. When all seven lights are wired, run
      `experiments/pad_tower_map_test.py` to verify the physical tower/pad ↔ enum
      mapping (a mismatch looks like wrong pad colors)
- [ ] Decide whether `LightPos.Pad_top`/`Pad_bottom` stay merged (one physical
      RGB per pad today) or the hardware grows a second addressable LED
- [x] Fix or drop the PRINT environment — fixed 2026-07-07 on
      `sound-system-review`: `PrintSound`/`PrintSoundSystem` implement the full
      abstract contract and the factory constructs all three PRINT systems.
      Now usable as a desk simulator (`play.py print --allgames <Game>`):
      keyboard input (1-7 = towers, enter/space/esc = controller; degrades to
      no-input when stdin isn't a TTY), change-driven throttled light printing
      (~5 lines/sec instead of ~200), and `NullSoundSystem` works and is
      selected by `play.py --no-sound` (any environment). Possible future
      tier: ANSI 24-bit color blocks as live towers
- [x] Sound bank loading stalls — measured 2026-07-07 on hardware: the ambient
      bank (919MB decoded) froze the game loop 4.34s on every entry, including
      each 2-minute idle timeout; all banks total ~1.7GB decoded against the
      Pi's 8GB. Decision: preload at boot + path-keyed cache (done on
      `sound-system-review`). Each game declares `SOUND_BANK` and asks for it
      via `load_sound_bank(self.SOUND_BANK)`; play.py derives the preload set
      from the run's games plus `GameController.INTRO_SOUND_BANK`, so a
      single-game dev run preloads only what it needs. Streaming shelved
      unless the game grows or the hardware slims; an unexpected "Loading
      sound bank" INFO mid-show means a game's declaration and its ask drifted
- [ ] Make `ColorCycle` runnable from the command line: it's extracted from the
      selectable games as the ambient game before selection happens, so
      `play.py print --allgames ColorCycle` says "No games selected" — surprising
      for the game you most want to smoke-test
- [ ] **Deploy note: firmware and Pi code must ship together** — mismatched framing
      halves mean all switches read released

## Soak test stall — root cause found and fixed (2026-07-06)

Symptom was multi-minute pauses with no serial I/O. SIGUSR1 stack dump caught the
loop blocked in a socket `send()` to olad inside `SendDmx`. OLA's client is async:
every send gets a response that must be consumed by the wrapper's event loop, which
the old example-code controller never ran — unread responses filled the socket
buffers until olad stopped servicing the connection and the blocking send wedged
the whole loop (worsening over the soak: 48s → 102s → 116s).

Fixed by rewriting `DmxController` from the ground up (`dmx-rewrite` branch): DMX
worker thread owns all I/O, main loop writes to a latest-wins channel buffer and can
never block on DMX; every response is consumed by the wrapper's Run() loop; socket
has real timeouts; ack-watchdog + rate-limited reconnect like the serial path.
Original example code preserved at `experiments/dmx_reference/dmx_controller.py`.

## Branches to land

All landed as of 2026-07-07: `serial-response-framing` → `festival-prep` →
`main`, then `dmx-rewrite`, then `inputsystem-unify` (PR #28). Stale branches
deleted, including `git-commit-from-critical-nw-added-to-todo` (its Critical NW
hash lives under Reference below). The firmware/Pi deploy note moved to In flight.

## Festival-prep roadmap (from the 2026-07-04 review)

1. [ ] Logging overhaul: `dictConfig` + `--log-level` with per-module overrides, convert
       ~38 `print()`s to logging (the new `--debug` flag is a first step). The
       default console level should become INFO: today's WARNING default hides
       the operational breadcrumbs the journal exists for — the 5-minute DMX
       health lines the soak plan calls "the signal", mixer/serial "connected"
       lines, and the sound bank preload summary are all invisible without
       `--debug`
2. [x] OLA `DmxController` fixes — rewritten from scratch 2026-07-06 on `dmx-rewrite`
       (threaded, self-healing, responses always consumed; fixes the AddEvent leak,
       the olad-restart crash, and the soak stall). Pending soak validation.
3. [ ] Game-loop exception boundary + systemd `Restart=always`
4. [x] `JackSound.mix_into` bug — fixed 2026-07-07 on `sound-system-review`: the
       block and fade segment are computed once per callback and mixed identically
       into every mapped channel, with regression tests (`tests/test_jack_sound.py`)
5. [ ] Cleanup pass: CWD-dependent
       paths, add a type checker, grow the pytest suite for pure logic (input-system,
       serial-protocol, DMX, sound suites landed 2026-07 — 77 tests), festival
       `config.toml`, README rewrite. From the PR #29 reviews: extract the
       reconnect/rate-limited-log idiom now hand-rolled three times (serial, DMX,
       JACK controllers), and move the TTY guard from KeyboardInputSystem into
       KBHit where the termios dependency lives

## Assets repo (sound banks)

- [ ] Create the empty GitHub repo `FlyDanoFly/illuminatrix-assets` (private recommended
      — freesound licenses) and push the nested `sound_banks/` repo — the sound data
      currently lives only in that nested repo on this Pi
- [x] `git gc --prune` for the abandoned sound-bank commit — nothing left to prune as
      of 2026-07-07: `.git` is 2.1 MB and commit 1613201 is no longer in the object
      store (a past gc must have taken it)
- [ ] Prune the local junk variant dirs (`.bak`/`.HIDE`/`.pre_switch`/`.old_without_trimming`)
- [ ] Mix down the six stereo sound files to mono offline — they're converted at
      every boot (double RAM during decode + a WARNING each): in
      `lucy_magic_8_ball/sounds/`: sound-1-167181.mp3, gong-255733.mp3; and
      level-up-47165.wav + 812364__cvltiv8r__jarbled-sub.wav, which appear in
      both `lucy_whack_a_mole_1/sounds/` and `simon/game/`

## Backlog — gameplay and features (carried from the old list)

- [ ] Cleanup pass (general)
- [x] Make system initialization and lifecycle consistent — done via
      `inputsystem-unify`: every per-frame participant is a `BaseSystem` driven
      from the factory's `get_active_systems()` list in a stated order, and the
      shared controllers use refcounted startup/shutdown
- [ ] Fix all the sounds everywhere
- [ ] Add streaming
- [ ] Soft startup for selection mode
- [ ] Win condition for Simon
- [ ] Death condition for Whack-a-cow
- [ ] Win condition for Whack-a-cow
- [ ] Debouncing in the input system (the serial link already holds state through
      missed frames; this item is about physical contact bounce)

## Reference

- Final Critical NW code: commit `b0711c83c70acf60a610321d157de59da874f3e0`
