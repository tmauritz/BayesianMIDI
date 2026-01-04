import mido
import time
from datetime import datetime
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static, RichLog, Select, Label, Button
from textual import work

from performance_settings import PerformanceSettings
from SettingsModal import SettingsScreen
# --- LOCAL IMPORTS ---
from tempo_engine import TempoEngine
from ui_widgets import MetronomeDisplay


class BayesianMidiPerformer(App):

    CSS_PATH = ["styles/app.tcss", "styles/widgets.tcss"]

    BINDINGS = [("space", "toggle_play", "Start/Stop")]

    def __init__(self):
        super().__init__()
        self.current_port = None
        self.processing_active = True
        self.clock_running = False
        self.tempo_engine = TempoEngine(bpm=120)
        self.settings = PerformanceSettings()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="main_area"):
            # LEFT: Sidebar
            with Vertical(id="sidebar"):
                yield Label("MIDI Input:")
                yield Select(options=self.get_midi_ports(), id="port_selector")

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

    def get_midi_ports(self):
        try:
            inputs = mido.get_input_names()
            return [(name, name) for name in inputs] if inputs else [("No Ports", "none")]
        except:
            return [("Error", "error")]

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.control.id == "port_selector":
            self.start_midi_listener(str(event.value))
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
                total_steps = self.tempo_engine.step_counter
                beat = ((total_steps // 4) % 4) + 1
                sub = total_steps % 4

                self.call_from_thread(self.query_one("#metronome_box", MetronomeDisplay).update_beat, beat, sub)

                # Simulation Logic
                if sub == 0 and beat == 1:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    self.call_from_thread(
                        self.query_one("#output_log", RichLog).write,
                        f"[cyan]{timestamp} Generated: Bass Note (C2)[/]"
                    )

            time.sleep(0.002 if self.clock_running else 0.1)

    @work(thread=True, exclusive=True)
    def start_midi_listener(self, port_name):
        self.call_from_thread(self.query_one("#status_label", Static).update, f"[green]Listening:\n{port_name}[/]")

        if self.current_port:
            self.current_port.close()

        try:
            with mido.open_input(port_name) as port:
                self.current_port = port

                # non-blocking loop
                while self.processing_active:
                    for msg in port.iter_pending():
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        log_target = self.query_one("#input_log", RichLog)

                        note_type = self.app.settings.identify(msg.note)

                        if msg.type == 'note_on':
                            self.call_from_thread(log_target.write, f"[green]{timestamp} NOTE {msg.note} ({note_type})[/]")
                            self.call_from_thread(self.action_dispatch_midi, msg.note)
                        else:
                            self.call_from_thread(log_target.write, f"[dim]{timestamp} {msg}[/]")
                    time.sleep(0.01) # sleep briefly to prevent high CPU usage

        except Exception as e:
            self.call_from_thread(self.query_one("#input_log", RichLog).write, f"[red]Error: {e}[/]")

    def on_unmount(self):
        self.processing_active = False
        if self.current_port: self.current_port.close()


if __name__ == "__main__":
    app = BayesianMidiPerformer()
    app.run()