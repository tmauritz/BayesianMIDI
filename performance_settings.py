from dataclasses import dataclass

from bayesian_network import DrumType


@dataclass
class PerformanceSettings:
    """Stores all configurable parameters for the performance."""
    kick_note: int = 60
    snare_note: int = 65
    rim_note: int = 67

    def identify(self, note: int) -> DrumType:
        """
        Returns the name of the instrument for a given MIDI note,
        or None if the note is not mapped.
        """

        #TODO: is there a more elegant way?
        if note == self.kick_note:
            return DrumType.KICK
        if note == self.snare_note:
            return DrumType.SNARE
        if note == self.rim_note:
            return DrumType.RIM
        return DrumType.NONE