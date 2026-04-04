import queue
from math import floor

import mido
import time
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static, RichLog, Select, Label, Button
from textual import work

import bayesian.bayesian_network_ag_baked
from MidiScheduler import MidiScheduler
from bayesian.bayesian_network_helpers import DrumType, BayesianInput, BayesianOutput
from performance_settings import PerformanceSettings
from SettingsModal import SettingsScreen
from ui_widgets import MetronomeDisplay


class BayesianMidiPerformer(App):

    CSS_PATH = ["styles/app.tcss", "styles/widgets.tcss", "styles/settings.tcss"]
    BINDINGS = [("space", "toggle_play", "Start/Stop")]


    def __init__(self):
        super().__init__()
        self.work_queue = queue.Queue()

        self.clock_tick_count = 0
        self.step_count = 0
        mido.set_backend('mido.backends.rtmidi')
        self.current_input_port = None
        self.current_output_port = None
        self.processing_active = True
        self.clock_running = False
        self.bayesian_engine = bayesian.bayesian_network_ag_baked.BakedBayesianGenerator()
        self.settings = PerformanceSettings()
        self.midi_buffer = []
        self.midi_scheduler = MidiScheduler()
        self.last_beat_state = None
        self.output_log_buffer = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="main_area"):
            # LEFT: Sidebar
            with Vertical(id="sidebar"):

                yield Button("Settings", id="open_settings_btn", variant="primary")
                yield Button("START", id="toggle_clock", variant="success")
                yield Static("\nStatus:\n[red]OFF[/]", id="status_label")

            # MIDDLE: Metronome (Imported Widget)
            yield MetronomeDisplay(id="metronome_box")

            # RIGHT: Logs
            with Vertical(id="right_column"):
                yield Label("Input History")
                yield RichLog(id="input_log", highlight=True, markup=True)

                yield Label("Generated Output")
                yield RichLog(id="output_log", highlight=False, markup=False)

        yield Footer()

    def action_toggle_play(self) -> None:
        """Toggles Play Button. ALso Called when the user presses space."""
        self.clock_running = not self.clock_running
        btn = self.query_one("#toggle_clock", Button)

        if self.clock_running:
            btn.label, btn.variant = "STOP", "error"
            self.query_one("#output_log", RichLog).write("[bold green]▶ Performance Started[/]")
        else:
            btn.label, btn.variant = "START", "success"
            self.query_one("#output_log", RichLog).write("[bold red]⏹ Performance Stopped[/]")

    def action_dispatch_midi(self, note: int) -> None:
        """
        Passes the MIDI note to the active screen if it has a handler.
        This must run on the main thread.
        """
        # check if the current screen has a 'handle_midi_input' method
        if hasattr(self.screen, "handle_midi_input"):
            self.screen.handle_midi_input(note)

    def get_midi_input_ports(self):
        try:
            inputs = mido.get_input_names()
            return [(name, name) for name in inputs] if inputs else [("No Ports", "none")]
        except:
            return [("Error", "error")]

    def get_midi_output_ports(self):
        try:
            outputs = mido.get_output_names()
            return [(name, name) for name in outputs] if outputs else [("No Ports", "none")]
        except:
            return [("Error", "error")]

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "toggle_clock":
            self.action_toggle_play()
        if event.button.id == "open_settings_btn":
            # Push the screen onto the stack
            self.push_screen(SettingsScreen())

    @work(exclusive=True, thread=True)
    def brain_worker(self) -> None:
        """The dedicated thread for Bayesian Inference."""
        while self.processing_active:
            try:
                # Wait for data from the MIDI thread (blocks for 100ms max)
                task_data = self.work_queue.get(timeout=0.1)

                if task_data[0] == 'process_step':
                    _, events, bar, beat, sub = task_data
                    self.process_bayesian_step(events, bar, beat, sub)

            except queue.Empty:

                continue

    def on_mount(self) -> None:
        """Called when the app is first mounted."""
        # This tells Textual: "Run self.flush_logs every 0.1 seconds"
        self.set_interval(0.1, self.flush_logs)
        self.brain_worker()
        # Optional: Start with a clean log
        self.query_one("#input_log", RichLog).write("[bold cyan]System Ready. Waiting for MIDI...[/]")

    def set_midi_output_port(self, port_name):
        """Helper called by SettingsScreen to change output safely."""
        if self.current_output_port:
            self.current_output_port.close()
        try:
            self.current_output_port = mido.open_output(port_name)
            self.midi_scheduler.set_port(self.current_output_port)
            self.query_one("#output_log", RichLog).write(f"[green]Output connected: {port_name}[/]")
        except Exception as e:
            self.query_one("#output_log", RichLog).write(f"[red]Error connecting output: {e}[/]")

    def start_midi_listener(self, port_name):
        self.query_one("#status_label", Static).update(
            f"[green]Listening:\n{port_name} (Current Backend: {mido.backend.name})[/]"
        )

        if self.current_input_port:
            self.current_input_port.close()

        try:
            # 1. Open with callback
            self.current_input_port = mido.open_input(port_name, callback=self.on_midi_message)

            # 2. UNBLOCK CLOCK: Reach into the backend to disable filters
            # We look for '_rt' (standard) or 'callback_port' (some mido versions)
            backend = getattr(self.current_input_port, '_rt',
                              getattr(self.current_input_port, 'callback_port', None))

            if backend:
                # timing=False -> DO NOT ignore clock/start/stop
                # active_sense=True -> DO ignore the clutter heartbeat
                backend.ignore_types(timing=False, sysex=False, active_sense=True)
                self.query_one("#input_log", RichLog).write("[cyan]MIDI Clock Unblocked[/]")

        except Exception as e:
            self.query_one("#input_log", RichLog).write(f"[red]Error: {e}[/]")

    def on_midi_message(self, msg):
        """
        Runs on high-priority thread.
        """
        # --- 1. Transport ---
        if msg.type == 'start' or msg.type == 'continue':
            self.clock_running = True
            self.clock_tick_count = 0
            self.step_count = 0
            self.midi_buffer.clear()
            return

        elif msg.type == 'stop':
            self.clock_running = False
            return

        # --- 2. Clock Pulses ---
        elif msg.type == 'clock':
            if self.clock_running:
                self.clock_tick_count += 1

                if self.clock_tick_count >= 6:
                    self.clock_tick_count = 0

                    # Bundle the data and put it in the queue for the Brain
                    beat = ((self.step_count // 4) % 4) + 1
                    sub = self.step_count % 4
                    bar = self.step_count // 16

                    # Snapshot the buffer and send to worker
                    self.work_queue.put(('process_step', self.midi_buffer[:], bar, beat, sub))
                    self.midi_buffer.clear()
                    self.step_count += 1
            return

        # --- 3. Note Input ---
        elif msg.type == 'note_on' and msg.velocity > 0:
            # UI Update (Only for notes!)
            self.call_from_thread(self.action_dispatch_midi, msg.note)

            if self.clock_running:
                note_type = self.settings.identify(msg.note)
                self.midi_buffer.append((note_type, msg.velocity))

    def on_unmount(self):
        self.processing_active = False
        if self.current_input_port: self.current_input_port.close()
        if self.current_output_port: self.current_output_port.close()

    def process_bayesian_step(self, recent_events, bar, beat, sub):
        """
        Called by the metronome every 16th note.
        2. Updates Bayesian State (Density/Energy).
        3. Infers output.
        """
        # 2. DETERMINE DOMINANT INPUT
        # If the drummer played a Kick AND a Snare, which one wins?
        # Logic: Kicks take priority for downbeats, otherwise take the loudest.
        dominant_drum = DrumType.NONE
        max_velocity = 0

        if recent_events:
            # Simple logic: take the loudest hit
            for d_type, vel in recent_events:
                if vel > max_velocity:
                    max_velocity = vel
                    dominant_drum = d_type

        # 3. BUILD EVIDENCE (Using your Chapter 5 Structure)
        # Calculate Step (1-16) based on Beat (1-4) and Sub (0-3)
        current_step = ((beat - 1) * 4) + sub + 1

        evidence = BayesianInput(
            drum_type=dominant_drum,
            velocity=max_velocity,
            bar=bar,
            step=current_step
        )

        # 4. INFER & ACT
        result = self.bayesian_engine.infer(evidence)
        if result.should_play is not True:
            return
        # self.call_from_thread(self.log_generation, result)

        if self.current_output_port:
            self.midi_scheduler.play_note(
                note=result.midi_note,
                velocity=result.velocity,
                channel=result.channel,
                duration=result.duration
            )
        else:
            self.call_from_thread(self.log_error, "No Output selected!")

    def log_generation(self, result: BayesianOutput) -> None:
        """
        Updates the Output Log with the decision made by the Bayesian Engine.
        Must be called via self.call_from_thread if used in a worker.
        """
        log_widget = self.query_one("#output_log", RichLog)

        # Get current timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")

        if result.should_play:
            # Format: [12:00:01] Kick -> I (Root) -> Note 60
            message = (
                f"[{timestamp}] PLAY "
                f"Note: {result.midi_note} (Vel: {result.velocity}) | "
                f"{result.debug_info}"
            )
        else:
            # Optional: Log 'Rest' decisions if you want to see the engine thinking
            # message = f"[{timestamp}] [dim]... Rest ({result.debug_info})[/]"
            return

        self.output_log_buffer.append(message)

    def flush_logs(self):
        # This runs on the Main Thread automatically via set_interval
        if self.output_log_buffer:
            log_widget = self.query_one("#output_log", RichLog)

            # Join all pending messages into one write operation
            # This triggers only ONE layout calculation instead of N
            batch_message = "\n".join(self.output_log_buffer)
            log_widget.write(batch_message)

            # Clear the queue
            self.output_log_buffer.clear()

    def log_error(self, error_message: str) -> None:
        """
        Updates the Output Log with an error message.
        Must be called via self.call_from_thread if used in a worker.
        """
        log_widget = self.query_one("#output_log", RichLog)

        # Get current timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Format: [12:00:01] ERROR my error message
        # We use [bold red] to make the error stand out
        formatted_message = (
            f"[{timestamp}] [bold red]ERROR[/] "
            f"{error_message}"
        )

        log_widget.write(formatted_message)

if __name__ == "__main__":
    app = BayesianMidiPerformer()
    app.run()