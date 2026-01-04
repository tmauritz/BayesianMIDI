from dataclasses import dataclass

@dataclass
class PerformanceSettings:
    """Stores all configurable parameters for the performance."""
    kick_note: int = 36
    snare_note: int = 38
    rim_note: int = 37

    def identify(self, note: int) -> str | None:
        """
        Returns the name of the instrument for a given MIDI note,
        or None if the note is not mapped.
        """

        #TODO: is there a more elegant way?
        if note == self.kick_note:
            return "Kick"
        if note == self.snare_note:
            return "Snare"
        if note == self.rim_note:
            return "Rim"
        return None