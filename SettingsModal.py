import mido
import time
from datetime import datetime
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, RichLog
from textual.containers import Grid, Container, Horizontal, Vertical


class SettingsScreen(ModalScreen):
    """A modal screen for configuring MIDI settings."""

    BINDINGS = [("escape", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        with Container(id="dialog"):
            with Horizontal(id="dialog_body"):
                # --- LEFT COLUMN: Settings & Inputs ---
                with Vertical(id="left_pane"):
                    yield Label("Connection Settings", classes="pane_header")

                    with Grid(id="settings_grid"):
                        # Connection Settings
                        yield Label("MIDI Input:")
                        yield Select([], id="input_selector", prompt="Select Input")

                        yield Label("MIDI Output:")
                        yield Select([], id="output_selector", prompt="Select Output")

                        # Note Mapping Settings
                        yield Label("Kick Note:")
                        yield Input(placeholder="36", id="kick_input", type="integer")

                        yield Label("Snare Note:")
                        yield Input(placeholder="38", id="snare_input", type="integer")

                        yield Label("Rim Note:")
                        yield Input(placeholder="37", id="rim_input", type="integer")

                        yield Button("Save & Close", variant="success", id="save_btn")

                # --- RIGHT COLUMN: Logs & Testing ---
                with Vertical(id="right_pane"):
                    yield Label("Testing & Monitor", classes="pane_header")

                    # Test Button
                    with Container(id="test_area"):
                        yield Button("Send Test Note (C4)", id="test_note_btn", variant="primary")

                    # Log Area
                    yield Label("MIDI Monitor:", classes="sub_label")
                    yield RichLog(id="midi_monitor", highlight=True, markup=True)


    def on_mount(self) -> None:
        """Load current values and populate port lists."""
        settings = self.app.settings
        self.query_one("#kick_input").value = str(settings.kick_note)
        self.query_one("#snare_input").value = str(settings.snare_note)
        self.query_one("#rim_input").value = str(settings.rim_note)

        try:
            inputs = [(name, name) for name in mido.get_input_names()]
            outputs = [(name, name) for name in mido.get_output_names()]
        except Exception:
            inputs = []
            outputs = []

        input_sel = self.query_one("#input_selector", Select)
        input_sel.set_options(inputs)

        output_sel = self.query_one("#output_selector", Select)
        output_sel.set_options(outputs)

        if self.app.current_input_port:
            input_sel.value = self.app.current_input_port.name

        if self.app.current_output_port:
            output_sel.value = self.app.current_output_port.name

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.control.id == "input_selector":
            if event.value != Select.BLANK:
                self.app.start_midi_listener(str(event.value))

        elif event.control.id == "output_selector":
            if event.value != Select.BLANK:
                self.app.set_midi_output_port(str(event.value))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save_btn":
            self.save_and_close()
        elif event.button.id == "test_note_btn":
            self.send_test_note()

    def send_test_note(self):
        port = self.app.current_output_port
        if port:
            try:
                port.send(mido.Message('note_on', note=60, velocity=100))
                time.sleep(0.1)
                port.send(mido.Message('note_off', note=60, velocity=0))
                self.notify("Sent Test Note (C4)")
            except Exception as e:
                self.notify(f"Error: {e}", severity="error")
        else:
            self.notify("No Output Port Selected", severity="warning")

    def save_and_close(self):
        try:
            self.app.settings.kick_note = int(self.query_one("#kick_input").value)
            self.app.settings.snare_note = int(self.query_one("#snare_input").value)
            self.app.settings.rim_note = int(self.query_one("#rim_input").value)
            self.dismiss()
            self.notify("Settings Saved!")
        except ValueError:
            self.notify("Please enter valid integers", severity="error")

    def handle_midi_input(self, note: int) -> None:
        log = self.query_one("#midi_monitor", RichLog)
        timestamp = datetime.now().strftime("%H:%M:%S")
        log.write(f"[{timestamp}] Note On: [bold cyan]{note}[/]")

        focused_widget = self.focused
        if isinstance(focused_widget, Input):
            focused_widget.value = str(note)
            self.notify(f"Mapped Note {note}")