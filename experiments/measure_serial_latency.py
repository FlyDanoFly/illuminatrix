"""Measure controller serial round-trip latency, per exchange.

Hammers request->response as fast as possible and reports the latency
distribution. The tail (p99/max), not the average, is what sizes a read
timeout or a frames-without-response miss threshold.

Run from the project root with the installation service STOPPED (two
processes cannot share the port; exclusive=True makes that fail loudly):

    sudo systemctl stop <illuminatrix service>
    poetry run python experiments/measure_serial_latency.py

--cycle sends a moving color pattern instead of all-zeros so the
measurement includes realistic SoftPWM ISR + LED load. The tower/control
LEDs will animate while it runs.
"""

import argparse
import statistics
import sys
import time

import serial

sys.path.insert(0, ".")
from systems.concrete.SwitchInputSystem import (  # noqa: E402
    SERIAL_FRAME_START_BYTE,
    build_frame,
    compute_crc8,
)


def make_payload(i: int, cycle: bool) -> tuple[list[int], list[int]]:
    if not cycle:
        return [0, 0, 0] * 7, [0, 0, 0]
    # Crude moving rainbow: enough to keep the SoftPWM channels busy
    rgb = [(i * 7 + ch * 11) % 256 for ch in range(21)]
    return rgb, [(i * 3) % 256] * 3


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="/dev/ttyACM0")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--count", type=int, default=5000, help="number of exchanges to measure")
    parser.add_argument("--cycle", action="store_true", help="send changing colors (realistic LED/ISR load)")
    parser.add_argument("--timeout", type=float, default=1.0, help="per-read timeout; counts as a miss, not a sample")
    parser.add_argument("--legacy", action="store_true", help="old firmware: 2 raw response bytes, no framing/CRC")
    options = parser.parse_args()
    response_size = 2 if options.legacy else 4

    port = serial.Serial(options.port, options.baud, timeout=options.timeout, exclusive=True)
    port.reset_input_buffer()

    # Warmup: let the USB link and firmware settle, discard these
    for i in range(20):
        port.write(build_frame(*make_payload(i, options.cycle)))
        port.read(response_size)

    samples_ms: list[float] = []
    misses = 0
    bad_frames = 0
    t_start = time.monotonic()
    for i in range(options.count):
        frame = build_frame(*make_payload(i, options.cycle))
        t0 = time.perf_counter()
        port.write(frame)
        response = port.read(response_size)
        t1 = time.perf_counter()
        if len(response) != response_size:
            misses += 1
            port.reset_input_buffer()
        elif not options.legacy and (
            response[0] != SERIAL_FRAME_START_BYTE
            or compute_crc8(response[1:3]) != response[3]
        ):
            bad_frames += 1
            port.reset_input_buffer()
        else:
            samples_ms.append((t1 - t0) * 1000.0)
    elapsed = time.monotonic() - t_start
    port.close()

    if not samples_ms:
        print(f"No valid responses in {options.count} exchanges — is the controller connected and flashed?")
        return

    samples_ms.sort()

    def pct(p: float) -> float:
        return samples_ms[min(len(samples_ms) - 1, int(len(samples_ms) * p))]

    print(f"exchanges: {len(samples_ms)} ok, {misses} missed (timeout {options.timeout}s), "
          f"{bad_frames} bad frames, {len(samples_ms) / elapsed:.0f} round trips/sec")
    print(f"min    {samples_ms[0]:7.2f} ms")
    print(f"median {statistics.median(samples_ms):7.2f} ms")
    print(f"mean   {statistics.fmean(samples_ms):7.2f} ms")
    print(f"p95    {pct(0.95):7.2f} ms")
    print(f"p99    {pct(0.99):7.2f} ms")
    print(f"max    {samples_ms[-1]:7.2f} ms")

    # Text histogram, 1ms buckets up to 20ms then an overflow bucket
    print("\nlatency histogram (1ms buckets):")
    buckets = [0] * 21
    for s in samples_ms:
        buckets[min(20, int(s))] += 1
    peak = max(buckets)
    for i, n in enumerate(buckets):
        if n == 0:
            continue
        label = f"{i:2d}-{i + 1:2d}ms" if i < 20 else "  >20ms"
        print(f"{label} {'#' * max(1, n * 50 // peak)} {n}")


if __name__ == "__main__":
    main()
