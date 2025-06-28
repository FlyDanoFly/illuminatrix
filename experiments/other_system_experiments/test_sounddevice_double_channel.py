# Trying to play two sounds with sounddevice
# Trying the naive way, not really getting through the documentation, just trying
# This approach doesn't work
# ChatGPT thinks that I need to mix maunally with sounddevice
# I think I'll try jack again

import signal
import sys
import time

import numpy as np
import sounddevice as sd
import soundfile as sf

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

channel = 0
print(f"Playing on channel {channel + 1}")

# Create multichannel buffer with zeros
out = np.zeros((len(data), CHANNELS), dtype=np.float32)

# Insert sound data into the selected channel
out[:, channel] = data

# Play and wait
sd.play(out, samplerate=SAMPLERATE)
time.sleep(5)
sd.play(out, samplerate=SAMPLERATE)
sd.wait()

print("Done")
