import numpy as np
import sounddevice as sd
import soundfile as sf
import time
import random
import signal
import sys

# ========== CONFIG ==========

CHANNELS = 8
SAMPLERATE = 48000
MIN_INTERVAL = 0.5  # seconds
MAX_INTERVAL = 2.5  # seconds
SOUND_FILE = "LRMonoPhase4.wav"  # Must be mono or stereo
DEVICE_NAME = None  # or "hw:1,0" or a number

# ========== CLEAN EXIT ==========

def signal_handler(sig, frame):
    print("\nExiting cleanly.")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# ========== LOAD SOUND ==========

data, sr = sf.read(SOUND_FILE, dtype='float32')
if sr != SAMPLERATE:
    print(f"Resample '{SOUND_FILE}' to {SAMPLERATE}Hz for best results.")

# Force to mono by averaging if stereo
if data.ndim > 1:
    data = data.mean(axis=1)

# ========== MAIN LOOP ==========

print("Starting random channel playback. Press Ctrl-C to stop.")
if DEVICE_NAME:
    sd.default.device = DEVICE_NAME

while True:
    # Choose a random channel
    channel = random.randint(0, CHANNELS - 1)
    print(f"Playing on channel {channel + 1}")

    # Create multichannel buffer with zeros
    out = np.zeros((len(data), CHANNELS), dtype=np.float32)

    # Insert sound data into the selected channel
    out[:, channel] = data

    # Play and wait
    sd.play(out, samplerate=SAMPLERATE)
    sd.wait()

    # Sleep for random interval
    time.sleep(random.uniform(MIN_INTERVAL, MAX_INTERVAL))

