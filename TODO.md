# Illuminatrix TODO

Last groomed: 2026-07-06, during serial soak testing on the `serial-response-framing` branch.

## In flight — uncommitted work on `serial-response-framing`

- [ ] Commit the generic response framing pass (Arduino `bytePos` response builder +
      Python `extract_latest_response` returning `tuple[int, ...]`) — keeping this
- [ ] Commit the `flash.sh` SKETCH path fix (was pointing at the old
      `~/Projects/from_illuminatrix_box` checkout)
- [ ] Commit the soak-test instrumentation in `play.py`: faulthandler on SIGUSR1,
      frame-stall warnings with per-phase timing, repeatable `--debug LOGGER` flag
- [ ] Commit or fold in the stomp-pad experiment changes: `processed_color_cycle()`,
      clamp-overflow logging, `which_light` selection
- [ ] Decide what to do with untracked `arduino/ppwwdd.sh` (path-echo stub — keep or delete?)
- [ ] Replace the dummy stomp-pad color-cycle data in `SwitchInputSystem.update()`
      with real game-driven RGB (marked `TODO` in the code)

## In flight — soak test stall investigation

Symptom: runs for a while, then multi-minute pauses with no serial send/receive and
nothing in the journal. Send logs stopping with no serial ERRORs means the frame loop
itself stalls, not the serial code.

- [ ] During the next pause: `kill -USR1 $(pgrep -f play.py)` and read the stack dump
      in the journal (or `py-spy dump --pid <pid>`)
- [ ] Check the new frame-stall WARNINGs — they name the slowest phase after a stall ends
- [ ] Rule out journald rate limiting (look for "Suppressed N messages"; if LEDs keep
      animating during a "quiet" period, it's only log suppression)
- [ ] Correlate pause timestamps with `journalctl -k` (USB/ttyACM resets) and
      `journalctl -u olad` (daemon restarts)
- [ ] Prime suspect: `DmxController.SendDmx` is a synchronous socket write to olad from
      inside the frame loop — a wedged olad blocks everything, serial included

## Branches to land

- [ ] `serial-response-framing` (3 commits + the uncommitted work above) → into `festival-prep`
- [ ] `festival-prep` (5 commits: color-cycle experiment, monotonic clock, serial
      hardening + review fixes, sound_banks gitignore) → into `main`
- [ ] Delete `git-commit-from-critical-nw-added-to-todo` once this file lands (its only
      commit recorded the Critical NW hash, now under Reference below)
- [ ] **Deploy note: firmware and Pi code must ship together** — mismatched framing
      halves mean all switches read released

## Festival-prep roadmap (from the 2026-07-04 review)

1. [ ] Logging overhaul: `dictConfig` + `--log-level` with per-module overrides, convert
       ~38 `print()`s to logging (the new `--debug` flag is a first step)
2. [ ] OLA `DmxController` fixes: `AddEvent` accumulates unbounded (wrapper `Run()` is
       never called — the queued events never fire and never free); hourly olad restart
       crashes the program when the 3×0.3s retry window is outlasted — make it
       reconnect-and-carry-on like the serial path. Also a stall suspect, see above.
3. [ ] Game-loop exception boundary + systemd `Restart=always`
4. [ ] `JackSound.mix_into` bug: `fade_out_index` advances per channel, so multi-tower
       sounds fade N× too fast
5. [ ] Cleanup pass: `delta_ms`/`delta_secs` naming in GameController, CWD-dependent
       paths, add a type checker, grow the pytest suite for pure logic, festival
       `config.toml`, README rewrite

## Assets repo (sound banks)

- [ ] Create the empty GitHub repo `FlyDanoFly/illuminatrix-assets` (private recommended
      — freesound licenses) and push the nested `sound_banks/` repo
- [ ] After the assets push is verified: `git gc --prune` in this repo to drop ~1GB of
      unreachable blobs from the abandoned sound-bank commit (1613201)
- [ ] Prune the local junk variant dirs (`.bak`/`.HIDE`/`.pre_switch`/`.old_without_trimming`)

## Backlog — gameplay and features (carried from the old list)

- [ ] Cleanup pass (general)
- [ ] Make system initialization and lifecycle consistent — maybe done, verify
- [ ] Fix all the sounds everywhere
- [ ] Add streaming
- [ ] Soft startup for selection mode
- [ ] Win condition for Simon
- [ ] Death condition for Whack-a-cow
- [ ] Win condition for Whack-a-cow
- [ ] Debouncing in the input system

## Reference

- Final Critical NW code: commit `b0711c83c70acf60a610321d157de59da874f3e0`
