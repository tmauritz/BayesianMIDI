import mido
import time
from datetime import datetime
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, RichLog, Select, Label, Button
from textual import work
from textual.reactive import reactive


# --- 1. The Clock Logic (From previous discussion) ---
class TempoEngine:
    def __init__(self, bpm=120, steps_per_beat=4):
        self.bpm = bpm
        self.steps_per_beat = steps_per_beat
        self.interval = (60.0 / self.bpm) / self.steps_per_beat
        self.last_tick_time = time.perf_counter()
        self.step_counter = 0

    def set_bpm(self, new_bpm):
        self.bpm = new_bpm
        self.interval = (60.0 / self.bpm) / self.steps_per_beat

    def check_tick(self):
        """Returns True if a 16th note tick just happened."""
        now = time.perf_counter()
        if now - self.last_tick_time >= self.interval:
            self.last_tick_time += self.interval
            self.step_counter += 1
            return True
        return False


# --- 2. The Visual Metronome Widget ---
class MetronomeDisplay(Static):
    """A large display for the current beat."""

    # Reactive variables trigger a redraw when changed
    current_beat = reactive(1)
    current_sub = reactive(0)

    def on_mount(self):
        self.update_display()

    def watch_current_beat(self, old_val, new_val):
        self.update_display()

    def update_display(self):
        # Create a visual grid: [1] . . . [2] . . .
        # Highlight the current beat

        # Simple visual logic:
        # If subdivision is 0 (Downbeat), use Big Number.
        # Else, use small dot.

        color = "grey"
        if self.current_sub == 0:
            color = "green" if self.current_beat == 1 else "yellow"
            display_str = f"[{color} bold]BEAT {self.current_beat}[/]"
            sub_display = "[b]O[/] . . ."
        else:
            display_str = f"[{color}]BEAT {self.current_beat}[/]"
            # Visualizing 16th notes (0, 1, 2, 3)
            dots = ["O", ".", ".", "."]
            dots[self.current_sub] = f"[b {color}]X[/]"  # Highlight current 16th
            sub_display = " ".join(dots)

        self.update(f"\n{display_str}\n\n{sub_display}")


# --- 3. The Main App ---
class BayesianMidiPerformer(App):
    CSS = """
    Screen { layout: vertical; }

    #sidebar {
        width: 30;
        dock: left;
        background: $panel;
        padding: 1;
        border-right: solid $accent;
    }

    #main_area {
        layout: horizontal;
        height: 100%;
    }

    #metronome_box {
        width: 40%;
        height: 100%;
        border: solid green;
        content-align: center middle;
        text-align: center;
        background: $surface;
    }

    #logs {
        width: 60%;
        height: 100%;
        border: solid $accent;
        background: $surface;
    }
    """

    def __init__(self):
        super().__init__()
        self.current_port = None
        self.processing_active = True
        self.tempo_engine = TempoEngine(bpm=120)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="main_area"):
            # LEFT: Sidebar Controls
            with Vertical(id="sidebar"):
                yield Label("MIDI Input:")
                yield Select(options=self.get_midi_ports(), id="port_selector")

                yield Label("\nTempo (BPM):")
                # Simple BPM Toggle for demo (could be an input field)
                yield Select(
                    options=[("80", 80), ("100", 100), ("120", 120), ("140", 140)],
                    value=120,
                    id="bpm_selector",
                    allow_blank=False
                )

                yield Static("\nStatus:\n[red]OFF[/]", id="status_label")

            # MIDDLE: Metronome (Big Visuals)
            yield MetronomeDisplay(id="metronome_box")

            # RIGHT: Logs (Matrix Style)
            yield RichLog(id="logs", highlight=True, markup=True)

        yield Footer()

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
            new_bpm = int(event.value)
            self.tempo_engine.set_bpm(new_bpm)
            self.query_one("#logs", RichLog).write(f"[b]Tempo set to {new_bpm}[/]")

    def on_mount(self):
        # Start the clock immediately when app starts
        self.run_clock()

    @work(thread=True, exclusive=True)
    def run_clock(self):
        """The Heartbeat Worker: Runs constantly to update the metronome."""
        while self.processing_active:
            if self.tempo_engine.check_tick():
                # 1. Calculate Music State
                # step_counter is total 16th notes.
                # beat (1-4)
                # sub (0-3)
                total_steps = self.tempo_engine.step_counter
                beat_in_bar = ((total_steps // 4) % 4) + 1
                subdivision = total_steps % 4

                # 2. Update UI (Thread-safe)
                metro = self.query_one("#metronome_box", MetronomeDisplay)
                metro.current_beat = beat_in_bar
                metro.current_sub = subdivision

                # 3. Optional: Flash the border on the "One"
                if subdivision == 0 and beat_in_bar == 1:
                    self.call_from_thread(metro.styles.__setattr__, "border", "double red")
                elif subdivision == 0:
                    self.call_from_thread(metro.styles.__setattr__, "border", "solid green")

            # Tiny sleep to prevent CPU burn, but fast enough for 16th notes
            time.sleep(0.002)

    @work(thread=True, exclusive=True)
    def start_midi_listener(self, port_name):
        self.call_from_thread(self.query_one("#status_label", Static).update, f"[green]Listening:\n{port_name}[/]")

        if self.current_port: self.current_port.close()

        try:
            with mido.open_input(port_name) as port:
                self.current_port = port
                for msg in port:
                    if not self.processing_active: break

                    # LOGGING
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    if msg.type == 'note_on':
                        log_msg = f"[green]{timestamp} 🥁 NOTE {msg.note} (Vel {msg.velocity})[/]"
                    else:
                        log_msg = f"[dim]{timestamp} {msg}[/]"

                    self.call_from_thread(self.query_one("#logs", RichLog).write, log_msg)
        except Exception as e:
            self.call_from_thread(self.query_one("#logs", RichLog).write, f"[red]Error: {e}[/]")

    def on_unmount(self):
        self.processing_active = False
        if self.current_port: self.current_port.close()


if __name__ == "__main__":
    app = BayesianMidiPerformer()
    app.run()