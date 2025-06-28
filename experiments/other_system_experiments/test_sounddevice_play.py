import numpy as np
import sounddevice as sd

samplerate = 48000
duration = 2
t = np.linspace(0, duration, int(samplerate * duration), endpoint=False)

# Create 8 different sine waves
signal = np.stack([0.1 * np.sin(2 * np.pi * (200 + 50 * i) * t) for i in range(8)], axis=-1)

sd.play(signal, samplerate=samplerate)
sd.wait()

