# From ChatGPT

import argparse
import os

import numpy as np
from scipy.io import wavfile


def stereo_to_8ch(input_path: str, output_path: str):
    rate, data = wavfile.read(input_path)

    # Validate input is stereo
    if data.ndim != 2 or data.shape[1] != 2:
        raise ValueError(f"Input file '{input_path}' is not a stereo file (2 channels)")

    # Duplicate the stereo signal 4 times to make 8 channels
    data_8ch = np.tile(data, (1, 4))  # shape: (n_samples, 8)

    # Write the 8-channel file
    wavfile.write(output_path, rate, data_8ch.astype(data.dtype))
    print(f"8-channel file written to: {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Duplicate a stereo WAV file into 8 channels (4x stereo).")
    parser.add_argument("input", help="Path to input stereo WAV file")
    parser.add_argument("output", nargs="?", help="Path to output 8-channel WAV file (optional)")

    args = parser.parse_args()

    input_path = args.input
    output_path = args.output or os.path.splitext(input_path)[0] + "_8ch.wav"

    stereo_to_8ch(input_path, output_path)

if __name__ == "__main__":
    main()

