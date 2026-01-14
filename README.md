# Bayesian MIDI Performer
![demo_screen.svg](demo_screen.svg)

A real-time, generative MIDI performance tool driven by Bayesian Networks. This application listens to incoming drum triggers (kick, snare, rim), analyzes the musical context (density, velocity, bar position), and improvises a melodic accompaniment on the fly.

Built with **Textual** for a modern Terminal User Interface (TUI) and **pyAgrum** for probabilistic reasoning.

## 🚀 Features

* **Real-time TUI:** Interactive terminal interface with a visual metronome, live logs, and settings controls.
* **Generative AI:** Uses a Bayesian Network to make musical decisions based on input density and energy.
* **Optimized Performance:** Defaults to a "Baked" Bayesian engine that pre-calculates 512 probability states into a lookup table for zero-latency inference.
* **Low Latency Scheduler:** Custom threaded `MidiScheduler` ensures Note-On events are instant while managing Note-Offs asynchronously.
* **Benchmarking Tools:** Includes scripts to compare the performance of manual, dynamic, and baked inference engines.

## 🛠️ Installation

### Prerequisites

* **Python 3.8+**
* **MIDI Interface:** You will likely need a virtual MIDI loopback driver to route signals between this app and your DAW/Synth.
    * *Mac:* Use **IAC Driver** (Audio MIDI Setup).
    * *Windows:* Use **loopMIDI**.
    * *Linux:* ALSA sequencer usually handles this natively.

### Dependencies

Install the required Python packages:

```bash
pip install textual mido python-rtmidi pyagrum
```

* `textual`: For the TUI application.
* `mido` + `python-rtmidi`: For real-time MIDI input/output.
* `pyagrum`: For defining and baking the Bayesian Networks.

## 🎹 Usage

1. **Start the Application:**
```bash
python main.py
```

2. **Controls:**
* **Spacebar:** Start/Stop the Clock.
* **Tempo:** Adjust the BPM using the dropdown in the sidebar.
* **Mouse:** The TUI is fully clickable.


3. **MIDI Configuration:**
* Click the **Settings** button to open the modal.
* **MIDI Input:** Select the port connected to your drum pad or controller.
* **MIDI Output:** Select the port connected to your sound source (DAW/Synth).
* **Note Mapping:** Define which MIDI notes correspond to your Kick, Snare, and Rim.
* Click **Save & Close** or send a **Test Note** to verify the connection.



## 📂 Project Structure

### Core Application

* `main.py`: The entry point. Initializes the `BayesianMidiPerformer` app, `TempoEngine`, and processing loops.
* `ui_widgets.py` & `SettingsModal.py`: UI components for the metronome display and configuration screens.
* `tempo_engine.py`: Handles BPM calculations, tick generation, and bar counting.
* `MidiScheduler.py`: A thread-safe handler that sends Note-On messages immediately and schedules Note-Off messages via a priority queue.

### Bayesian Logic

* `bayesian/bayesian_network_ag_baked.py`: **(Default)** A high-performance wrapper that bakes `pyAgrum` logic into a dictionary for fast lookup.
* `bayesian/bayesian_network_ag.py`: The dynamic implementation using `pyAgrum`'s Variable Elimination.
* `bayesian/bayesian_network.py`: A legacy manual dictionary-based implementation.
* `bayesian_benchmark.py`: A script to run performance comparisons (latency, note counts) between the three implementation styles.

## ⚙️ Logic & Mappings

The system interprets inputs based on the `PerformanceSettings` class. By default:

* **Kick:** Note 60
* **Snare:** Note 65
* **Rim:** Note 67

The Bayesian Engine analyzes these inputs to infer:

1. **Density:** Sparse, Medium, or Busy.
2. **Energy:** Chill, Groove, or High.
3. **Output:** Decides whether to play, what chord tone to use, and which MIDI channel to route to.

## ⚠️ Troubleshooting

* **"Error" on Port Selection:** Ensure your MIDI device is connected *before* starting the script. If using `python-rtmidi` on Windows, ensure you have the necessary C++ build tools installed.
* **Audio Latency:** If the audio feels delayed, check the buffer size of your DAW or audio interface. The `MidiScheduler` is designed to send MIDI messages instantly upon decision.
* **Visual Lag:** The TUI updates via `call_from_thread` and might appear slightly behind the audio; this is intentional to prioritize audio timing over visual redraws.

```

```