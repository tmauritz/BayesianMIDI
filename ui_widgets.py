from textual.app import ComposeResult
from textual.containers import Vertical, Container
from textual.widgets import Digits, Input, Label
from textual.containers import Horizontal



class MetronomeDisplay(Vertical):
    """
    A composed widget that holds a Big 'Digits' display.
    """

    CSS_PATH = "styles/widgets.tcss"

    def compose(self) -> ComposeResult:
        yield Label("1", id="bar_digits")
        yield Digits("1", id="beat_digits")

    def update_beat(self, beat, sub, bar):
        # Update the Big Number
        self.query_one("#beat_digits", Digits).update(str(beat))
        self.query_one("#bar_digits", Label).update(str(bar))

        # Highlight logic
        color = "grey"
        if sub == 0:
            color = "green" if beat == 1 else "yellow"

        # Flash Border
        if sub == 0:
            border_col = "red" if beat == 1 else "green"
            self.styles.border = ("double", border_col)
        else:
            self.styles.border = ("solid", "green")

