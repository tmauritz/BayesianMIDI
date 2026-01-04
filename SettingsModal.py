from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label
from textual.containers import Grid, Container


class SettingsScreen(ModalScreen):
    """A modal screen for configuring MIDI settings."""

    BINDINGS = [("escape", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        with Container(id="dialog"):
            yield Label("MIDI Output Settings", id="dialog_title")

            # Use a Grid for aligned labels and inputs
            with Grid(id="settings_grid"):
                yield Label("Kick Note:")
                yield Input(placeholder="36", id="kick_input", type="integer")

                yield Label("Snare Note:")
                yield Input(placeholder="38", id="snare_input", type="integer")

                yield Label("Rim Note:")
                yield Input(placeholder="37", id="rim_input", type="integer")

            with Container(id="dialog_buttons"):
                yield Button("Save & Close", variant="success", id="save_btn")

    def on_mount(self) -> None:
        """Pre-fill inputs with current values from the main app."""
        # Access the main app using self.app
        self.query_one("#kick_input").value = str(getattr(self.app, "kick_note", 36))
        self.query_one("#snare_input").value = str(getattr(self.app, "snare_note", 38))
        self.query_one("#rim_input").value = str(getattr(self.app, "rim_note", 37))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save_btn":
            # Save values back to the main app instance
            try:
                self.app.kick_note = int(self.query_one("#kick_input").value)
                self.app.snare_note = int(self.query_one("#snare_input").value)
                self.app.rim_note = int(self.query_one("#rim_input").value)
                self.dismiss()  # Close the screen
            except ValueError:
                self.notify("Please enter valid integers", severity="error")