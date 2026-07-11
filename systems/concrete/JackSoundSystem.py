"""Jack Sound System for Python - A simple sound mixer using JACK Audio Connection Kit and lightly mimicing the pygame interafce.

This is evolving from a very iterative process, needs a decent amount of cleanup.
Most important next goal is to get it running with a simulation.
"""

import logging
import math
import random
import sys
import threading
import time
import typing
from dataclasses import dataclass
from enum import Enum

import jack
import json5
import numpy
import soundfile

from bases.SoundSystem import NullSound, Sound, SoundSystem
from constants.constants import TowerEnum

logger = logging.getLogger(__name__)


JACKMIXER_USE_SERVER = True
JACK_SERVER_NAME = "illuminatrix_jack_server_mixer"

# Minimum time between attempts to (re)connect to the JACK server
JACK_RECONNECT_INTERVAL_SECS = 2.0
# Tower levels: mean-square energy at or below this dB reads as 0.0, full
# scale (0 dB) as 1.0. -40 dB spans roughly "quiet ambience" to "loud"
LEVEL_FLOOR_DB = -40.0
# Release time for the smoothed tower levels — the meter falls to ~63% of
# the way toward the new quieter value in this many seconds. Attack is
# instant: lights should hit with the sound, not after it
LEVEL_RELEASE_SECS = 0.25
# While disconnected, repeat an ERROR at this interval so a silent
# installation is visible in the log stream, not just one line at startup
JACK_DISCONNECTED_LOG_INTERVAL_SECS = 30.0


class MixerState(Enum):
    INIT = 0
    STARTED = 1
    DISCONNECTED = 2
    SHUTDOWN = 3


class SoundType(Enum):
    SOUND = "sound"
    MUSIC = "music"
    AMBIENCE = "ambience"
    VOICE = "voice"


@dataclass
class SoundData:
    key: str
    filename: str
    sound_type: SoundType
    data: numpy.ndarray
    samplerate: int

    def create_sound(self, volume: float = 1.0, num_loops: int = 0) -> Sound:
        """Create a Sound object from this SoundData."""
        # TODO: formalize the key, filename, and sound_type usage
        ranby = self.key + "-" + "".join(random.choice("abcdefghij") for _ in range(8))
        return JackSound(filename=ranby, data=self.data, samplerate=self.samplerate, volume=volume, num_loops=num_loops)


def load_sound_file(filename: str) -> tuple[numpy.ndarray, int]:
    """Load a sound file and return its data and samplerate."""
    try:
        data, samplerate = soundfile.read(filename, dtype='float32')
        if len(data.shape) > 1:
            logger.warning("Loaded multitrack sound file %s, converting to mono.", filename)
            data = data.sum(axis=1) / data.shape[1]
        return data, samplerate
    except Exception as e:
        logger.error("Error loading sound file %s: %s", filename, e)
        raise


def load_sound_bank(directory: str) -> dict[str, SoundData]:
    """
    Look for a sound_bank_manifest.json file in the directory, and if it exists, load the sounds listed in it.

    The manifest should be a JSON5 file with the following structure:
    {
        "sound_name": {
            "file": "path/to/sound/file.wav",
            "type": "sound",  // or "music", "ambience", "voice"
        },
        ...
    }
    """
    sound_bank = {}
    manifest_file = f"{directory}/sound_bank_manifest.json"
    try:
        with open(manifest_file, 'r') as f:
            manifest = json5.load(f)
            for name, sound_info in manifest.items():
                filename = sound_info['file']
                full_path = f"{directory}/{filename}"
                try:
                    sound_type = SoundType(sound_info['type'])
                except ValueError:
                    logger.warning("Unknown sound type %r for %s, defaulting to 'sound'", sound_info['type'], name)
                    sound_type = SoundType.SOUND

                # TODO: add support for other sound types, for now load everything as 'sound'
                file_start_secs = time.monotonic()
                data, samplerate = load_sound_file(full_path)
                logger.debug(
                    "Loaded %s (%.1fs of audio) in %.2fs",
                    full_path, len(data) / samplerate, time.monotonic() - file_start_secs,
                )
                sound_bank[name] = SoundData(
                    key=name,
                    filename=filename,
                    sound_type=sound_type,
                    data=data,
                    samplerate=samplerate,
                )
    except FileNotFoundError:
        logger.warning("No sound bank manifest found in %s", directory)
        raise
    except ValueError as e:
    # except json5.JSONDecodeError as e:
        logger.error("Error decoding JSON from sound bank manifest: %s", e)
        raise
    except KeyError as e:
        logger.error("Missing key in sound bank manifest: %s", e)
        raise
    return sound_bank


