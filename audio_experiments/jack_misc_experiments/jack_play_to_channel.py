import sys
import jack
import soundfile as sf
import numpy as np
import time

def play_to_jack_channel(filename, target_channel):
    client = jack.Client("audio_sender")
    client.blocksize = 512
    # client.samplerate = 48000

    # Register enough output ports for 8 channels
    num_output_channels = 8
    outports = [client.outports.register(f"out_{i}") for i in range(num_output_channels)]

    # Load audio file
    data, samplerate = sf.read(filename, dtype='float32')
    if len(data.shape) == 1:
        data = data[:, np.newaxis]  # Convert mono to 2D

    total_frames, file_channels = data.shape

    if samplerate != client.samplerate:
        raise ValueError(f"Sample rate mismatch: file {samplerate}, JACK {client.samplerate}")

    playhead = [0]  # mutable so inner function can modify it

    @client.set_process_callback
    def process(frames):
        start = playhead[0]
        end = start + frames

        for i, port in enumerate(outports):
            buf = np.frombuffer(port.get_buffer(), dtype=np.float32)
            if i == target_channel:
                if start >= total_frames:
                    buf[:] = 0.0
                elif end <= total_frames:
                    buf[:] = data[start:end, 0]
                else:
                    available = total_frames - start
                    buf[:available] = data[start:, 0]
                    buf[available:] = 0.0
            else:
                buf[:] = 0.0

        playhead[0] += frames

    # Activate client and connect to physical outputs
    with client:
        system_out = client.get_ports(is_physical=True, is_input=True)
        if len(system_out) <= target_channel:
            raise RuntimeError(f"JACK only has {len(system_out)} physical output channels.")

        client.connect(outports[target_channel], system_out[target_channel].name)

        print(f"Playing {filename} to JACK output channel {target_channel}...")
        while playhead[0] < total_frames:
            time.sleep(0.1)

    print("Done.")

# Example usage:
play_to_jack_channel(sys.argv[1], target_channel=1)

