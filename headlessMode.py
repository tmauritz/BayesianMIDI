import mido
import queue
import threading
import time
import sys

# Your existing logic imports
from MidiScheduler import MidiScheduler
from bayesian.bayesian_network_helpers import DrumType, BayesianInput
from performance_settings import PerformanceSettings
import bayesian.bayesian_network_ag_baked


class HeadlessBayesianPerformer:
    def __init__(self, input_name, output_name):
        print(f"\n--- Initializing Performer ---")
        print(f"Input:  {input_name}")
        print(f"Output: {output_name}\n")

        # 1. State & Sync
        self.work_queue = queue.Queue()
        self.clock_tick_count = 0
        self.step_count = 0
        self.clock_running = False
        self.processing_active = True

        # 2. Engines
        self.bayesian_engine = bayesian.bayesian_network_ag_baked.BakedBayesianGenerator()
        self.scheduler = MidiScheduler()
        self.settings = PerformanceSettings()  # Using your existing settings class

        # 3. Buffers
        self.midi_buffer = []

        # 4. Open Ports
        try:
            self.out_port = mido.open_output(output_name)
            self.scheduler.set_port(self.out_port)

            self.in_port = mido.open_input(input_name, callback=self.on_midi_message)

            # Disable RtMidi Filters
            backend = getattr(self.in_port, '_rt', getattr(self.in_port, 'callback_port', None))
            if backend:
                backend.ignore_types(timing=False, sysex=False, active_sense=True)
                print(">>> MIDI Clock Unblocked successfully.")
        except Exception as e:
            print(f"FAILED TO OPEN PORTS: {e}")
            sys.exit(1)

        # 5. Start Brain Thread
        self.brain_thread = threading.Thread(target=self.brain_worker, daemon=True)
        self.brain_thread.start()

    def on_midi_message(self, msg):
        """Ear Thread: High Priority, Minimal Logic."""
        if msg.type in ['start', 'continue']:
            self.clock_running = True
            self.clock_tick_count = 0
            self.step_count = 0
            self.midi_buffer.clear()
            print("\n[TRANSPORT START]")
            return

        if msg.type == 'stop':
            self.clock_running = False
            print("\n[TRANSPORT STOP]")
            return

        if msg.type == 'clock' and self.clock_running:
            self.clock_tick_count += 1
            if self.clock_tick_count >= 6:
                self.clock_tick_count = 0

                # Math
                bar = self.step_count // 16
                beat = ((self.step_count // 4) % 4) + 1
                sub = self.step_count % 4

                # Snapshot the buffer and send to Brain
                snapshot = self.midi_buffer[:5]
                self.midi_buffer.clear()
                self.work_queue.put(('step', snapshot, bar, beat, sub))

                self.step_count += 1

        elif msg.type == 'note_on' and msg.velocity > 0:
            if self.clock_running:
                # Use your existing settings to identify the drum
                d_type = self.settings.identify(msg.note)
                self.midi_buffer.append((d_type, msg.velocity))

    def brain_worker(self):
        """Brain Thread: Heavy Thinking."""
        while self.processing_active:
            try:
                task = self.work_queue.get(timeout=0.5)
                if task[0] == 'step':
                    _, events, bar, beat, sub = task
                    self.process_step(events, bar, beat, sub)
            except queue.Empty:
                continue

    def process_step(self, events, bar, beat, sub):
        # 1. Determine Input
        dominant_drum = DrumType.NONE
        max_vel = 0
        for d, v in events:
            if v > max_vel:
                max_vel, dominant_drum = v, d

        current_step = ((beat - 1) * 4) + sub + 1
        evidence = BayesianInput(
            drum_type=dominant_drum,
            velocity=max_vel,
            bar=bar,
            step=current_step
        )

        # 2. Inference
        result = self.bayesian_engine.infer(evidence)

        # 3. Act & Print
        if result.should_play:
            # We use a single f-string for printing to keep console output fast
            print(
                f"Step {current_step:02} | {beat}.{sub} | Input: {dominant_drum.name:6} | ACTION: PLAY {result.midi_note} CHANNEL {result.channel}")
            self.scheduler.play_note(result.midi_note, result.velocity, result.channel, result.duration)


def select_port(port_list, port_type):
    if not port_list:
        print(f"No {port_type} ports found!")
        sys.exit(1)

    print(f"\nAvailable MIDI {port_type.upper()} Ports:")
    for i, name in enumerate(port_list):
        print(f" [{i}] {name}")

    while True:
        try:
            idx = int(input(f"Select {port_type} index: "))
            if 0 <= idx < len(port_list):
                return port_list[idx]
        except ValueError:
            pass
        print("Invalid index, try again.")


if __name__ == "__main__":
    try:
        mido.set_backend('mido.backends.rtmidi')
        print("Using rtmidi backend.")
    except Exception as e:
        print(f"Could not load JACK backend: {e}")
        # Falls back to default (usually ALSA) if JACK isn't running or supported

    # 1. Select Ports
    in_name = select_port(mido.get_input_names(), "input")
    out_name = select_port(mido.get_output_names(), "output")

    # 2. Run Performer
    performer = HeadlessBayesianPerformer(in_name, out_name)

    print("\nSystem Online. Waiting for MIDI Start/Clock from hardware...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        performer.processing_active = False