def _energy_to_level(mean_square: float) -> float:
    """Map a block's mean-square energy to a perceptual 0.0-1.0 level:
    LEVEL_FLOOR_DB reads as 0.0, full scale (0 dB) as 1.0. The log
    mapping is what makes quiet ambience visible instead of parking the
    meter near zero until a peak."""
    if mean_square <= 0.0:
        return 0.0
    db = 10.0 * math.log10(mean_square)
    if LEVEL_FLOOR_DB >= 0.0:
        # Degenerate tuning (floor at or above full scale): act as a hard
        # gate at the floor instead of dividing by zero — a bad knob value
        # must cost fidelity, not the process
        return 1.0 if db >= LEVEL_FLOOR_DB else 0.0
    return min(1.0, max(0.0, (db - LEVEL_FLOOR_DB) / -LEVEL_FLOOR_DB))


class JackSound(Sound):
    """A class representing a sound that can be played by the mixer.

    This class can be initialized from a file or raw data, and supports looping and volume control.
    It also supports fading out the sound over a specified duration.
    """
    def __init__(self, filename: str = '', data: numpy.ndarray | None = None, samplerate: int | None = None, volume: float = 1.0, num_loops: int = 0):
        """Initialize a Sound object.

        There are two ways to initialize a Sound object:
        1. From a file, using the filename parameter.
        2. From raw data, using the data and samplerate parameters.
        If both filename and data are provided, data and samplerate takes precedence.
        """
        self.data: numpy.ndarray
        self.samplerate: int
        # TODO: formalize the key, filename, and sound_type usage
        self.key: str = filename  # Use filename as key, can be overridden later
        if data is not None and samplerate is not None:
            # If data and samplerate are provided, use them directly
            self.data = data
            self.samplerate = samplerate
        elif filename:
            # If a filename is provided, read the sound file
            self.data, self.samplerate = load_sound_file(filename)
        else:
            raise ValueError("Either filename or data and samplerate must be provided")

        assert len(self.data.shape) == 1, "Sound data must be 1D (mono), got shape: {}".format(self.data.shape)
        self.channels: int = 1
        self.position: int = 0
        self.volume: float = volume
        self.loops: int = num_loops
        # TODO: if I get into adding reltime effects, make this an effect
        self.fade_out_active: bool = False
        # A zero-length sound (empty/corrupt file) is born finished —
        # otherwise mix_into's wrap loop could spin forever on it
        self.fade_out_complete: bool = len(self.data) == 0
        self.fade_out_curve = numpy.linspace(1.0, 1.0, 1, dtype=numpy.float32)
        self.fade_out_index = 0

    def is_done(self) -> bool:
        # Called from the JACK process callback: keep it allocation- and
        # logging-free
        if self.fade_out_complete:
            return True
        if self.fade_out_active:
            return False
        if self.loops != 0:
            # Loops remain (negative means forever); position may rest
            # exactly at the end between callbacks — the next one wraps
            return False
        return self.position >= len(self.data)

    def start_fade_out(self, fade_secs: float) -> None:
        if self.fade_out_complete:
            return
        # Restarting mid-fade begins the new curve at the current
        # amplitude, not full volume — a reset to full is an audible pop
        # (e.g. a game's 0.25s stop_all overlapped by shutdown's 1s one).
        # The len guard matters: a zero-frame fade (fade_secs < one
        # sample) leaves an empty active curve, and indexing it crashes
        if self.fade_out_active and len(self.fade_out_curve) > 0:
            start_amplitude = self.fade_out_curve[min(self.fade_out_index, len(self.fade_out_curve) - 1)]
        else:
            start_amplitude = self.volume
        total_frames = int(fade_secs * self.samplerate)
        self.fade_out_curve = numpy.linspace(start_amplitude, 0.0, total_frames, dtype=numpy.float32)
        self.fade_out_index = 0
        self.fade_out_active = True

    def stop(self) -> None:
        """Stop the sound immediately, without fading out."""
        self.fade_out_active = False
        self.fade_out_complete = True
        self.position = len(self.data)
        # A looping sound must not wrap in the one mix_into that can run
        # between stop() and the mixer pruning it
        self.loops = 0

    def mix_into(self, output_buffers: list[numpy.ndarray], channel_map: list[TowerEnum]) -> None:
        """Mix this sound's next block into every mapped channel.

        The block (and its fade-curve segment) is computed once and added
        identically to each channel; per-sound state advances once per
        callback, no matter how many towers the sound plays on. A looping
        sound wraps within the block, so loop boundaries are gapless
        instead of leaving up to one JACK period of silence.
        """
        frames = len(output_buffers[0])

        segments = []
        filled = 0
        while filled < frames:
            remaining = len(self.data) - self.position
            if remaining <= 0:
                if self.loops == 0:
                    break
                self.loops -= 1
                self.position = 0
                remaining = len(self.data)
                if remaining == 0:
                    # Zero-length data can never fill the block; without
                    # this the wrap loop spins forever on the JACK thread
                    break
            take = min(frames - filled, remaining)
            segments.append(self.data[self.position:self.position + take])
            self.position += take
            filled += take
        if len(segments) == 1:
            block = segments[0]
        elif segments:
            block = numpy.concatenate(segments)
        else:
            block = self.data[:0]

        if self.fade_out_active or self.fade_out_complete:
            fade_remaining = len(self.fade_out_curve) - self.fade_out_index
            fade_len = min(len(block), fade_remaining)
            block = block[:fade_len] * self.fade_out_curve[self.fade_out_index:self.fade_out_index + fade_len]
            self.fade_out_index += fade_len
            if self.fade_out_index >= len(self.fade_out_curve) or fade_len <= 0:
                self.fade_out_active = False
                self.fade_out_complete = True
        elif self.volume != 1.0:
            # At unity volume block stays a read-only view of self.data —
            # skipping the multiply avoids a per-callback array allocation
            # on the JACK realtime thread. NEVER mutate block in place:
            # self.data is the bank-cache array shared by every play of
            # this sound, so `block *= x` would corrupt the cached audio
            block = block * self.volume

        for target_channel in (tower_enum.value - 1 for tower_enum in channel_map):
            if target_channel >= len(output_buffers):
                continue
            output_buffers[target_channel][:len(block)] += block


