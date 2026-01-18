import random
import pyagrum as gum

from bayesian.bayesian_network_ag import BayesianMusicGeneratorAg
from bayesian.bayesian_network_helpers import *

# Assumes Enums and Dataclasses are imported
# from my_music_types import DrumType, DensityLevel, EnergyLevel, ChordType, BeatType, PitchFunc, BayesianInput, BayesianOutput

class BakedBayesianGenerator:
    def __init__(self):
        print("Initializing Logic Engine...")
        print("  - Building Bayesian Network...")
        # We rely on the PyAgrum class just for the baking phase
        # (Assuming the class from the previous step is named BayesianMusicGeneratorAg)
        self._engine = BayesianMusicGeneratorAg()

        print(f"  - Baking 512 states into lookup table...", end="")
        self._lookup_table = {}
        self._bake_logic()
        print(" Done.")

        # We can now delete the heavy engine to free memory
        del self._engine

    def _bake_logic(self):
        """
        Iterates every possible input combination, runs the Bayesian inference,
        and saves the resulting probability distributions.
        """
        # Iterate all Dimensions
        for bar in range(1, 5):
            for drum in [DrumType.NONE, DrumType.KICK, DrumType.SNARE, DrumType.RIM]:
                # We iterate the categorical velocity (Soft/Loud), not 0-127
                for is_loud in [False, True]:
                    for step in range(1, 17):

                        # 1. Setup Evidence in the Engine
                        # We have to replicate the 'infer' setup logic here manually
                        # to get the raw distributions out.

                        # Context derivation
                        is_downbeat = (step % 4 == 1)
                        is_offbeat = (step % 2 == 1) and not is_downbeat
                        if is_downbeat:
                            b_enum = BeatType.DOWNBEAT
                        elif is_offbeat:
                            b_enum = BeatType.OFFBEAT
                        else:
                            b_enum = BeatType.SUBDIVISION

                        # Convert Step to "Harmonic Context" logic if needed
                        # (Your current model relies on Bar, not Step, for chords, so this is easy)

                        # Set Evidence directly
                        # We use the string keys for safety/clarity during baking
                        self._engine.ie.setEvidence({
                            'Bar': bar - 1,
                            'Drum_Type': int(drum),
                            'In_Velocity': 1 if is_loud else 0,
                            'Beat_Type': int(b_enum)
                        })

                        # 2. Extract Distributions (The "Baking")
                        # We grab the raw list of floats [P(0), P(1), ...] for each node

                        # Optimization: Check Play Gate first.
                        # If P(Play=True) is 0.0 (like for DrumType.NONE), we store None to save space.
                        play_dist = self._engine.ie.posterior('Play_Note').tolist()

                        if play_dist[1] < 0.001:  # P(Play) is effectively 0
                            cache_entry = None
                        else:
                            cache_entry = {
                                'play': play_dist,
                                'pitch': self._engine.ie.posterior('Pitch_Func').tolist(),
                                'chord': self._engine.ie.posterior('Chord').tolist(),
                                'energy': self._engine.ie.posterior('Energy').tolist(),
                                'channel': self._engine.ie.posterior('Out_Channel').tolist()
                            }

                        # 3. Store in Table
                        # Key: (Bar, DrumEnum, IsLoud, Step)
                        key = (bar, drum, is_loud, step)
                        self._lookup_table[key] = cache_entry

                        # Reset for next loop
                        self._engine.ie.eraseAllEvidence()

    def infer(self, data: BayesianInput) -> BayesianOutput:
        """
        Real-time inference. Zero graph traversal. Pure dictionary lookup + random math.
        """
        # 1. Create Lookup Key
        is_loud = data.velocity > 90
        key = (data.bar, data.drum_type, is_loud, data.step)

        # 2. Retrieve Probabilities
        dists = self._lookup_table.get(key)

        # Fast Fail (Rest)
        if dists is None:
            return BayesianOutput(False, 0, 0, 0, 0, "Rest (Baked)")

        # 3. Sample from Distributions
        # choices() is fast. It uses the weights we baked.

        # Play Gate
        should_play = random.choices([False, True], weights=dists['play'])[0]
        if not should_play:
            return BayesianOutput(False, 0, 0, 0, 0, "Rest")

        # Pitch Function
        pf_val = random.choices(list(PitchFunc), weights=dists['pitch'])[0]

        # Chord
        c_enums = [ChordType.I, ChordType.IV, ChordType.V, ChordType.VI]
        current_chord = random.choices(c_enums, weights=dists['chord'])[0]

        # Energy
        current_energy = random.choices(list(EnergyLevel), weights=dists['energy'])[0]

        # Channel
        # Indices 0,1,2 map to MIDI 1,2,3
        channel_idx = random.choices([0, 1, 2], weights=dists['channel'])[0]
        final_channel = channel_idx + 1

        # 4. Post-Processing Math (Deterministic)
        # (This logic must live here because it depends on the specific random variables we just sampled)

        # Velocity Math
        energy_mult = 1.2 if current_energy == EnergyLevel.HIGH else 0.9
        final_velocity = int(data.velocity * energy_mult)
        if final_velocity > 127: final_velocity = 127

        # Pitch Math
        final_pitch = self._resolve_pitch(current_chord, pf_val, final_channel)

        return BayesianOutput(
            should_play=True,
            midi_note=final_pitch,
            velocity=final_velocity,
            duration=0.5,
            channel=final_channel,
            debug_info=f"{current_chord.name} -> {pf_val.name} (Baked)"
        )

    def _resolve_pitch(self, chord: ChordType, func: PitchFunc, channel: int) -> int:

        # 1. Determine Root Offset based on Chord
        root_offset = 0
        if chord == ChordType.IV:
            root_offset = 5
        elif chord == ChordType.V:
            root_offset = 7
        elif chord == ChordType.VI:
            root_offset = 9

        # 2. Determine Interval based on Pitch Function
        interval = 0
        if func == PitchFunc.THIRD_FIFTH:
            interval = 4 if random.random() < 0.5 else 7
        elif func == PitchFunc.COLOR:
            r = random.random()
            if r < 0.33:
                interval = 2
            elif r < 0.66:
                interval = 11
            else:
                interval = 14

        # 3. Calculate Base Pitch (Middle C approx)
        base_pitch = 60 + root_offset + interval

        # 4. Apply Channel Transposition
        # Channel 1 (Bass) -> Down 2 octave (-24)
        # Channel 2 (Mid) -> Down 1 octave
        # Channel 3 (Lead) -> Up 2 octaves (+24)
        if channel == 1:
            base_pitch -= 24
        elif channel == 2:
            base_pitch -= 12
        elif channel == 3:
            base_pitch += 24

        return base_pitch