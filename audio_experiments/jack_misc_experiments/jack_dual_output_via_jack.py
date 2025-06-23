import jack
import numpy as np

client = jack.Client("dual_output_demo")
out1 = client.outports.register("out1")  # For card 1
out2 = client.outports.register("out2")  # For card 2

samplerate = client.samplerate
frequency = 440.0
duration = 5.0
samples = int(duration * samplerate)
t = np.arange(samples) / samplerate
wave = 0.2 * np.sin(2 * np.pi * frequency * t).astype(np.float32)

frame_cursor = 0

@client.set_process_callback
def process(frames):
    global frame_cursor
    end = frame_cursor + frames
    if end > len(wave):
        out1.get_buffer()[:] = 0
        out2.get_buffer()[:] = 0
        return

    chunk = wave[frame_cursor:end]
    out1.get_buffer()[:] = chunk
    out2.get_buffer()[:] = chunk
    frame_cursor = end

@client.set_shutdown_callback
def shutdown(status, reason):
    print("JACK shutdown:", reason)

client.activate()

# List all playback ports for inspection
print("\nAvailable playback ports:")
for port in client.get_ports(is_audio=True, is_physical=True, is_output=False):
    print(" -", port.name)

# Replace these with correct port names for your system
client.connect(out1, "system:playback_1")  # First card's left channel
client.connect(out2, "system:playback_2")  # Second card's left channel

print("\nPlaying sound for 5 seconds...")
import time

time.sleep(5)

client.deactivate()
client.close()