class JackMixer:
    """Mixes Sound objects into JACK output ports, one port per tower.

    Connection lives in startup(), not __init__, and failures degrade
    instead of raising: a missing JACK server costs sound output, never
    the process. update() — driven every frame by JackSoundSystem —
    notices a dead server, drops the sounds it can no longer finish, and
    retries the connection, rate limited.
    """

    def __init__(
            self,
            name: str = "jack_mixer",
            use_server: bool = JACKMIXER_USE_SERVER,
            servername: str = JACK_SERVER_NAME,
    ):
        # TODO: perhaps make the channel auto detected, as well as the force to stereo?
        self.name = name
        self.use_server = use_server
        self.servername = servername
        self.client: jack.Client | None = None
        self.outports: list[jack.OwnPort] = []
        self.active_sounds: list[tuple[Sound, list[TowerEnum]]] = []
        self.lock: threading.Lock = threading.Lock()
        self.state: MixerState = MixerState.INIT
        self.force_play_on_all_channels: bool = False
        # Mean-square energy of the last rendered block, one slot per
        # tower, written by process() on the JACK thread and read by the
        # game loop. Fixed-size for its whole life so the two threads
        # never race on a reallocation; a torn read costs one frame of
        # stale meter, which no one can see
        self._channel_energy = numpy.zeros(len(TowerEnum), dtype=numpy.float32)
        # Set from JACK's shutdown-callback thread; handled in update()
        self._server_went_away: bool = False
        self._last_connect_attempt_secs: float = float("-inf")
        self._last_disconnected_log_secs: float = float("-inf")

    def process(self, _: int):
        # the parameter is the number of frames to process
        output_buffers = [
            numpy.frombuffer(port.get_buffer(), dtype=numpy.float32)
            for port in self.outports
        ]
        # Zero before the state check so the shutdown window plays
        # silence instead of repeating the last rendered buffer
        for buf in output_buffers:
            buf[:] = 0.0

        if self.state != MixerState.STARTED:
            self._channel_energy[:] = 0.0
            return

        with self.lock:
            still_playing = []
            for sound, channel_map in self.active_sounds:
                # Never mix a finished sound. This is the invariant the
                # per-Sound guards (born-complete empty data, stop()
                # zeroing loops) defend in depth; checking here keeps a
                # future Sound state from rediscovering it the hard way
                if sound.is_done():
                    continue
                sound.mix_into(output_buffers, channel_map)
                if not sound.is_done():
                    still_playing.append((sound, channel_map))
            self.active_sounds = still_playing

        # Meter the mixed output per tower for the game loop's
        # get_tower_levels(). dot() returns a scalar — no per-callback
        # array allocation. Extra physical ports beyond the seven towers
        # (an 8-channel interface) simply go unmetered
        for i, buf in enumerate(output_buffers):
            if i >= len(self._channel_energy):
                break
            self._channel_energy[i] = numpy.dot(buf, buf) / len(buf)

    def startup(self):
        if self.state != MixerState.INIT:
            raise RuntimeError("Mixer can only be started from INIT state")
        # The metering dot() in process() is the only BLAS-routed call in
        # this process, and OpenBLAS does lazy first-call setup (buffers,
        # possibly threads). Warm it here so that stall never lands on the
        # JACK realtime thread
        warm = numpy.ones(8, dtype=numpy.float32)
        numpy.dot(warm, warm)
        if self._try_connect():
            self.state = MixerState.STARTED
        else:
            self.state = MixerState.DISCONNECTED
            logger.error(
                "JACK server unavailable at startup — no sound until it appears, retrying"
            )

    def update(self) -> None:
        """Per-frame maintenance, driven by JackSoundSystem: notice a dead
        server, tear down its client, and reconnect (rate limited)."""
        if self.state not in (MixerState.STARTED, MixerState.DISCONNECTED):
            return
        if self._server_went_away:
            self._server_went_away = False
            logger.error(
                "JACK server went away — dropping %d active sounds, reconnecting",
                len(self.active_sounds),
            )
            self._teardown_client()
            self.state = MixerState.DISCONNECTED
        if self.state == MixerState.DISCONNECTED:
            if self._try_connect():
                self.state = MixerState.STARTED
            else:
                self._log_disconnected()

    def _try_connect(self) -> bool:
        """Open a client, register ports, activate. Rate limited so a dead
        server doesn't get hammered every frame."""
        now = time.monotonic()
        if now - self._last_connect_attempt_secs < JACK_RECONNECT_INTERVAL_SECS:
            return False
        self._last_connect_attempt_secs = now
        client = None
        try:
            if self.use_server:
                client = jack.Client(self.name, no_start_server=True, servername=self.servername)
            else:
                client = jack.Client(self.name)
            client.set_process_callback(self.process)
            client.set_shutdown_callback(self._on_server_shutdown)
            client.activate()
            ports = []
            system_ports = client.get_ports(is_physical=True, is_input=True, is_audio=True, is_midi=False)
            for i, system_port in enumerate(system_ports, start=1):
                outport = typing.cast("jack.OwnPort", client.outports.register(f"out_{i}"))
                client.connect(outport, system_port)
                ports.append(outport)
            if not ports:
                # A server with no playback hardware (interface unplugged,
                # dummy backend) must count as disconnected: mix_into on an
                # empty buffer list would raise on the JACK thread, and a
                # "connected" state would never retry when hardware appears
                raise jack.JackError("no physical playback ports found")
        except jack.JackError as e:
            logger.debug("JACK connect attempt failed: %s", e)
            if client is not None:
                try:
                    client.close()
                except jack.JackError:
                    pass
            return False
        self.force_play_on_all_channels = len(ports) == 2
        if self.force_play_on_all_channels:
            # If we have exactly two output ports, force them to be stereo
            logger.info("Stereo output detected, forcing stereo playback on all channels.")
        self.outports = ports
        self.client = client
        # Reset so a future outage logs immediately again
        self._last_disconnected_log_secs = float("-inf")
        logger.info("Mixer connected to JACK (%d outputs)", len(ports))
        return True

    def _on_server_shutdown(self, status, reason) -> None:
        # Called on JACK's thread; defer all teardown to update() on the
        # game loop, where the lock and client are safe to touch
        self._server_went_away = True

    def _log_disconnected(self) -> None:
        now = time.monotonic()
        if now - self._last_disconnected_log_secs < JACK_DISCONNECTED_LOG_INTERVAL_SECS:
            return
        self._last_disconnected_log_secs = now
        logger.error("JACK server unavailable — no sound until it returns")

    def _teardown_client(self) -> None:
        client, self.client = self.client, None
        self.outports = []
        # No callbacks means no fresh meter values; a stale loud reading
        # would freeze the lights bright for the whole outage
        self._channel_energy[:] = 0.0
        with self.lock:
            # Sounds can't finish without process callbacks; games gating
            # on are_any_sounds_playing() must not wait forever
            self.active_sounds = []
        if client is None:
            return
        try:
            client.deactivate()
            client.close()
        except jack.JackError as e:
            logger.debug("Ignoring error closing dead JACK client: %s", e)

    def shutdown(self):
        if self.state in (MixerState.SHUTDOWN, MixerState.INIT):
            return
        self.state = MixerState.SHUTDOWN
        logger.info("Shutting down JACK mixer...")
        self._teardown_client()
        logger.info("Mixer shut down cleanly.")

    def play(self, sound: Sound, channel_map: list[TowerEnum] | TowerEnum | None = None) -> bool:
        """Play a sound on the mixer. Returns True if the sound was
        enqueued, False if it was dropped (JACK disconnected) — callers
        must not hand a dropped Sound to game code, because a sound the
        mixer never advances reports is_done() False forever.

        Args:
            sound (Sound): The sound to play.
            channel_map (list[TowerEnum]): A list of channel indices to play the sound on. Defaults to all channels.
        """
        if self.state == MixerState.INIT:
            raise RuntimeError("Mixer must be started to play sounds")
        if self.state != MixerState.STARTED:
            logger.warning("JACK not connected, dropping sound")
            return False
        if channel_map is None or self.force_play_on_all_channels:
            channel_map = list(TowerEnum)
        if not isinstance(channel_map, list):
            channel_map = [channel_map]
        with self.lock:
            self.active_sounds.append((sound, channel_map))
        return True

    def stop_all(self, fade_secs: float = 0.5):
        with self.lock:
            for sound, _ in self.active_sounds:
                sound.start_fade_out(fade_secs)

    def is_anything_playing(self):
        return bool(self.active_sounds)

    def get_channel_energy(self) -> numpy.ndarray:
        """Mean-square energy of the last rendered block, indexed by
        tower (TowerEnum.value - 1). Written on the JACK thread; treat
        the returned array as read-only."""
        return self._channel_energy


