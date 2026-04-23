import csv
import random
import os

from bayesian.dynamic.dynamic_bayesian_network import *


def run_large_simulation(network, iterations=1000):
    """
    Simulates a large number of beats with varied input to test
    the system's long-term stability and performance.
    """
    results_path = os.path.join("out", "simulation_results.csv")
    os.makedirs("out", exist_ok=True)

    # Prepare data for logging
    log_data = []

    print(f"Starting simulation of {iterations} beats...")

    for i in range(iterations):
        # 1. Generate randomized musical input
        # Bias toward MEDIUM/HIGH to test tension, or LOW to test decay
        in_density = random.choices([Density.LOW, Density.MEDIUM, Density.HIGH], weights=[0.2, 0.5, 0.3])[0]
        in_velocity = random.choices([Velocity.LOW, Velocity.MEDIUM, Velocity.HIGH], weights=[0.2, 0.5, 0.3])[0]

        # 2. Run Inference and capture performance
        # Note: Set override_active to True occasionally to test pad triggers
        is_override = (random.random() < 0.05)

        start_time = time.perf_counter()
        ms = network.tick(in_density, in_velocity, override_active=is_override)

        # 3. Log the state results
        log_data.append({
            "beat": i,
            "latency_ms": ms,
            "input_density": in_density.name,
            "input_velocity": in_velocity.name,
            "anchor": Anchor(network.memory["Past_Anchor"]).name,
            "tension": Tension(network.memory["Past_Tension"]).name,
            "momentum": Momentum(network.memory["Past_Momentum"]).name
        })

    # 4. Write to CSV
    keys = log_data[0].keys()
    with open(results_path, 'w', newline='') as output_file:
        dict_writer = csv.DictWriter(output_file, fieldnames=keys)
        dict_writer.writeheader()
        dict_writer.writerows(log_data)

    print(f"Simulation complete. Data saved to {results_path}")


if __name__ == "__main__":
    network = DynamicBayesianNetwork()
    # Run a 1000-beat stress test (approx. 8 minutes of drumming at 120 BPM)
    run_large_simulation(network, iterations=10000)