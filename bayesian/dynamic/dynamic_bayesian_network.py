import os
import time

import pyagrum as gum
import pyagrum.lib.image as gumimage
from enum import IntEnum

class Momentum(IntEnum):
    LOW = 0,
    MEDIUM = 1,
    HIGH = 2

class Anchor(IntEnum):
    ROOT = 0,
    SECOND = 2,
    THIRD = 3,
    FOURTH = 4,
    FIFTH = 5

class Tension(IntEnum):
    LOW = 0,
    MEDIUM = 1,
    HIGH = 2

class Density(IntEnum):
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
        "Past Density": Density.LOW,
        "Past Velocity": Velocity.LOW
    }

    def __init__(self):
        print("Initializing Dynamic Network...")
        self.bn = self._build_network()

    def _build_network(self):
        '''
        Builds the network without CPTs.
        :return: the base network.
        '''
        dbn = gum.BayesNet('BayesMIDI')

        # Define State Pairs with custom names
        states = [
            ("Past Momentum", "Current Momentum", Momentum),    #
            ("Past Anchor", "Current Anchor", Anchor),          #
            ("Past Tension", "Current Tension", Tension),       #
            ("Past Density", "Current Density", Density), #
            ("Past Velocity", "Current Velocity", Velocity)     #
        ]

        for past, current, labels in states:
            dbn.add(gum.LabelizedVariable(past, past, len(labels)))
            dbn.add(gum.LabelizedVariable(current, current, len(labels)))
            dbn.addArc(past, current)

        # --- INPUT NODES (From Accumulator) ---
        # These represent the physical reality of the current beat (T1)
        dbn.add(gum.LabelizedVariable('Input Density', 'Raw Density', len(Density)))
        dbn.add(gum.LabelizedVariable('Input Velocity', 'Raw Force', len(Velocity)))
        dbn.add(gum.LabelizedVariable('Override', 'Pad Trigger', len(Override)))

        # --- VOICE NODES (Outputs) ---
        # We will assume our standard 3-voice setup: Bass, Lead, Embellish
        voices = ['Bass', 'Lead', 'Embellish']

        for v in voices:
            dbn.add(gum.LabelizedVariable(f'{v} Gate', f'{v} Gate', ['Rest', 'Play']))
            dbn.add(gum.LabelizedVariable(f'{v} Pitch', f'{v} Pitch', 12))
            dbn.add(gum.LabelizedVariable(f'{v} Velocity', f'{v} Velocity', len(Velocity)))

        # --- ARCS BETWEEN NODES ---
        # Inputs to Current States
        dbn.addArc('Input Density', 'Current Density')
        dbn.addArc('Input Velocity', 'Current Velocity')

        # Arcs between state nodes
        dbn.addArc('Current Velocity', 'Current Tension')
        dbn.addArc('Current Tension', 'Current Anchor')
        dbn.addArc('Current Density', 'Current Momentum')

        # Overrides to Voice Gates (Forces 100% Play)
        for v in voices:
            dbn.addArc('Override', f'{v} Gate')

        # State Logic to Voices
        for v in voices:
            # Momentum influences Voice Gates
            dbn.addArc('Current Momentum', f'{v} Gate')

            # Harmonic Anchor AND Tension influence Voice Pitches
            dbn.addArc('Current Anchor', f'{v} Pitch')
            dbn.addArc('Current Tension', f'{v} Pitch')

            # Density AND Velocity influence Voice Velocities
            dbn.addArc('Current Density', f'{v} Velocity')
            dbn.addArc('Current Velocity', f'{v} Velocity')

        # --- EXPORTING ---
        output_dir = "out"
        os.makedirs(output_dir, exist_ok=True)

        # Export as SVG vector graphic
        export_path = os.path.join(output_dir, "revised_network_topology.svg")
        gumimage.export(dbn, export_path)
        print(f"Network topology successfully exported to: {export_path}")

        return dbn

    def tick(self, input_Density, input_velocity, override_active=False):
        """
        Executes every metronome pulse.
        """
        ie = gum.LazyPropagation(self.bn)

        # 1. SET EVIDENCE: Transfer memory from last tick to 'Past' nodes
        for key, value in self.memory.items():
            ie.setEvidence({key: int(value)})

        # 2. SET EVIDENCE: Current physical drum inputs
        ie.setEvidence({
            'Input Density': int(input_Density),
            'Input Velocity': int(input_velocity),
            'Override': int(Override.ALL if override_active else Override.NONE)
        })

        # 3. PERFORM INFERENCE
        ie.makeInference()

        # 4. UPDATE MEMORY: For the next beat (Shift Current -> Past)
        # We use argmax() to find the most likely state determined by the DBN
        self.memory["Past Momentum"] = ie.posterior("Current Momentum").argmax()
        self.memory["Past Anchor"] = ie.posterior("Current Anchor").argmax()
        self.memory["Past Tension"] = ie.posterior("Current Tension").argmax()
        self.memory["Past Density"] = ie.posterior("Current Density").argmax()
        self.memory["Past Velocity"] = ie.posterior("Current Velocity").argmax()

        # 5. GENERATE OUTPUT: Print decisions for each voice
        print(f"\n--- Metronome Tick | State: {Anchor(self.memory['Past Anchor']).name} ---")
        voices = ['Bass', 'Lead', 'Embellish']
        for v in voices:
            gate_prob = ie.posterior(f'{v} Gate')[1]  # Prob of 'Play'

            if gate_prob > 0.5:  # Simple threshold for the console demo
                pitch_idx = ie.posterior(f'{v} Pitch').argmax()
                vel_idx = ie.posterior(f'{v} Velocity').argmax()
                print(f" > {v:9}: PLAY | Pitch: {pitch_idx:2} | Vel: {Velocity(vel_idx).name}")
            else:
                print(f" > {v:9}: REST")


if __name__ == "__main__":
    network = DynamicBayesianNetwork()
