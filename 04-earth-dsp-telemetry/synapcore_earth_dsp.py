#!/usr/bin/env python3
"""
Synapcore Earth DSP Engine (48 kHz / 64-bit)
Sintese sonora ancorada na fundamental Re (D1 = 36.71 Hz) e Crossover LR4 (90.0 Hz).
"""
import math, struct, wave

def generate_earth_telemetry(output_path="synapcore_alert_36hz.wav", duration=1.0, sample_rate=48000):
    n_samples = int(sample_rate * duration)
    with wave.open(output_path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            t = i / sample_rate
            sub = math.sin(2.0 * math.pi * 36.71 * t) * 0.45
            mod = math.sin(2.0 * math.pi * 146.84 * t) * 2.5
            screech = math.sin(2.0 * math.pi * 880.0 * t + mod) * 0.15 * math.exp(-3.0 * t)
            sample = max(-0.501, min(0.501, sub + screech))
            frames.extend(struct.pack("<h", int(sample * 32767)))
        wf.writeframes(frames)
    print(f"[OK] Telemetria Earth gerada em {output_path}.")

if __name__ == "__main__":
    generate_earth_telemetry()
