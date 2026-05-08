import mido
import time
import random

# CONFIGURATION
# Match this to your Virtual Loopback Output name
OUT_PORT_NAME = 'Midi Through:Midi Through Port-0 14:0'
BPM = 120
TICKS_PER_BEAT = 24
SECONDS_PER_TICK = 60.0 / (BPM * TICKS_PER_BEAT)


def simulate_drummer():
    try:
        out = mido.open_output(OUT_PORT_NAME)
        print(f"--- Virtual Drummer Online: Sending to {OUT_PORT_NAME} ---")

        # 1. Send START signal
        out.send(mido.Message('start'))

        beat_count = 0
        while True:
            # --- Simulate CLOCK LOOP ---
            for tick in range(TICKS_PER_BEAT):
                out.send(mido.Message('clock'))

                # --- SIMULATE DRUM HITS ---
                # Test different densities based on the beat count
                if tick == 0:  # Every beat start
                    # High Velocity Climax (Beats 0-7)
                    if beat_count < 8:
                        out.send(mido.Message('note_on', note=36, velocity=110))
                        out.send(mido.Message('note_on', note=38, velocity=100))

                    # Sparse Ghosting (Beats 8-15)
                    elif beat_count < 16:
                        if beat_count % 2 == 0:  # Every other beat
                            out.send(mido.Message('note_on', note=36, velocity=40))

                    # Absolute Silence (Beat 16+)
                    # No notes sent, testing DBN decay

                time.sleep(SECONDS_PER_TICK)

            beat_count += 1
            if beat_count % 4 == 0:
                print(f"Simulated Beat: {beat_count}")

    except KeyboardInterrupt:
        out.send(mido.Message('stop'))
        print("\nSimulation Stopped.")


if __name__ == "__main__":
    simulate_drummer()