from dataclasses import dataclass
from enum import IntEnum

class DrumType(IntEnum):
    NONE = 0
    KICK = 1
    SNARE = 2
    RIM = 3


class DensityLevel(IntEnum):
    SPARSE = 0
    MEDIUM = 1
    BUSY = 2


class EnergyLevel(IntEnum):
    CHILL = 0
    GROOVE = 1
    HIGH = 2


class ChordType(IntEnum):
    I = 1
    IV = 4
    V = 5
    VI = 6


class BeatType(IntEnum):
    DOWNBEAT = 0
    OFFBEAT = 1
    SUBDIVISION = 2


class PitchFunc(IntEnum):
    ROOT = 0
    THIRD_FIFTH = 1
    COLOR = 2


@dataclass
class BayesianInput:
    drum_type: DrumType
    velocity: int
    bar: int
    step: int


@dataclass
class BayesianOutput:
    should_play: bool
    midi_note: int
    velocity: int
    duration: float
    channel: int
    debug_info: str

