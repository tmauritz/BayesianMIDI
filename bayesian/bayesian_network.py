import random

from bayesian.bayesian_network_helpers import *

class BayesianMusicGenerator:
    def __init__(self):
        # We pre-split data into ([Choices], [Weights]) tuples.
        # This prevents creating lists inside the real-time loop.

        # --- Table 1: Density ---
        # Flattened Map: (Bar, DrumType) -> ([DensityLevels], [Weights])
        self._density_map = {}

        # Helper to register range logic once at startup
        def register_density(bar_start, bar_end, drum, dist):
            choices = tuple(dist.keys())
            weights = tuple(dist.values())
            for b in range(bar_start, bar_end + 1):
                self._density_map[(b, drum)] = (choices, weights)

        # Bar 1-3
        register_density(1, 3, DrumType.KICK,
                         {DensityLevel.SPARSE: 0.80, DensityLevel.MEDIUM: 0.15, DensityLevel.BUSY: 0.05})
        register_density(1, 3, DrumType.SNARE,
                         {DensityLevel.SPARSE: 0.20, DensityLevel.MEDIUM: 0.70, DensityLevel.BUSY: 0.10})
        register_density(1, 3, DrumType.RIM,
                         {DensityLevel.SPARSE: 0.10, DensityLevel.MEDIUM: 0.40, DensityLevel.BUSY: 0.50})
        # Bar 4
        register_density(4, 4, DrumType.KICK,
                         {DensityLevel.SPARSE: 0.40, DensityLevel.MEDIUM: 0.40, DensityLevel.BUSY: 0.20})
        register_density(4, 4, DrumType.SNARE,
                         {DensityLevel.SPARSE: 0.05, DensityLevel.MEDIUM: 0.25, DensityLevel.BUSY: 0.70})
        register_density(4, 4, DrumType.RIM,
                         {DensityLevel.SPARSE: 0.05, DensityLevel.MEDIUM: 0.25, DensityLevel.BUSY: 0.70})

        # --- Table 2: Energy ---
        # Map: (VelCategory (0=Soft, 1=Loud), Density) -> ([EnergyLevels], [Weights])
        self._energy_map = {}

        def register_energy(is_loud, density, dist):
            self._energy_map[(1 if is_loud else 0, density)] = (tuple(dist.keys()), tuple(dist.values()))

        register_energy(False, DensityLevel.SPARSE,
                        {EnergyLevel.CHILL: 0.95, EnergyLevel.GROOVE: 0.05, EnergyLevel.HIGH: 0.0})
        register_energy(False, DensityLevel.BUSY,
                        {EnergyLevel.CHILL: 0.60, EnergyLevel.GROOVE: 0.40, EnergyLevel.HIGH: 0.0})
        register_energy(True, DensityLevel.SPARSE,
                        {EnergyLevel.CHILL: 0.20, EnergyLevel.GROOVE: 0.70, EnergyLevel.HIGH: 0.10})
        register_energy(True, DensityLevel.MEDIUM,
                        {EnergyLevel.CHILL: 0.05, EnergyLevel.GROOVE: 0.50, EnergyLevel.HIGH: 0.45})
        register_energy(True, DensityLevel.BUSY,
                        {EnergyLevel.CHILL: 0.00, EnergyLevel.GROOVE: 0.10, EnergyLevel.HIGH: 0.90})

        # --- Table 3: Chords ---
        # Map: Bar -> ([ChordTypes], [Weights])
        self._chord_map = {
            1: ((ChordType.I, ChordType.V), (0.95, 0.05)),
            2: ((ChordType.I, ChordType.IV, ChordType.V, ChordType.VI), (0.10, 0.80, 0.05, 0.05)),
            3: ((ChordType.I, ChordType.IV, ChordType.V), (0.90, 0.05, 0.05)),
            4: ((ChordType.I, ChordType.IV, ChordType.V, ChordType.VI), (0.05, 0.05, 0.85, 0.05)),
        }

        # --- Table 5: Pitch Function ---
        # Map: (Chord, BeatType) -> ([PitchFuncs], [Weights])
        self._pitch_map = {}

        # Default distribution to fallback on
        self._pitch_fallback = ((PitchFunc.ROOT, PitchFunc.THIRD_FIFTH, PitchFunc.COLOR), (0.30, 0.40, 0.30))

        # Specific overrides
        self._pitch_map[(ChordType.I, BeatType.DOWNBEAT)] = ((PitchFunc.ROOT, PitchFunc.THIRD_FIFTH, PitchFunc.COLOR),
                                                             (0.80, 0.15, 0.05))
        self._pitch_map[(ChordType.I, BeatType.OFFBEAT)] = ((PitchFunc.ROOT, PitchFunc.THIRD_FIFTH, PitchFunc.COLOR),
                                                            (0.20, 0.60, 0.20))
        self._pitch_map[(ChordType.V, BeatType.DOWNBEAT)] = ((PitchFunc.ROOT, PitchFunc.THIRD_FIFTH, PitchFunc.COLOR),
                                                             (0.50, 0.30,
                                                              0.20))  # Using 'Downbeat' to proxy 'Any' for now

    def infer(self, data: BayesianInput) -> BayesianOutput:
        # --- PRE-CALCULATIONS ---
        is_downbeat = (data.step % 4 == 1)  # 1, 5, 9, 13
        is_offbeat = (data.step % 2 == 1) and not is_downbeat

        if is_downbeat:
            beat_type = BeatType.DOWNBEAT
        elif is_offbeat:
            beat_type = BeatType.OFFBEAT
        else:
            beat_type = BeatType.SUBDIVISION

        is_loud = 1 if data.velocity > 90 else 0

        # --- STEP 1: LATENT VARIABLES  ---

        # 1. Density
        d_choices, d_weights = self._density_map.get((data.bar, data.drum_type),
                                                     ([DensityLevel.MEDIUM], [1.0]))
        current_density = random.choices(d_choices, weights=d_weights)[0]

        # 2. Energy
        e_key = (is_loud, current_density)
        e_choices, e_weights = self._energy_map.get(e_key, ([EnergyLevel.CHILL], [1.0]))
        current_energy = random.choices(e_choices, weights=e_weights)[0]

        # 3. Chord
        c_choices, c_weights = self._chord_map.get(data.bar, ([ChordType.I], [1.0]))
        current_chord = random.choices(c_choices, weights=c_weights)[0]

        # --- STEP 2: OUTPUT VARIABLES ---

        # 4. Play Gate
        if data.drum_type == DrumType.KICK and is_downbeat:
            should_play = (random.random() < 0.99)
        elif data.drum_type == DrumType.NONE:
            should_play = False
        else:
            base_prob = 0.2 if current_density == DensityLevel.SPARSE else 0.8
            should_play = (random.random() < base_prob)

        if not should_play:
            # Quick exit
            return BayesianOutput(False, 0, 0, 0, 0, "Rest")

        # 5. Pitch Function
        p_key = (current_chord, beat_type)
        p_choices, p_weights = self._pitch_map.get(p_key, self._pitch_fallback)
        pitch_func = random.choices(p_choices, weights=p_weights)[0]

        # 6. Resolve Pitch
        final_pitch = self._resolve_pitch(current_chord, pitch_func)

        # 7. Velocity & Channel
        final_channel = 1 if data.drum_type == DrumType.KICK else 2

        # optimized velocity math
        energy_mult = 1.2 if current_energy == EnergyLevel.HIGH else 0.9
        final_velocity = int(data.velocity * energy_mult)
        if final_velocity > 127: final_velocity = 127

        return BayesianOutput(
            should_play=True,
            midi_note=final_pitch,
            velocity=final_velocity,
            duration=0.5,
            channel=final_channel,
            debug_info=f"{current_chord.name} -> {pitch_func.name}"
        )

    def _resolve_pitch(self, chord: ChordType, func: PitchFunc) -> int:
        # Offsets relative to C (60)
        # Using if/elif is faster than dictionary creation inside the method
        root_offset = 0
        if chord == ChordType.IV:
            root_offset = 5
        elif chord == ChordType.V:
            root_offset = 7
        elif chord == ChordType.VI:
            root_offset = 9

        interval = 0
        if func == PitchFunc.THIRD_FIFTH:
            interval = 4 if random.random() < 0.5 else 7
        elif func == PitchFunc.COLOR:
            # simple random choice
            r = random.random()
            if r < 0.33:
                interval = 2
            elif r < 0.66:
                interval = 11
            else:
                interval = 14

        return 60 + root_offset + interval