import mido
import time
from datetime import datetime

from aiohttp_jinja2 import render_string
from mido import Message
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static, RichLog, Select, Label, Button
from textual import work

from bayesian_network import BayesianInput, BayesianOutput, BayesianMusicGenerator, DrumType
from performance_settings import PerformanceSettings
from SettingsModal import SettingsScreen
from tempo_engine import TempoEngine
from ui_widgets import MetronomeDisplay


class BayesianMidiPerformer(App):

    CSS_PATH = ["styles/app.tcss", "styles/widgets.tcss"]
    BINDINGS = [("space", "toggle_play", "Start/Stop")]

    def __init__(self):
        super().__init__()
        self.current_input_port = None
        self.current_output_port = None
        self.processing_active = True
        self.clock_running = False
        self.tempo_engine = TempoEngine(bpm=120)
        self.bayesian_engine = BayesianMusicGenerator()
        self.settings = PerformanceSettings()
        self.midi_buffer = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="main_area"):
            # LEFT: Sidebar
            with Vertical(id="sidebar"):
                yield Label("MIDI Input:")
                yield Select(options=self.get_midi_input_ports(), id="input_port_selector")
                yield Label("MIDI Output:")
                yield Select(options=self.get_midi_output_ports(), id="output_port_selector")

                yield Label("\nTempo (BPM):")
                yield Select(
                    options=[("80", 80), ("100", 100), ("120", 120), ("140", 140)],
                    value=120,
                    id="bpm_selector",
                    allow_blank=False
                )

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
                yield RichLog(id="output_log", highlight=True, markup=True)

        yield Footer()

    def action_toggle_play(self) -> None:
        """Toggles Play Button. ALso Called when the user presses space."""
        self.clock_running = not self.clock_running
        btn = self.query_one("#toggle_clock", Button)

        if self.clock_running:
            btn.label, btn.variant = "STOP", "error"
            self.tempo_engine.reset()
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

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.control.id == "input_port_selector":
            self.start_midi_listener(str(event.value))
        elif event.control.id == "output_port_selector":
            if self.current_output_port:
                self.current_output_port.close()
            try:
                self.current_output_port = mido.open_output(str(event.value))
            except Exception as e:
                self.call_from_thread(self.query_one("#input_log", RichLog).write, f"[red]Error: {e}[/]")

        elif event.control.id == "bpm_selector":
            self.tempo_engine.set_bpm(int(event.value))
            self.query_one("#input_log", RichLog).write(f"[b]Tempo set to {event.value}[/]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "toggle_clock":
            self.action_toggle_play()
        if event.button.id == "open_settings_btn":
            # Push the screen onto the stack
            self.push_screen(SettingsScreen())

    def on_mount(self):
        self.run_clock()

    @work(thread=True, exclusive=True)
    def run_clock(self):
        while self.processing_active:
            if self.clock_running and self.tempo_engine.check_tick():
                steps = self.tempo_engine.step_count
                beat = ((steps // 4) % 4) + 1
                sub = steps % 4
                self.call_from_thread(self.query_one("#metronome_box", MetronomeDisplay).update_beat, beat, sub)
                # Network Logic
                # Grab all notes that happened since the last tick
                recent_events = self.midi_buffer[:]
                self.midi_buffer.clear()  # Reset for next tick

                self.process_bayesian_step(recent_events, beat, sub)

            time.sleep(0.002 if self.clock_running else 0.1)

    @work(thread=True, exclusive=True)
    def start_midi_listener(self, port_name):
        self.call_from_thread(self.query_one("#status_label", Static).update, f"[green]Listening:\n{port_name}[/]")

        if self.current_input_port:
            self.current_input_port.close()

        try:
            with mido.open_input(port_name) as port:
                self.current_input_port = port

                # non-blocking loop
                while self.processing_active:
                    for msg in port.iter_pending():
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        log_target = self.query_one("#input_log", RichLog)
                        note_type = self.app.settings.identify(msg.note)

                        if msg.type == 'note_on':
                            # self.call_from_thread(log_target.write, f"[green]{timestamp} NOTE {msg.note} ({str(note_type)})[/]")
                            self.call_from_thread(self.action_dispatch_midi, msg.note)
                            if self.clock_running:
                                self.call_from_thread(self.app.midi_buffer.append, (note_type, msg.velocity))
                        # else:
                            # self.call_from_thread(log_target.write, f"[dim]{timestamp} {msg}[/]")
                    time.sleep(0.01) # sleep briefly to prevent high CPU usage

        except Exception as e:
            self.call_from_thread(self.query_one("#input_log", RichLog).write, f"[red]Error: {e}[/]")

    def on_unmount(self):
        self.processing_active = False
        if self.current_input_port: self.current_input_port.close()
        if self.current_output_port: self.current_output_port.close()

    @work(thread=True)
    def process_bayesian_step(self, recent_events, beat, sub):
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
            bar=self.tempo_engine.bar_count,
            step=current_step
        )

        # 4. INFER & ACT
        result = self.bayesian_engine.infer(evidence)
        self.call_from_thread(self.log_generation, result)
        if result.should_play is not True:
            return

        if self.current_output_port:
            msg_on = mido.Message('note_on', channel = result.channel, note=result.midi_note,  velocity=result.velocity)
            msg_off = mido.Message('note_off', channel = result.channel, note=result.midi_note, velocity=result.velocity)
            self.play_note(msg_on, msg_off, result.duration)
        else:
            self.call_from_thread(self.log_error, "No Output selected!")

    @work(thread=True)
    def play_note(self, msg_note_on: mido.Message, msg_note_off: mido.Message, output_duration):
        """
        Sends a note on and off. delays the note off for time in seconds.
        """
        if not self.current_output_port:
            return
        self.current_output_port.send(msg_note_on)
        time.sleep(output_duration)
        self.current_output_port.send(msg_note_off)

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
                f"[{timestamp}] [bold green]PLAY[/] "
                f"Note: {result.midi_note} (Vel: {result.velocity}) | "
                f"[dim]{result.debug_info}[/]"
            )
        else:
            # Optional: Log 'Rest' decisions if you want to see the engine thinking
            # message = f"[{timestamp}] [dim]... Rest ({result.debug_info})[/]"
            return

        log_widget.write(message)

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