SHUTDOWN_FADE_SECS = 1.0
# Bound the shutdown fade wait: if the JACK server died mid-run the
# process callback never runs, sounds never finish, and an unbounded
# wait would hang the whole shutdown
SHUTDOWN_FADE_GRACE_SECS = 1.0


class JackSoundSystem(SoundSystem):
    def __init__(self, mixer: JackMixer, **_):
        super().__init__()
        self.mixer = mixer
        self.sound_bank: dict[str, SoundData] = {}
        self._bank_cache: dict[str, dict[str, SoundData]] = {}
        self._tower_levels: dict[TowerEnum, float] = {
            tower_enum: 0.0 for tower_enum in TowerEnum
        }

    def startup(self) -> None:
        """Start the JACK mixer (degrades to silence if the server is
        missing; the mixer keeps retrying from update())."""
        self.mixer.startup()

    def preload_sound_banks(self, paths: list[str]) -> None:
        """Warm the bank cache before the game loop starts — play.py
        derives the list from the run's games' SOUND_BANK declarations,
        so a game's own load_sound_bank ask becomes a switch instead of
        seconds of frozen loop."""
        start_secs = time.monotonic()
        for path in paths:
            try:
                self._load_bank_cached(path)
            except Exception:
                # A broken bank costs its game's sounds, not the boot;
                # this ERROR names it while someone is still watching
                logger.exception("Failed to preload sound bank %s", path)
        logger.info(
            "Preloaded %d sound banks in %.1fs",
            len(self._bank_cache), time.monotonic() - start_secs,
        )

    def shutdown(self) -> None:
        """Fade everything out, then shut down the JACK mixer."""
        self.mixer.stop_all(fade_secs=SHUTDOWN_FADE_SECS)
        deadline = time.monotonic() + SHUTDOWN_FADE_SECS + SHUTDOWN_FADE_GRACE_SECS
        while self.mixer.is_anything_playing() and time.monotonic() < deadline:
            time.sleep(0.05)
        if self.mixer.is_anything_playing():
            logger.warning(
                "Sounds still playing %.1fs after the shutdown fade began, shutting down anyway",
                SHUTDOWN_FADE_SECS + SHUTDOWN_FADE_GRACE_SECS,
            )
        self.mixer.shutdown()

    def update(self, delta_secs: float) -> None:
        """Audio itself renders on JACK's thread; this drives the mixer's
        housekeeping (server-death detection and reconnect) and refreshes
        the smoothed per-tower levels games read."""
        self.mixer.update()
        self._update_tower_levels(delta_secs)

    def _update_tower_levels(self, delta_secs: float) -> None:
        """Fold the mixer's raw per-block energy into the smoothed
        perceptual levels: instant attack (lights hit with the sound),
        exponential-style release over LEVEL_RELEASE_SECS (they breathe
        out instead of flickering at the frame rate)."""
        energy = self.mixer.get_channel_energy()
        release = min(1.0, delta_secs / LEVEL_RELEASE_SECS) if delta_secs > 0 else 0.0
        for i, tower_enum in enumerate(TowerEnum):
            raw = _energy_to_level(float(energy[i]))
            smoothed = self._tower_levels[tower_enum]
            if raw >= smoothed:
                smoothed = raw
            else:
                smoothed += (raw - smoothed) * release
            self._tower_levels[tower_enum] = smoothed

    def get_tower_levels(self) -> dict[TowerEnum, float]:
        """Smoothed 0.0-1.0 output level per tower — see SoundSystem.
        In the two-port stereo bench fallback only towers 1 and 2 carry
        meters; the rest read 0.0."""
        return dict(self._tower_levels)

    def render(self) -> None:
        """Audio renders on JACK's thread; nothing to do per frame."""
        pass

    def load_sound_bank(self, path: str) -> None:
        """Switch the current sound bank, loading and caching it on first
        use. play.py preloads every bank the run's games declare, so
        mid-show calls should be cache hits — a load here means a
        SOUND_BANK declaration drifted from this ask (or a non-game
        component grew a bank play.py doesn't know about), and it stalls
        the game loop (the ambient bank measured 4.3s)."""
        self.sound_bank = self._load_bank_cached(path)

    def _load_bank_cached(self, path: str) -> dict[str, SoundData]:
        key = path.rstrip("/")
        cached = self._bank_cache.get(key)
        if cached is not None:
            logger.debug("Sound bank %s served from cache", path)
            return cached
        logger.info("Loading sound bank from %s", path)
        start_secs = time.monotonic()
        bank = load_sound_bank(path)
        elapsed_secs = time.monotonic() - start_secs
        audio_secs = sum(len(sd.data) / sd.samplerate for sd in bank.values())
        logger.info(
            "Loaded sound bank %s: %d sounds, %.1fs of audio, in %.2fs",
            path, len(bank), audio_secs, elapsed_secs,
        )
        self._bank_cache[key] = bank
        return bank

    def play(
            self,
            sound: str,
            tower_enums: list[TowerEnum] | None = None,
            volume: float = 1.0,
            num_loops: int = 0) -> Sound:
        """Play a sound from the sound bank. Always returns a Sound: on
        failure (unknown key, mixer down) an already-finished NullSound,
        so game code gating on is_done() moves on without None guards."""
        if sound not in self.sound_bank:
            logger.warning("Sound %s not found in sound bank", sound)
            return NullSound()
        play_on_tower_enums: list[TowerEnum] = tower_enums or list(TowerEnum)
        sound_data = self.sound_bank[sound]
        snd = sound_data.create_sound(volume=volume, num_loops=num_loops)
        if not self.mixer.play(snd, play_on_tower_enums):
            # Dropped (JACK disconnected): a Sound the mixer never
            # advances would report is_done() False forever
            return NullSound()
        return snd

    def stop_all(self, fade_secs: float = 0.25):
        self.mixer.stop_all(fade_secs)

    def are_any_sounds_playing(self) -> bool:
        """Check if any sounds are currently playing."""
        return self.mixer.is_anything_playing()

if __name__ == "__main__":
    # Bench smoke test: loops the first sound of a bank through JACK.
    # Needs a running JACK server; ^C to quit.
    #
    #     python systems/concrete/JackSoundSystem.py [bank_dir] [sound_name]
    logging.basicConfig(level=logging.DEBUG)
    system = JackSoundSystem(mixer=JackMixer())
    system.startup()
    system.load_sound_bank(sys.argv[1] if len(sys.argv) > 1 else "sound_banks/lucy_whack_a_mole_1")
    sound_name = sys.argv[2] if len(sys.argv) > 2 else next(iter(system.sound_bank))
    try:
        system.play(sound_name, volume=0.5, num_loops=-1)
        while True:
            system.update(1 / 30)
            time.sleep(1 / 30)
    except KeyboardInterrupt:
        print("Exiting")
    finally:
        system.shutdown()
