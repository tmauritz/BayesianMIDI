from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Digits, Label


class MetronomeDisplay(Vertical):
    """
    A composed widget that holds a Big 'Digits' display.
    """

    CSS_PATH = "styles/widgets.tcss"

    def compose(self) -> ComposeResult:
        yield Digits("1", id="beat_digits")
        yield Label("O . . .", id="sub_dots")

    def update_beat(self, beat, sub):
        # Update the Big Number
        self.query_one("#beat_digits", Digits).update(str(beat))

        # Update the dots
        dots = ["O", ".", ".", "."]

        # Highlight logic
        color = "grey"
        if sub == 0:
            color = "green" if beat == 1 else "yellow"
            dots[0] = f"[{color} bold]O[/]"
        else:
            dots[sub] = f"[white bold]X[/]"

        self.query_one("#sub_dots", Label).update(" ".join(dots))

        # Flash Border
        if sub == 0:
            border_col = "red" if beat == 1 else "green"
            self.styles.border = ("double", border_col)
        else:
            self.styles.border = ("solid", "green")