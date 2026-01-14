import pyAgrum as gum
import random
from bayesian.bayesian_network_helpers import *

# Assumes you have your Enums/Dataclasses imported:
# from my_music_types import DrumType, DensityLevel, EnergyLevel, ChordType, BeatType, PitchFunc, BayesianInput, BayesianOutput

class BayesianMusicGeneratorAg:
    def __init__(self):
        # 1. Build Network
        self.bn = self._build_network()

        # 2. Optimization: Use Variable Elimination (Faster for small queries)
        self.ie = gum.VariableElimination(self.bn)

        # 3. Optimization: Cache Node IDs (Avoids string lookup overhead)
        self.id_bar = self.bn.idFromName('Bar')
        self.id_drum = self.bn.idFromName('Drum_Type')
        self.id_vel = self.bn.idFromName('In_Velocity')
        self.id_beat = self.bn.idFromName('Beat_Type')

        self.id_density = self.bn.idFromName('Density')
        self.id_energy = self.bn.idFromName('Energy')
        self.id_chord = self.bn.idFromName('Chord')

        self.id_play = self.bn.idFromName('Play_Note')
        self.id_pitch = self.bn.idFromName('Pitch_Func')
        self.id_channel = self.bn.idFromName('Out_Channel')  # <--- Added Back

    def _build_network(self):
        bn = gum.BayesNet("DrumGenie_Final")

        # --- NODES ---
        bar = bn.add(gum.LabelizedVariable('Bar', 'Bar Number', 4))
        drum = bn.add(gum.LabelizedVariable('Drum_Type', 'Instrument', 4))
        in_vel = bn.add(gum.LabelizedVariable('In_Velocity', 'Input Vel', 2))
        beat_type = bn.add(gum.LabelizedVariable('Beat_Type', 'Rhythmic Context', 3))

        density = bn.add(gum.LabelizedVariable('Density', 'Note Density', 3))
        energy = bn.add(gum.LabelizedVariable('Energy', 'Musical Energy', 3))
        chord = bn.add(gum.LabelizedVariable('Chord', 'Current Chord', 4))

        play = bn.add(gum.LabelizedVariable('Play_Note', 'Gate', 2))
        pitch_func = bn.add(gum.LabelizedVariable('Pitch_Func', 'Pitch Strategy', 3))

        # NEW: Output Channel Node
        # 0:Ch1(Bass), 1:Ch2(Backing), 2:Ch3(Lead)
        channel = bn.add(gum.LabelizedVariable('Out_Channel', 'MIDI Channel', 3))

        # --- ARCS ---
        for link in [(bar, density), (drum, density),
                     (in_vel, energy), (density, energy),
                     (bar, chord),
                     (drum, play), (density, play), (beat_type, play),
                     (chord, pitch_func), (beat_type, pitch_func),
                     # NEW: Channel depends on Drum and Bar
                     (drum, channel), (bar, channel)]:
            bn.addArc(*link)

        # --- FILL CPTs ---

        # 1. DENSITY (48 cells)
        bn.cpt(density).fillWith([0.33, 0.33, 0.34] * 16)

        def set_density(b_start, b_end, d_enum, dist):
            arr = [dist.get(DensityLevel.SPARSE, 0), dist.get(DensityLevel.MEDIUM, 0), dist.get(DensityLevel.BUSY, 0)]
            for b in range(b_start, b_end + 1):
                bn.cpt(density)[{'Bar': b - 1, 'Drum_Type': int(d_enum)}] = arr

        set_density(1, 3, DrumType.KICK,
                    {DensityLevel.SPARSE: 0.80, DensityLevel.MEDIUM: 0.15, DensityLevel.BUSY: 0.05})
        set_density(1, 3, DrumType.SNARE,
                    {DensityLevel.SPARSE: 0.20, DensityLevel.MEDIUM: 0.70, DensityLevel.BUSY: 0.10})
        set_density(1, 3, DrumType.RIM, {DensityLevel.SPARSE: 0.10, DensityLevel.MEDIUM: 0.40, DensityLevel.BUSY: 0.50})
        set_density(4, 4, DrumType.KICK,
                    {DensityLevel.SPARSE: 0.40, DensityLevel.MEDIUM: 0.40, DensityLevel.BUSY: 0.20})
        set_density(4, 4, DrumType.SNARE,
                    {DensityLevel.SPARSE: 0.05, DensityLevel.MEDIUM: 0.25, DensityLevel.BUSY: 0.70})
        set_density(4, 4, DrumType.RIM, {DensityLevel.SPARSE: 0.05, DensityLevel.MEDIUM: 0.25, DensityLevel.BUSY: 0.70})

        # 2. ENERGY (18 cells)
        bn.cpt(energy).fillWith([0.33, 0.33, 0.34] * 6)

        def set_energy(is_loud, dens_enum, dist):
            arr = [dist.get(EnergyLevel.CHILL, 0), dist.get(EnergyLevel.GROOVE, 0), dist.get(EnergyLevel.HIGH, 0)]
            bn.cpt(energy)[{'In_Velocity': 1 if is_loud else 0, 'Density': int(dens_enum)}] = arr

        set_energy(False, DensityLevel.SPARSE, {EnergyLevel.CHILL: 0.95, EnergyLevel.GROOVE: 0.05})
        set_energy(False, DensityLevel.BUSY, {EnergyLevel.CHILL: 0.60, EnergyLevel.GROOVE: 0.40})
        set_energy(False, DensityLevel.MEDIUM, {EnergyLevel.CHILL: 0.80, EnergyLevel.GROOVE: 0.20})
        set_energy(True, DensityLevel.SPARSE,
                   {EnergyLevel.CHILL: 0.20, EnergyLevel.GROOVE: 0.70, EnergyLevel.HIGH: 0.10})
        set_energy(True, DensityLevel.MEDIUM,
                   {EnergyLevel.CHILL: 0.05, EnergyLevel.GROOVE: 0.50, EnergyLevel.HIGH: 0.45})
        set_energy(True, DensityLevel.BUSY, {EnergyLevel.CHILL: 0.00, EnergyLevel.GROOVE: 0.10, EnergyLevel.HIGH: 0.90})

        # 3. CHORD (4 rows * 4 values = 16 cells)
        bn.cpt(chord).fillWith([0.25, 0.25, 0.25, 0.25] * 4)

        def set_chord(bar_num, dist):
            arr = [dist.get(ChordType.I, 0), dist.get(ChordType.IV, 0), dist.get(ChordType.V, 0),
                   dist.get(ChordType.VI, 0)]
            bn.cpt(chord)[{'Bar': bar_num - 1}] = arr

        set_chord(1, {ChordType.I: 0.95, ChordType.V: 0.05})
        set_chord(2, {ChordType.I: 0.10, ChordType.IV: 0.80, ChordType.V: 0.05, ChordType.VI: 0.05})
        set_chord(3, {ChordType.I: 0.90, ChordType.IV: 0.05, ChordType.V: 0.05})
        set_chord(4, {ChordType.I: 0.05, ChordType.IV: 0.05, ChordType.V: 0.85, ChordType.VI: 0.05})

        # 4. PLAY GATE
        # We use the loop logic here as it's cleaner than fillWith for complex conditionals
        for d_type in [DrumType.NONE, DrumType.KICK, DrumType.SNARE, DrumType.RIM]:
            for b_type in [BeatType.DOWNBEAT, BeatType.OFFBEAT, BeatType.SUBDIVISION]:
                for dens in [DensityLevel.SPARSE, DensityLevel.MEDIUM, DensityLevel.BUSY]:
                    p_play = 0.0
                    if d_type == DrumType.NONE:
                        p_play = 0.0
                    elif d_type == DrumType.KICK and b_type == BeatType.DOWNBEAT:
                        p_play = 0.99
                    else:
                        p_play = 0.2 if dens == DensityLevel.SPARSE else 0.8
                    bn.cpt(play)[{'Drum_Type': int(d_type), 'Beat_Type': int(b_type), 'Density': int(dens)}] = [
                        1.0 - p_play, p_play]

        # 5. PITCH FUNC (36 cells)
        bn.cpt(pitch_func).fillWith([0.30, 0.40, 0.30] * 12)
        c_map = {ChordType.I: 0, ChordType.IV: 1, ChordType.V: 2, ChordType.VI: 3}
        bn.cpt(pitch_func)[{'Chord': c_map[ChordType.I], 'Beat_Type': int(BeatType.DOWNBEAT)}] = [0.80, 0.15, 0.05]
        bn.cpt(pitch_func)[{'Chord': c_map[ChordType.I], 'Beat_Type': int(BeatType.OFFBEAT)}] = [0.20, 0.60, 0.20]
        bn.cpt(pitch_func)[{'Chord': c_map[ChordType.V], 'Beat_Type': int(BeatType.DOWNBEAT)}] = [0.50, 0.30, 0.20]

        # 6. OUTPUT CHANNEL (NEW)
        # Size: 4(Drum) * 4(Bar) * 3(Channel) = 48 cells
        bn.cpt(channel).fillWith([1, 0, 0] * 16)  # Initialize Default to Ch1

        # Kick (1) -> Always Ch1 (Bass)
        # Rim (3) -> Always Ch3 (Lead)
        # None (0) -> Don't care
        for b in range(4):
            bn.cpt(channel)[{'Bar': b, 'Drum_Type': int(DrumType.KICK)}] = [1.0, 0.0, 0.0]
            bn.cpt(channel)[{'Bar': b, 'Drum_Type': int(DrumType.RIM)}] = [0.0, 0.0, 1.0]

        # Snare (2) Logic
        # Bar 1-3 (Indices 0, 1, 2)
        for b in [0, 1, 2]:
            bn.cpt(channel)[{'Bar': b, 'Drum_Type': int(DrumType.SNARE)}] = [0.0, 0.90, 0.10]  # Mostly Ch2

        # Bar 4 (Index 3)
        bn.cpt(channel)[{'Bar': 3, 'Drum_Type': int(DrumType.SNARE)}] = [0.0, 0.40, 0.60]  # More Ch3

        return bn

    def infer(self, data: BayesianInput) -> BayesianOutput:
        # --- Pre-calc Context ---
        is_downbeat = (data.step % 4 == 1)
        is_offbeat = (data.step % 2 == 1) and not is_downbeat

        if is_downbeat:
            b_enum = BeatType.DOWNBEAT
        elif is_offbeat:
            b_enum = BeatType.OFFBEAT
        else:
            b_enum = BeatType.SUBDIVISION

        vel_idx = 1 if data.velocity > 90 else 0

        # --- Set Evidence (Using Cached IDs) ---
        self.ie.setEvidence({
            self.id_bar: data.bar - 1,
            self.id_drum: int(data.drum_type),
            self.id_vel: vel_idx,
            self.id_beat: int(b_enum)
        })

        # --- 1. Gate Check (Optimization) ---
        play_dist = self.ie.posterior(self.id_play).tolist()
        should_play = random.choices([False, True], weights=play_dist)[0]

        if not should_play:
            return BayesianOutput(False, 0, 0, 0, 0, "Rest")

        # --- 2. Sample Latent & Output Nodes ---

        # CHANNEL
        chan_dist = self.ie.posterior(self.id_channel).tolist()
        channel_idx = random.choices([0, 1, 2], weights=chan_dist)[0]
        final_channel = channel_idx + 1  # Convert 0-2 to MIDI 1-3

        # PITCH FUNC
        pf_dist = self.ie.posterior(self.id_pitch).tolist()
        pf_val = random.choices(list(PitchFunc), weights=pf_dist)[0]

        # CHORD (Needed for Pitch Math)
        c_dist = self.ie.posterior(self.id_chord).tolist()
        c_enums = [ChordType.I, ChordType.IV, ChordType.V, ChordType.VI]
        current_chord = random.choices(c_enums, weights=c_dist)[0]

        # ENERGY (Needed for Velocity Math)
        e_dist = self.ie.posterior(self.id_energy).tolist()
        current_energy = random.choices(list(EnergyLevel), weights=e_dist)[0]

        # --- 3. Post-Processing ---
        energy_mult = 1.2 if current_energy == EnergyLevel.HIGH else 0.9
        final_velocity = int(data.velocity * energy_mult)
        if final_velocity > 127: final_velocity = 127

        final_pitch = self._resolve_pitch(current_chord, pf_val)

        return BayesianOutput(
            should_play=True,
            midi_note=final_pitch,
            velocity=final_velocity,
            duration=0.5,
            channel=final_channel,
            debug_info=f"{current_chord.name} -> {pf_val.name}"
        )

    def _resolve_pitch(self, chord: ChordType, func: PitchFunc) -> int:
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
            r = random.random()
            if r < 0.33:
                interval = 2
            elif r < 0.66:
                interval = 11
            else:
                interval = 14

        return 60 + root_offset + interval