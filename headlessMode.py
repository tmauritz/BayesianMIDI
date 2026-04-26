import sys
import threading
import mido
import time
import queue
import random

from MidiScheduler import MidiScheduler
from bayesian.dynamic.dynamic_bayesian_network import DynamicBayesianNetwork, Density, Velocity


class HeadlessBayesianPerformer:
    def __init__(self, input_name, output_name):
        print(f"\n--- Initializing DBN Performer ---")

        # 1. Communication & State
        self.work_queue = queue.Queue()
        self.processing_active = True
        self.clock_tick_count = 0
        self.step_count = 0
        self.clock_running = False

        # 2. Engines
        self.dbn = DynamicBayesianNetwork()
        self.scheduler = MidiScheduler()

        # 3. Input Buffers
        self.hit_velocities = []
        self.override_detected = False

        # 4. Open Ports
        try:
            self.out_port = mido.open_output(output_name)
            self.in_port = mido.open_input(input_name, callback=self.on_midi_message)
            self.scheduler.set_port(self.out_port)

            # Unblock Clock
            backend = getattr(self.in_port, '_rt', getattr(self.in_port, 'callback_port', None))
            if backend:
                backend.ignore_types(timing=False, sysex=True, active_sense=True)
                print(f">>> MIDI Clock Unblocked on {input_name}")
        except Exception as e:
            print(f"CRITICAL ERROR: {e}")
            sys.exit(1)

        # 5. Start Worker Thread
        self.thread = threading.Thread(target=self.run_loop, daemon=True)
        self.thread.start()
        print(">>> Worker Thread Started")

    def on_midi_message(self, msg):
        """Real-time callback: Triggers tasks for the worker thread."""
        if msg.type == 'clock':
            if self.clock_running:
                self.clock_tick_count += 1

                # A. Trigger Resolution every 6 ticks (16th Note)
                if self.clock_tick_count % 6 == 0:
                    self.work_queue.put("RESOLVE_16TH")

                # B. Trigger Inference every 24 ticks (Quarter Note)
                if self.clock_tick_count >= 24:
                    self.clock_tick_count = 0
                    self.work_queue.put("INFER_BEAT")

        elif msg.type == 'start':
            self.clock_running = True
            self.clock_tick_count = 0
            print(">> MIDI START")

        elif msg.type == 'stop':
            self.clock_running = False
            print(">> MIDI STOP")

        elif msg.type == 'note_on' and msg.velocity > 0:
            self.hit_velocities.append(msg.velocity)
            if msg.note == 72:
                self.override_detected = True

    def _calculate_input_states(self):
        """Maps aggregated raw MIDI hits to DBN Enums."""
        count = len(self.hit_velocities)
        avg_vel = sum(self.hit_velocities) / count if count > 0 else 0

        d = Density.LOW if count <= 1 else (Density.MEDIUM if count <= 10 else Density.HIGH)
        v = Velocity.LOW if avg_vel < 45 else (Velocity.MEDIUM if avg_vel < 90 else Velocity.HIGH)
        return d, v

    def process_inference(self):
        """The 'Brain' cycle: Happens once per quarter note."""
        d, v = self._calculate_input_states()
        inf_ms = self.dbn.tick(d, v, override_active=self.override_detected, silent=True)

        # Reset buffers for the next beat
        self.hit_velocities = []
        self.override_detected = False
        self.step_count += 1
        # print(f"Beat {self.step_count} | Brain: {inf_ms:.1f}ms")

    def process_resolution(self):
        """The 'Hands' cycle: Happens once per sixteenth note."""
        midi_msgs, res_ms = self.dbn.resolve_outputs(silent=True)

        for msg in midi_msgs:
            # Send to Scheduler for immediate Note On + Managed Note Off
            self.scheduler.play_note(
                note=msg['note'],
                velocity=msg['velocity'],
                channel=msg['channel'],
                duration=0.1  # 150ms sustain for testing
            )

    def run_loop(self):
        """Main thread loop for non-blocking processing."""
        try:
            while self.processing_active:
                try:
                    task = self.work_queue.get(timeout=0.1)
                    if task == "INFER_BEAT":
                        self.process_inference()
                    elif task == "RESOLVE_16TH":
                        self.process_resolution()
                except queue.Empty:
                    continue
        except KeyboardInterrupt:
            self.processing_active = False
            print("\nShutting down Performer...")

def select_port(port_list, port_type):
    """Helper to pick MIDI ports via terminal input."""
    if not port_list:
        print(f"Error: No MIDI {port_type} ports found.")
        sys.exit(1)

    print(f"\nAvailable MIDI {port_type.upper()} Ports:")
    for i, name in enumerate(port_list):
        print(f" [{i}] {name}")

    while True:
        try:
            choice = input(f"Select {port_type} index (0-{len(port_list) - 1}): ")
            idx = int(choice)
            if 0 <= idx < len(port_list):
                return port_list[idx]
        except (ValueError, IndexError):
            pass
        print("Invalid selection. Please enter a valid number.")


if __name__ == "__main__":
    # Force JACK backend if available
    try:
        mido.set_backend('mido.backends.rtmidi')
        print("Using rtmidi backend.")
    except Exception:
        print("Using default MIDI backend (ALSA).")

    # 1. Port Selection
    in_name = select_port(mido.get_input_names(), "input")
    out_name = select_port(mido.get_output_names(), "output")

    # 2. Start Performer
    performer = HeadlessBayesianPerformer(in_name, out_name)

    print("\n--- SYSTEM ONLINE ---")
    print("Waiting for MIDI Start + Clock pulses...")

    try:
        while True:
            time.sleep(1)  # Keep main thread alive
    except KeyboardInterrupt:
        print("\nShutting down Performer...")
        performer.processing_active = False