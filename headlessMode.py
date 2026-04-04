import mido
import queue
import threading
import time
import sys

# Your project-specific imports
from MidiScheduler import MidiScheduler
from bayesian.bayesian_network_helpers import DrumType, BayesianInput
from performance_settings import PerformanceSettings
import bayesian.bayesian_network_ag_baked

GRACE_PERIOD_MS = 15

class HeadlessBayesianPerformer:
    def __init__(self, input_name, output_name):
        print(f"\n--- Initializing Headless Performer (Grace: {GRACE_PERIOD_MS}ms) ---")

        # 1. Thread-Safe Communication
        self.work_queue = queue.Queue()
        self.processing_active = True

        # 2. Timing State
        self.clock_tick_count = 0
        self.step_count = 0
        self.clock_running = False

        # 3. Engines & Settings
        self.bayesian_engine = bayesian.bayesian_network_ag_baked.BakedBayesianGenerator()
        self.scheduler = MidiScheduler()
        self.settings = PerformanceSettings()

        # 4. Buffers
        self.midi_buffer = []

        # 5. Open Ports
        try:
            self.out_port = mido.open_output(output_name)
            self.scheduler.set_port(self.out_port)

            self.in_port = mido.open_input(input_name, callback=self.on_midi_message)

            # Access the underlying backend to disable clock filtering
            backend = getattr(self.in_port, '_rt', getattr(self.in_port, 'callback_port', None))
            if backend:
                # timing=False means "Don't ignore clock"
                backend.ignore_types(timing=False, sysex=False, active_sense=True)
                print(f">>> MIDI Clock Unblocked on {input_name}")
        except Exception as e:
            print(f"CRITICAL ERROR opening ports: {e}")
            sys.exit(1)

        # 6. Start the "Brain" thread
        self.brain_thread = threading.Thread(target=self.brain_worker, daemon=True)
        self.brain_thread.start()

    def flush_work_queue(self):
        """Clears any pending beats so the engine doesn't play catch-up."""
        count = 0
        while not self.work_queue.empty():
            try:
                self.work_queue.get_nowait()
                count += 1
            except queue.Empty:
                break
        if count > 0:
            print(f">>> Flushed {count} stale steps from queue.")

    def on_midi_message(self, msg):
        """
        The 'Ear' (High-Priority Thread).
        Must remain extremely fast to avoid missing clock pulses.
        """
        # --- Transport Control ---
        if msg.type in ['start', 'continue']:
            self.flush_work_queue()
            self.clock_running = True
            self.clock_tick_count = 0
            self.step_count = 0
            self.midi_buffer.clear()
            print("\n[MIDI START/CONTINUE]")
            return

        if msg.type == 'stop':
            self.clock_running = False
            self.flush_work_queue()
            print("\n[MIDI STOP]")
            return

        # --- Timing Pulses (24 PPQN) ---
        if msg.type == 'clock' and self.clock_running:
            self.clock_tick_count += 1
            if self.clock_tick_count >= 6:
                self.clock_tick_count = 0

                # 1. RECORD EXACT TRIGGER TIME
                trigger_time = time.perf_counter()

                # 2. Package everything for the Brain
                bar = (self.step_count // 16) % 4
                beat = ((self.step_count // 4) % 4) + 1
                sub = self.step_count % 4

                self.work_queue.put(('beat', trigger_time, bar, beat, sub))
                self.step_count += 1

        elif msg.type == 'note_on' and msg.velocity > 0:
            if self.clock_running:
                self.midi_buffer.append((self.settings.identify(msg.note), msg.velocity))

    def brain_worker(self):
        """Brain Thread: Monitors Jitter and Inference."""
        while self.processing_active:
            try:
                task = self.work_queue.get(timeout=0.5)
                if task[0] == 'beat':
                    _, trigger_time, bar, beat, sub = task

                    # 1. Wait for Grace Period
                    if GRACE_PERIOD_MS > 0:
                        time.sleep(GRACE_PERIOD_MS / 1000.0)

                    # 2. Calculate Wake Jitter
                    # (Actual Time - Trigger Time) - Intended Delay
                    # actual_wake_time = time.perf_counter()
                    # total_delay_ms = (actual_wake_time - trigger_time) * 1000
                    # jitter_ms = total_delay_ms - GRACE_PERIOD_MS

                    # 3. Snapshot and Process
                    snapshot = self.midi_buffer[:]
                    self.midi_buffer.clear()

                    self.process_step(snapshot, bar, beat, sub)
                    # end_time = time.perf_counter()
                    # duration_ms = (end_time - trigger_time) * 1000
                    # print(f"Total Time: {duration_ms}ms, Jitter {jitter_ms}ms")
            except queue.Empty:
                continue

    def process_step(self, events, bar, beat, sub):
        """Performs Bayesian inference and schedules MIDI output."""
        start_perf = time.perf_counter()

        # 1. Determine dominant hit for this 16th note
        dominant_drum = DrumType.NONE
        max_vel = 0
        for d, v in events:
            if v > max_vel:
                max_vel, dominant_drum = v, d

        # 2. Build Evidence
        # Step (1-16)
        current_step = ((beat - 1) * 4) + sub + 1
        evidence = BayesianInput(
            drum_type=dominant_drum,
            velocity=max_vel,
            bar=bar,
            step=current_step
        )

        # 3. Bayesian Inference (The 'Heavy' Part)
        result = self.bayesian_engine.infer(evidence)

        # 4. Schedule Output
        if result.should_play:
            self.scheduler.play_note(
                note=result.midi_note,
                velocity=result.velocity,
                channel=result.channel,
                duration=result.duration
            )

        # 5. Performance Profiling
        end_perf = time.perf_counter()
        duration_ms = (end_perf - start_perf) * 1000

        # Output current status to console
        # If duration_ms > 125ms (at 120bpm), you are lagging!
        status_msg = f"Bar {bar:02} | {beat}.{sub} | Input: {dominant_drum.name:6} | Inference: {duration_ms:4.1f}ms"

        if result.should_play:
            print(f"{status_msg} | ACTION: PLAY {result.midi_note}")
        elif duration_ms > 50:
            # Only print 'quiet' steps if they are suspiciously slow
            print(f"{status_msg} | [SLOW STEP]")


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
        performer.scheduler.stop()