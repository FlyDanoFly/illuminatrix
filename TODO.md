# Illuminatrix TODO

Last groomed: 2026-07-06, after the soak-test stall was root-caused and the DMX
controller rewritten on the `dmx-rewrite` branch.

## In flight

- [ ] Soak test the DMX rewrite: the stall root cause is fixed in code but needs a
      long run to confirm (stall WARNINGs and the 5-minute "DMX health" INFO lines
      are the signal; `kill -USR1` for a live stack dump if anything wedges)
- [x] Replace the dummy stomp-pad color-cycle data in `SwitchInputSystem.update()`
      with real game-driven RGB — done on the `inputsystem-unify` branch: the
      serial link is now `StompPadController` (light sink + input source),
      `SwitchInputSystem` is a facade over it, and `DmxLightSystem` routes
      `LightPos.Pad_*` to it (pads mirror tower color by default since games set
      `LightPos.All`). Needs a hardware check: pads should follow tower colors
- [ ] Decide whether `LightPos.Pad_top`/`Pad_bottom` stay merged (one physical
      RGB per pad today) or the hardware grows a second addressable LED

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

- [ ] `dmx-rewrite` (stacked on `serial-response-framing`) → after soak validation
- [ ] `serial-response-framing` (framing + soak instrumentation + TODO rewrite) → into `festival-prep`
- [ ] `festival-prep` (5 commits: color-cycle experiment, monotonic clock, serial
      hardening + review fixes, sound_banks gitignore) → into `main`
- [ ] Delete `git-commit-from-critical-nw-added-to-todo` once this file lands (its only
      commit recorded the Critical NW hash, now under Reference below)
- [ ] **Deploy note: firmware and Pi code must ship together** — mismatched framing
      halves mean all switches read released

## Festival-prep roadmap (from the 2026-07-04 review)

1. [ ] Logging overhaul: `dictConfig` + `--log-level` with per-module overrides, convert
       ~38 `print()`s to logging (the new `--debug` flag is a first step)
2. [x] OLA `DmxController` fixes — rewritten from scratch 2026-07-06 on `dmx-rewrite`
       (threaded, self-healing, responses always consumed; fixes the AddEvent leak,
       the olad-restart crash, and the soak stall). Pending soak validation.
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
