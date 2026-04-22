import os
import pyagrum as gum
import pyagrum.lib.image as gumimage
from enum import IntEnum

class Momentum(IntEnum):
    LOW = 0,
    MEDIUM = 1,
    HIGH = 2

class Anchor(IntEnum):
    ROOT = 0,
    SECOND = 1,
    THIRD = 2,
    FOURTH = 3,
    FIFTH = 4

class Tension(IntEnum):
    LOW = 0,
    MEDIUM = 1,
    HIGH = 2

class Intensity(IntEnum):
    LOW = 0,
    MEDIUM = 1,
    HIGH = 2,

class Velocity(IntEnum):
    LOW = 0,
    MEDIUM = 1,
    HIGH = 2,

class Override(IntEnum):
    NONE = 0,
    ALL = 1

class DynamicBayesianNetwork:

    memory = {
        "Past Momentum": Momentum.LOW,
        "Past Anchor": Anchor.ROOT,
        "Past Tension": Tension.LOW,
        "Past Intensity": Intensity.LOW,
        "Past Velocity": Velocity.LOW
    }

    def __init__(self):
        self.bn = self._build_network()

    def _build_network(self):
        dbn = gum.BayesNet('MIDI_Partner_Revised_Architecture')

        # Define State Pairs with custom names
        states = [
            ("Past Momentum", "Current Momentum", Momentum),
            ("Past Anchor", "Current Anchor", Anchor),
            ("Past Tension", "Current Tension", Tension),
            ("Past Intensity", "Current Intensity", Intensity),
            ("Past Velocity", "Current Velocity", Velocity)
        ]

        for past, current, labels in states:
            dbn.add(gum.LabelizedVariable(past, past, len(labels)))
            dbn.add(gum.LabelizedVariable(current, current, len(labels)))
            dbn.addArc(past, current)

        # --- INPUT NODES (From Accumulator) ---
        # These represent the physical reality of the current beat (T1)
        dbn.add(gum.LabelizedVariable('Input Intensity', 'Raw Density', len(Intensity)))
        dbn.add(gum.LabelizedVariable('Input Velocity', 'Raw Force', len(Velocity)))
        dbn.add(gum.LabelizedVariable('Override', 'Pad Trigger', len(Override)))

        # --- VOICE NODES (Outputs at T1) ---
        # We will assume your standard 3-voice setup: Bass, Lead, Embellish
        voices = ['Bass', 'Lead', 'Embellish']

        for v in voices:
            dbn.add(gum.LabelizedVariable(f'{v} Gate', f'{v} Gate', ['Rest', 'Play']))
            dbn.add(gum.LabelizedVariable(f'{v} Pitch', f'{v} Pitch', 12))
            dbn.add(gum.LabelizedVariable(f'{v} Velocity', f'{v} Velocity', len(Velocity)))

        # --- CONNECTING THE ARCS ---
        # A. Inputs to Current States
        dbn.addArc('Input Intensity', 'Current Intensity')
        dbn.addArc('Input Velocity', 'Current Velocity')

        # B. Overrides to Voice Gates (Forces 100% Play)
        for v in voices:
            dbn.addArc('Override', f'{v} Gate')

        # C. State Logic to Voices
        for v in voices:
            # Momentum influences Voice Gates
            dbn.addArc('Current Momentum', f'{v} Gate')

            # Harmonic Anchor AND Tension influence Voice Pitches
            dbn.addArc('Current Anchor', f'{v} Pitch')
            dbn.addArc('Current Tension', f'{v} Pitch')

            # Intensity AND Velocity influence Voice Velocities
            dbn.addArc('Current Intensity', f'{v} Velocity')
            dbn.addArc('Current Velocity', f'{v} Velocity')

        # --- EXPORTING ---
        output_dir = "out"
        os.makedirs(output_dir, exist_ok=True)

        # Export as a crisp SVG vector graphic
        export_path = os.path.join(output_dir, "revised_network_topology.svg")
        gumimage.export(dbn, export_path)
        print(f"Network topology successfully exported to: {export_path}")

        return dbn

if __name__ == "__main__":
    network = DynamicBayesianNetwork()