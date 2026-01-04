import random
from dataclasses import dataclass
from typing import Literal

# Types based on your tables
DrumType = Literal["Kick", "Snare", "Rim", "None"]
DensityLevel = Literal["Sparse", "Medium", "Busy"]
EnergyLevel = Literal["Chill", "Groove", "High"]
ChordType = Literal["I", "IV", "V", "vi"]
PitchFunction = Literal["Root", "3rd_5th", "Color"]

@dataclass
class BayesianInput:
    """Evidence variables (Section 5.2.2)"""
    drum_type: DrumType  # From MIDI Input
    velocity: int        # From MIDI Input (0-127)
    bar: int             # From Clock (1-4)
    step: int            # From Clock (1-16)

@dataclass
class BayesianOutput:
    """Query variables (Section 5.2.2)"""
    should_play: bool
    midi_note: int | None
    velocity: int
    duration: float  # In beats (0.25 = 16th, 1.0 = Quarter)
    channel: int
    debug_info: str  # To show "I -> Root" in your log


class BayesianMusicGenerator:
    def __init__(self):
        # ==========================================
        # LATENT NODE CPTS (Tables 1, 2, 3)
        # ==========================================

        # Table 1: Note Density P(Density | Bar, Drum)
        self.cpt_density = {
            # (Bar_Range_Start, Bar_Range_End, DrumType) -> {State: Prob}
            (1, 3, "Kick"): {"Sparse": 0.80, "Medium": 0.15, "Busy": 0.05},
            (1, 3, "Snare"): {"Sparse": 0.20, "Medium": 0.70, "Busy": 0.10},
            (1, 3, "Rim"): {"Sparse": 0.10, "Medium": 0.40, "Busy": 0.50},
            (4, 4, "Kick"): {"Sparse": 0.40, "Medium": 0.40, "Busy": 0.20},
            # Fallback for Bar 4 Snare/Rim
            (4, 4, "Snare"): {"Sparse": 0.05, "Medium": 0.25, "Busy": 0.70},
            (4, 4, "Rim"): {"Sparse": 0.05, "Medium": 0.25, "Busy": 0.70},
        }

        # Table 2: Energy P(Energy | Velocity, Density)
        # We simplify Velocity to "Soft" (<90) or "Loud" (>=90)
        self.cpt_energy = {
            ("Soft", "Sparse"): {"Chill": 0.95, "Groove": 0.05, "High": 0.00},
            ("Soft", "Busy"): {"Chill": 0.60, "Groove": 0.40, "High": 0.00},
            ("Loud", "Sparse"): {"Chill": 0.20, "Groove": 0.70, "High": 0.10},
            ("Loud", "Medium"): {"Chill": 0.05, "Groove": 0.50, "High": 0.45},
            ("Loud", "Busy"): {"Chill": 0.00, "Groove": 0.10, "High": 0.90},
        }

        # Table 3: Chords P(Chord | Bar, Step)
        self.cpt_chord = {
            # Simple map: Bar 1->I, Bar 2->IV, Bar 4->V
            1: {"I": 0.95, "IV": 0.0, "V": 0.05, "vi": 0.0},
            2: {"I": 0.10, "IV": 0.8, "V": 0.05, "vi": 0.05},
            3: {"I": 0.90, "IV": 0.05, "V": 0.05, "vi": 0.0},
            4: {"I": 0.05, "IV": 0.05, "V": 0.85, "vi": 0.05},
        }

        # Table 5: Pitch Function P(Function | Chord, BeatType)
        self.cpt_pitch_func = {
            ("I", "Downbeat"): {"Root": 0.80, "3rd_5th": 0.15, "Color": 0.05},
            ("I", "Offbeat"): {"Root": 0.20, "3rd_5th": 0.60, "Color": 0.20},
            ("V", "Any"): {"Root": 0.50, "3rd_5th": 0.30, "Color": 0.20},
            # Default
            ("Any", "Any"): {"Root": 0.30, "3rd_5th": 0.40, "Color": 0.30},
        }

    def infer(self, data: BayesianInput) -> BayesianOutput:
        """
        Runs the full Bayesian Inference chain:
        Input -> Latent -> Output
        """
        # --- PRE-CALCULATIONS ---
        # Derive Beat Type from Step (1-16)
        is_downbeat = data.step in [1, 5, 9, 13]
        beat_type = "Downbeat" if is_downbeat else "Offbeat"
        vel_category = "Loud" if data.velocity > 90 else "Soft"

        # --- STEP 1: LATENT VARIABLE INFERENCE ---

        # 1. Density (Table 1)
        # Find matching key in CPT
        density_probs = self._find_density_probs(data.bar, data.drum_type)
        current_density = self._sample(density_probs)

        # 2. Energy (Table 2)
        # Depends on Input Velocity and Inferred Density
        energy_probs = self.cpt_energy.get(
            (vel_category, current_density),
            {"Chill": 0.5, "Groove": 0.5, "High": 0.0}  # Fallback
        )
        current_energy = self._sample(energy_probs)

        # 3. Chord (Table 3)
        # Simplified: depends mainly on Bar
        chord_probs = self.cpt_chord.get(data.bar, {"I": 1.0})
        current_chord = self._sample(chord_probs)

        # --- STEP 2: OUTPUT VARIABLE INFERENCE ---

        # 4. Play Gate (Table 4)
        # Kick always plays on downbeats
        if data.drum_type == "Kick" and is_downbeat:
            should_play = (random.random() < 0.99)
        elif data.drum_type == "None":
            should_play = False
        else:
            # Logic for Snare/Rim based on density
            base_prob = 0.2 if current_density == "Sparse" else 0.8
            should_play = (random.random() < base_prob)

        if not should_play:
            return BayesianOutput(False, None, 0, 0, 0, "Rest")

        # 5. Pitch Function (Table 5)
        # Depends on Chord and Beat Type
        pitch_probs = self.cpt_pitch_func.get(
            (current_chord, beat_type),
            self.cpt_pitch_func[("Any", "Any")]
        )
        pitch_function = self._sample(pitch_probs)

        # 6. Resolve Pitch (Music Theory Helper)
        final_pitch = self._resolve_pitch(current_chord, pitch_function)

        # 7. Channel & Velocity (Tables 6 & 8)
        final_channel = 1 if data.drum_type == "Kick" else 2
        final_velocity = min(127, int(data.velocity * (1.2 if current_energy == "High" else 0.9)))

        return BayesianOutput(
            should_play=True,
            midi_note=final_pitch,
            velocity=final_velocity,
            duration=0.5,  # Placeholder for Table 7 logic
            channel=final_channel,
            debug_info=f"{current_chord} -> {pitch_function}"
        )

    # --- HELPERS ---

    def _find_density_probs(self, bar, drum):
        """Matches Table 1 logic regarding Bar ranges."""
        for (start, end, d_type), probs in self.cpt_density.items():
            if start <= bar <= end and d_type == drum:
                return probs
        return {"Medium": 1.0}  # Default

    def _sample(self, distribution: dict) -> str:
        """Weighted random choice from a dictionary {Option: Probability}."""
        choices = list(distribution.keys())
        weights = list(distribution.values())
        return random.choices(choices, weights=weights, k=1)[0]

    def _resolve_pitch(self, chord: ChordType, func: PitchFunction) -> int:
        """
        Translates abstract 'Chord V, 3rd' into a MIDI note.
        Assumes C Major (Root=60) for simplicity.
        """
        # Chord Offsets relative to C (60)
        chord_roots = {"I": 0, "IV": 5, "V": 7, "vi": 9}
        root_offset = chord_roots.get(chord, 0)

        # Interval Offsets
        if func == "Root":
            interval = 0
        elif func == "3rd_5th":
            interval = random.choice([4, 7])
        else:
            interval = random.choice([2, 11, 14])  # Color notes

        return 60 + root_offset + interval

