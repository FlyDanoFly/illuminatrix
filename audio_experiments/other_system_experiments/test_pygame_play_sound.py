import random
import signal
import sys
import time

import pygame

# ========== CONFIG ==========
SOUND_FILE = "boom.wav"  # Must be WAV or OGG (mono or stereo)
MIN_INTERVAL = 0.5  # seconds
MAX_INTERVAL = 2.5  # seconds

# ========== CLEAN EXIT ==========
def signal_handler(sig, frame):
    print("\nExiting cleanly.")
    pygame.quit()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# ========== INIT ==========
pygame.mixer.init(frequency=48000, channels=8)
sound = pygame.mixer.Sound(SOUND_FILE)

# ========== MAIN LOOP ==========
print("Starting random stereo playback. Press Ctrl-C to stop.")
while True:
    # Randomly choose left, right, or center
    panning = random.choice(["left", "right", "center"])
    
    if panning == "left":
        sound.set_volume(1.0, 0.0)
    elif panning == "right":
        sound.set_volume(0.0, 1.0)
    else:
        sound.set_volume(1.0, 1.0)
    
    print(f"Playing sound: {panning}")
    sound.play()

    time.sleep(random.uniform(MIN_INTERVAL, MAX_INTERVAL))

