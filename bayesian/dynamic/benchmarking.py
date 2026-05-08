import csv
import random
import os

from bayesian.dynamic.dynamic_bayesian_network import *


def run_large_simulation(network, iterations=1000):
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    filename = "bayesMIDI_benchmark.csv"
    name, extension = filename.split(".")
    new_filename = f"{name}_{timestamp}.{extension}"
    results_path = os.path.join("out", new_filename)
    os.makedirs("out", exist_ok=True)
    log_data = []

    print("Starting Simulation Runs...")

    for i in range(iterations):
        # Generate varied inputs
        in_d = random.choice(list(Density))
        in_v = random.choice(list(Velocity))

        # 1. Measure the 'Brain'
        inf_ms = network.tick(in_d, in_v, silent=True)

        # 2. Measure the 'Hands'
        res_start = time.perf_counter()
        midi_msgs = network.resolve_outputs(silent=True)
        res_ms = (time.perf_counter() - res_start) * 1000

        log_data.append({
            "beat": i,
            "inference_ms": inf_ms,
            "resolution_ms": res_ms,
            "total_ms": inf_ms + res_ms,
            "anchor": Anchor(network.memory["Past_Anchor"]).name,
            "voice_count": len(midi_msgs)
        })

    # Save to CSV for thesis analysis
    with open(results_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=log_data[0].keys())
        writer.writeheader()
        writer.writerows(log_data)

    print("Finished.")
    print("-" * 65)
    avg_inf = sum(d['inference_ms'] for d in log_data) / iterations
    avg_res = sum(d['resolution_ms'] for d in log_data) / iterations
    print(f"Averages -> Inference: {avg_inf:.4f}ms | Resolution: {avg_res:.4f}ms")

if __name__ == "__main__":
    network = DynamicBayesianNetwork()
    # Run a 1000-beat stress test (approx. 8 minutes of drumming at 120 BPM)
    run_large_simulation(network, iterations=10000)