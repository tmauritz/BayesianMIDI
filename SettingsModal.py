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
                yield Label("")
                yield Button("Save & Close", variant="success", id="save_btn")

    def on_mount(self) -> None:
        """Load current values from the settings object."""
        settings = self.app.settings
        self.query_one("#kick_input").value = str(settings.kick_note)
        self.query_one("#snare_input").value = str(settings.snare_note)
        self.query_one("#rim_input").value = str(settings.rim_note)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save_btn":
            # Save values back to the main app instance
            try:
                # Save directly to the object
                self.app.settings.kick_note = int(self.query_one("#kick_input").value)
                self.app.settings.snare_note = int(self.query_one("#snare_input").value)
                self.app.settings.rim_note = int(self.query_one("#rim_input").value)

                self.dismiss() #close modal
                self.notify("Settings Saved!")
            except ValueError:
                self.notify("Please enter valid integers", severity="error")

    def handle_midi_input(self, note: int) -> None:
        """
        Called by the main app when a MIDI note is received.
        If an input field is focused, write the note number into it.
        """
        # Get the widget that currently has focus
        focused_widget = self.focused

        # Check if the focused widget is one of our Inputs
        if isinstance(focused_widget, Input):
            # Update the text value
            focused_widget.value = str(note)

            # Optional: Add a quick visual flash to confirm receipt
            # self.notify(f"Mapped Note: {note}")