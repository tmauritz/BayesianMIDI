import os
import time
from datetime import datetime

import pyagrum as gum
import pyagrum.lib.image as gumimage
from enum import IntEnum

class Momentum(IntEnum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2

class Anchor(IntEnum):
    ROOT = 0
    SECOND = 1
    THIRD = 2
    FOURTH = 3
    FIFTH = 4

class Tension(IntEnum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2

class Density(IntEnum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2

class Velocity(IntEnum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2

class Override(IntEnum):
    NONE = 0
    ALL = 1

class DynamicBayesianNetwork:

    memory = {
        "Past_Momentum": Momentum.LOW,
        "Past_Anchor": Anchor.ROOT,
        "Past_Tension": Tension.LOW,
        "Past_Density": Density.LOW,
        "Past_Velocity": Velocity.LOW
    }

    def __init__(self):
        print("Initializing Dynamic Network...")
        self.bn = self._build_network()
        self._fill_cpts()

    def _build_network(self):
        '''
        Builds the network without CPTs.
        :return: the base network.
        '''
        dbn = gum.BayesNet('BayesMIDI')

        # Define State Pairs with custom names
        states = [
            ("Past_Momentum", "Current_Momentum", Momentum),    #
            ("Past_Anchor", "Current_Anchor", Anchor),          #
            ("Past_Tension", "Current_Tension", Tension),       #
            ("Past_Density", "Current_Density", Density), #
            ("Past_Velocity", "Current_Velocity", Velocity)     #
        ]

        for past, current, labels in states:
            dbn.add(gum.LabelizedVariable(past, past, len(labels)))
            dbn.add(gum.LabelizedVariable(current, current, len(labels)))
            dbn.addArc(past, current)

        # --- INPUT NODES (From Accumulator) ---
        # These represent the physical reality of the current beat (T1)
        dbn.add(gum.LabelizedVariable('Input_Density', 'Raw_Density', len(Density)))
        dbn.add(gum.LabelizedVariable('Input_Velocity', 'Raw_Force', len(Velocity)))
        dbn.add(gum.LabelizedVariable('Override', 'Pad_Trigger', len(Override)))

        # --- VOICE NODES (Outputs) ---
        # We will assume our standard 3-voice setup: Bass, Lead, Embellish
        voices = ['Bass', 'Lead', 'Embellish']

        for v in voices:
            dbn.add(gum.LabelizedVariable(f'{v}_Gate', f'{v}_Gate', ['Rest', 'Play']))
            dbn.add(gum.LabelizedVariable(f'{v}_Pitch', f'{v}_Pitch', 12))
            dbn.add(gum.LabelizedVariable(f'{v}_Velocity', f'{v}_Velocity', len(Velocity)))

        # --- ARCS BETWEEN NODES ---
        # Inputs to Current States
        dbn.addArc('Input_Density', 'Current_Density')
        dbn.addArc('Input_Velocity', 'Current_Velocity')

        # Arcs between state nodes
        dbn.addArc('Current_Velocity', 'Current_Tension')
        dbn.addArc('Current_Tension', 'Current_Anchor')
        dbn.addArc('Current_Density', 'Current_Momentum')

        # Overrides to Voice Gates (Forces 100% Play)
        for v in voices:
            dbn.addArc('Override', f'{v}_Gate')

        # State Logic to Voices
        for v in voices:
            # Momentum influences Voice Gates
            dbn.addArc('Current_Momentum', f'{v}_Gate')

            # Harmonic Anchor AND Tension influence Voice Pitches
            dbn.addArc('Current_Anchor', f'{v}_Pitch')
            dbn.addArc('Current_Tension', f'{v}_Pitch')

            # Density AND Velocity influence Voice Velocities
            dbn.addArc('Current_Density', f'{v}_Velocity')
            dbn.addArc('Current_Velocity', f'{v}_Velocity')

        return dbn

    def _fill_cpts(self):
        """
        Populates all CPTs in the network using the values from DBN_CPTs.md.
        """
        # --- 1. CURRENT DENSITY ---
        # Parents: Past_Density, Input_Density
        self.bn.cpt("Current_Density")[{'Past_Density': int(Density.LOW), 'Input_Density': int(Density.LOW)}] = [0.95,
                                                                                                                 0.05,
                                                                                                                 0.00]
        self.bn.cpt("Current_Density")[{'Past_Density': int(Density.LOW), 'Input_Density': int(Density.MEDIUM)}] = [
            0.30, 0.65, 0.05]
        self.bn.cpt("Current_Density")[{'Past_Density': int(Density.LOW), 'Input_Density': int(Density.HIGH)}] = [0.10,
                                                                                                                  0.40,
                                                                                                                  0.50]
        self.bn.cpt("Current_Density")[{'Past_Density': int(Density.MEDIUM), 'Input_Density': int(Density.LOW)}] = [
            0.40, 0.55, 0.05]
        self.bn.cpt("Current_Density")[{'Past_Density': int(Density.MEDIUM), 'Input_Density': int(Density.MEDIUM)}] = [
            0.10, 0.80, 0.10]
        self.bn.cpt("Current_Density")[{'Past_Density': int(Density.MEDIUM), 'Input_Density': int(Density.HIGH)}] = [
            0.00, 0.30, 0.70]
        self.bn.cpt("Current_Density")[{'Past_Density': int(Density.HIGH), 'Input_Density': int(Density.LOW)}] = [0.15,
                                                                                                                  0.65,
                                                                                                                  0.20]
        self.bn.cpt("Current_Density")[{'Past_Density': int(Density.HIGH), 'Input_Density': int(Density.MEDIUM)}] = [
            0.05, 0.35, 0.60]
        self.bn.cpt("Current_Density")[{'Past_Density': int(Density.HIGH), 'Input_Density': int(Density.HIGH)}] = [0.00,
                                                                                                                   0.05,
                                                                                                                   0.95]

        # --- 2. CURRENT VELOCITY ---
        # Parents: Past_Velocity, Input_Velocity
        self.bn.cpt("Current_Velocity")[{'Past_Velocity': int(Velocity.LOW), 'Input_Velocity': int(Velocity.LOW)}] = [
            0.98, 0.02, 0.00]
        self.bn.cpt("Current_Velocity")[
            {'Past_Velocity': int(Velocity.LOW), 'Input_Velocity': int(Velocity.MEDIUM)}] = [0.40, 0.60, 0.00]
        self.bn.cpt("Current_Velocity")[{'Past_Velocity': int(Velocity.LOW), 'Input_Velocity': int(Velocity.HIGH)}] = [
            0.05, 0.45, 0.50]
        self.bn.cpt("Current_Velocity")[
            {'Past_Velocity': int(Velocity.MEDIUM), 'Input_Velocity': int(Velocity.LOW)}] = [0.50, 0.50, 0.00]
        self.bn.cpt("Current_Velocity")[
            {'Past_Velocity': int(Velocity.MEDIUM), 'Input_Velocity': int(Velocity.MEDIUM)}] = [0.05, 0.90, 0.05]
        self.bn.cpt("Current_Velocity")[
            {'Past_Velocity': int(Velocity.MEDIUM), 'Input_Velocity': int(Velocity.HIGH)}] = [0.00, 0.30, 0.70]
        self.bn.cpt("Current_Velocity")[{'Past_Velocity': int(Velocity.HIGH), 'Input_Velocity': int(Velocity.LOW)}] = [
            0.20, 0.60, 0.20]
        self.bn.cpt("Current_Velocity")[
            {'Past_Velocity': int(Velocity.HIGH), 'Input_Velocity': int(Velocity.MEDIUM)}] = [0.05, 0.45, 0.50]
        self.bn.cpt("Current_Velocity")[{'Past_Velocity': int(Velocity.HIGH), 'Input_Velocity': int(Velocity.HIGH)}] = [
            0.00, 0.05, 0.95]

        # --- 3. CURRENT MOMENTUM ---
        # Parents: Past_Momentum, Current_Density
        self.bn.cpt("Current_Momentum")[{'Past_Momentum': int(Momentum.LOW), 'Current_Density': int(Density.LOW)}] = [
            0.99, 0.01, 0.00]
        self.bn.cpt("Current_Momentum")[
            {'Past_Momentum': int(Momentum.LOW), 'Current_Density': int(Density.MEDIUM)}] = [0.20, 0.80, 0.00]
        self.bn.cpt("Current_Momentum")[{'Past_Momentum': int(Momentum.LOW), 'Current_Density': int(Density.HIGH)}] = [
            0.00, 0.30, 0.70]
        self.bn.cpt("Current_Momentum")[
            {'Past_Momentum': int(Momentum.MEDIUM), 'Current_Density': int(Density.LOW)}] = [0.40, 0.60, 0.00]
        self.bn.cpt("Current_Momentum")[
            {'Past_Momentum': int(Momentum.MEDIUM), 'Current_Density': int(Density.MEDIUM)}] = [0.05, 0.90, 0.05]
        self.bn.cpt("Current_Momentum")[
            {'Past_Momentum': int(Momentum.MEDIUM), 'Current_Density': int(Density.HIGH)}] = [0.00, 0.40, 0.60]
        self.bn.cpt("Current_Momentum")[{'Past_Momentum': int(Momentum.HIGH), 'Current_Density': int(Density.LOW)}] = [
            0.05, 0.80, 0.15]
        self.bn.cpt("Current_Momentum")[
            {'Past_Momentum': int(Momentum.HIGH), 'Current_Density': int(Density.MEDIUM)}] = [0.00, 0.20, 0.80]
        self.bn.cpt("Current_Momentum")[{'Past_Momentum': int(Momentum.HIGH), 'Current_Density': int(Density.HIGH)}] = [
            0.00, 0.01, 0.99]

        # --- 4. CURRENT TENSION ---
        # Parents: Past_Tension, Current_Velocity
        self.bn.cpt("Current_Tension")[{'Past_Tension': int(Tension.LOW), 'Current_Velocity': int(Velocity.LOW)}] = [
            0.90, 0.10, 0.00]
        self.bn.cpt("Current_Tension")[{'Past_Tension': int(Tension.LOW), 'Current_Velocity': int(Velocity.MEDIUM)}] = [
            0.30, 0.60, 0.10]
        self.bn.cpt("Current_Tension")[{'Past_Tension': int(Tension.LOW), 'Current_Velocity': int(Velocity.HIGH)}] = [
            0.05, 0.25, 0.70]
        self.bn.cpt("Current_Tension")[{'Past_Tension': int(Tension.MEDIUM), 'Current_Velocity': int(Velocity.LOW)}] = [
            0.60, 0.35, 0.05]
        self.bn.cpt("Current_Tension")[
            {'Past_Tension': int(Tension.MEDIUM), 'Current_Velocity': int(Velocity.MEDIUM)}] = [0.10, 0.80, 0.10]
        self.bn.cpt("Current_Tension")[
            {'Past_Tension': int(Tension.MEDIUM), 'Current_Velocity': int(Velocity.HIGH)}] = [0.00, 0.20, 0.80]
        self.bn.cpt("Current_Tension")[{'Past_Tension': int(Tension.HIGH), 'Current_Velocity': int(Velocity.LOW)}] = [
            0.10, 0.70, 0.20]
        self.bn.cpt("Current_Tension")[
            {'Past_Tension': int(Tension.HIGH), 'Current_Velocity': int(Velocity.MEDIUM)}] = [0.00, 0.30, 0.70]
        self.bn.cpt("Current_Tension")[{'Past_Tension': int(Tension.HIGH), 'Current_Velocity': int(Velocity.HIGH)}] = [
            0.00, 0.05, 0.95]

        # --- 5. CURRENT ANCHOR ---
        # The anchor_table loop now uses contiguous indices 0-4
        anchor_table = [
            (Anchor.ROOT, [0.95, 0.01, 0.01, 0.01, 0.02], [0.60, 0.10, 0.10, 0.10, 0.10],
             [0.05, 0.25, 0.20, 0.30, 0.20]),
            (Anchor.SECOND, [0.02, 0.95, 0.01, 0.01, 0.01], [0.20, 0.50, 0.10, 0.10, 0.10],
             [0.40, 0.05, 0.15, 0.10, 0.30]),
            (Anchor.THIRD, [0.01, 0.01, 0.95, 0.02, 0.01], [0.10, 0.10, 0.60, 0.10, 0.10],
             [0.30, 0.10, 0.05, 0.40, 0.15]),
            (Anchor.FOURTH, [0.01, 0.01, 0.01, 0.95, 0.02], [0.15, 0.10, 0.10, 0.50, 0.15],
             [0.50, 0.05, 0.05, 0.05, 0.35]),
            (Anchor.FIFTH, [0.05, 0.00, 0.00, 0.00, 0.95], [0.30, 0.05, 0.05, 0.05, 0.55],
             [0.80, 0.05, 0.05, 0.05, 0.05])
        ]
        for past_a, low_t, med_t, high_t in anchor_table:
            self.bn.cpt("Current_Anchor")[{'Past_Anchor': int(past_a), 'Current_Tension': int(Tension.LOW)}] = low_t
            self.bn.cpt("Current_Anchor")[{'Past_Anchor': int(past_a), 'Current_Tension': int(Tension.MEDIUM)}] = med_t
            self.bn.cpt("Current_Anchor")[{'Past_Anchor': int(past_a), 'Current_Tension': int(Tension.HIGH)}] = high_t

        # --- 6. VOICE GATES ---
        # Parents: Override, Current_Momentum
        for v in ['Bass', 'Lead', 'Embellish']:
            # Normal play logic (Override=NONE)
            self.bn.cpt(f"{v}_Gate")[{'Override': int(Override.NONE), 'Current_Momentum': int(Momentum.LOW)}] = [0.95,
                                                                                                                 0.05]
            self.bn.cpt(f"{v}_Gate")[{'Override': int(Override.NONE), 'Current_Momentum': int(Momentum.MEDIUM)}] = [
                0.40, 0.60]
            self.bn.cpt(f"{v}_Gate")[{'Override': int(Override.NONE), 'Current_Momentum': int(Momentum.HIGH)}] = [0.10,
                                                                                                                  0.90]
            # Forced Trigger (Override=ALL)
            for m in Momentum:
                self.bn.cpt(f"{v}_Gate")[{'Override': int(Override.ALL), 'Current_Momentum': int(m)}] = [0.00, 1.00]

        # --- 7. VOICE PITCHES ---
        # Map the contiguous Anchor Enum to your specific semitone intervals
        anchor_offsets = {
            Anchor.ROOT: 0,
            Anchor.SECOND: 2,
            Anchor.THIRD: 3,
            Anchor.FOURTH: 4,
            Anchor.FIFTH: 5
        }

        for v in ['Bass', 'Lead', 'Embellish']:
            for a in Anchor:
                offset = anchor_offsets[a]
                for t in Tension:
                    self.bn.cpt(f"{v}_Pitch")[
                        {'Current_Anchor': int(a), 'Current_Tension': int(t)}] = self.get_pitch_probabilities(
                        offset, t)

        # --- 8. VOICE VELOCITY ---
        # Parents: Current_Density, Current_Velocity
        vel_mapping = [
            (Density.LOW, Velocity.LOW, [0.90, 0.10, 0.00]),
            (Density.LOW, Velocity.MEDIUM, [0.30, 0.60, 0.10]),
            (Density.LOW, Velocity.HIGH, [0.05, 0.35, 0.60]),
            (Density.MEDIUM, Velocity.LOW, [0.70, 0.30, 0.00]),
            (Density.MEDIUM, Velocity.MEDIUM, [0.10, 0.80, 0.10]),
            (Density.MEDIUM, Velocity.HIGH, [0.00, 0.20, 0.80]),
            (Density.HIGH, Velocity.LOW, [0.50, 0.40, 0.10]),
            (Density.HIGH, Velocity.MEDIUM, [0.05, 0.70, 0.25]),
            (Density.HIGH, Velocity.HIGH, [0.00, 0.10, 0.90])
        ]
        for v in ['Bass', 'Lead', 'Embellish']:
            for dens, vel, probs in vel_mapping:
                self.bn.cpt(f"{v}_Velocity")[{'Current_Density': int(dens), 'Current_Velocity': int(vel)}] = probs

    def get_pitch_probabilities(self, anchor_offset, tension_level):
        """Helper to rotate base pitch weights based on anchor offset."""
        if tension_level == Tension.LOW:
            weights = [0.80, 0.00, 0.02, 0.00, 0.08, 0.01, 0.00, 0.08, 0.00, 0.01, 0.00, 0.00]
        elif tension_level == Tension.MEDIUM:
            weights = [0.30, 0.02, 0.10, 0.03, 0.20, 0.05, 0.02, 0.15, 0.03, 0.05, 0.02, 0.03]
        else:  # Tension.HIGH
            weights = [0.05, 0.10, 0.10, 0.10, 0.10, 0.10, 0.15, 0.05, 0.10, 0.10, 0.10, 0.05]

        # Rotate weights so index 0 corresponds to the anchor semitone
        rotated = weights[-anchor_offset:] + weights[:-anchor_offset]
        return rotated

    def tick(self, input_density, input_velocity, override_active=False):
        # Start the clock
        start_time = time.perf_counter()

        ie = gum.LazyPropagation(self.bn)

        # 1. SET EVIDENCE
        for key, value in self.memory.items():
            ie.setEvidence({key: int(value)})

        ie.setEvidence({
            'Input_Density': int(input_density),
            'Input_Velocity': int(input_velocity),
            'Override': int(Override.ALL if override_active else Override.NONE)
        })

        # 2. PERFORM INFERENCE (The computationally expensive part)
        ie.makeInference()

        # 3. UPDATE MEMORY
        self.memory["Past_Momentum"] = ie.posterior("Current_Momentum").argmax()
        self.memory["Past_Anchor"] = ie.posterior("Current_Anchor").argmax()
        self.memory["Past_Tension"] = ie.posterior("Current_Tension").argmax()
        self.memory["Past_Density"] = ie.posterior("Current_Density").argmax()
        self.memory["Past_Velocity"] = ie.posterior("Current_Velocity").argmax()

        # Stop the clock after network is reset
        end_time = time.perf_counter()
        inference_ms = (end_time - start_time) * 1000

        # 4. REPORT RESULTS
        print(f"[{inference_ms:5.2f}ms] | Anchor: {Anchor(self.memory['Past_Anchor']).name:7} | "
              f"Tension: {Tension(self.memory['Past_Tension']).name:7} | "
              f"Momentum: {Momentum(self.memory['Past_Momentum']).name:7}")

        return inference_ms

    def export_all_cpts(self):
        """
        Exports every Conditional Probability Table to the 'out/cpts' directory as readable text.
        """
        cpt_dir = os.path.join("out", "cpts")
        os.makedirs(cpt_dir, exist_ok=True)

        for node_id in self.bn.nodes():
            node_name = self.bn.variable(node_id).name()
            # Text files are the most reliable way to view high-dimensional CPTs in a script
            file_path = os.path.join(cpt_dir, f"{node_name.replace(' ', '_')}_CPT.txt")

            with open(file_path, "w") as f:
                # Casting the CPT to a string produces a formatted table
                f.write(str(self.bn.cpt(node_id)))

            print(f"Exported CPT for {node_name} to {file_path}")

    def save_full_model(self):
        """
        Saves the structure and CPTs to a .bif file.
        This is the standard format for Bayesian Network GUI tools.
        """
        # 1. Get the current time
        now = datetime.now()

        # 2. Format it (e.g., Year-Month-Day_Hour-Minute-Second)
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        # 3. Assemble the string
        filename = "bayesMIDI_network.bif"
        name, extension = filename.split(".")
        new_filename = f"{name}_{timestamp}.{extension}"

        output_path = os.path.join("out", new_filename)
        gum.saveBN(self.bn, output_path)
        print(f"Full model (BIF format) saved to: {output_path}")

    def export_node_graph(self):
        output_dir = "out"
        os.makedirs(output_dir, exist_ok=True)

        # Export as SVG vector graphic
        export_path = os.path.join(output_dir, "dbn_topology.svg")
        gumimage.export(self.bn, export_path)
        print(f"Network topology successfully exported to: {export_path}")


if __name__ == "__main__":
    network = DynamicBayesianNetwork()

    # Simulation: 8 Beats
    # (Input Density, Input Velocity)
    sequence = [
        (Density.LOW, Velocity.LOW),  # Beat 1: Starting soft
        (Density.MEDIUM, Velocity.MEDIUM),  # Beat 2: Building up
        (Density.HIGH, Velocity.HIGH),  # Beat 3: Peak intensity
        (Density.HIGH, Velocity.HIGH),  # Beat 4: Sustaining climax
        (Density.LOW, Velocity.LOW),  # Beat 5: Sudden stop (Watch Momentum/Ghosting)
        (Density.LOW, Velocity.LOW),  # Beat 6: Continued silence
        (Density.LOW, Velocity.LOW),  # Beat 7: Tension should be dropping
        (Density.LOW, Velocity.LOW),  # Beat 8: Return to rest
    ]

    print(f"{'Latency':>10} | {'Current Anchor':^15} | {'Tension':^15} | {'Momentum':^15}")
    print("-" * 65)

    latencies = []
    for d, v in sequence:
        ms = network.tick(d, v)
        latencies.append(ms)
        time.sleep(0.5)  # Simulate 120 BPM

    print("-" * 65)
    print(f"Average Latency: {sum(latencies) / len(latencies):.2f}ms")
    print(f"Max Latency:     {max(latencies):.2f}ms")