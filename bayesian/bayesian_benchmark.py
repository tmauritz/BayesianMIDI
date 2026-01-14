import time
import random
import statistics
from collections import Counter

from bayesian.bayesian_network_ag_baked import BakedBayesianGenerator
# Import your implementations
# (Assumes classes are in the same file or imported correctly)
from bayesian_network import BayesianMusicGenerator, BayesianInput, DrumType
from bayesian_network_ag import BayesianMusicGeneratorAg


def generate_test_sequence(num_steps=1000):
    """Generates a random sequence of musical inputs."""
    inputs = []
    for _ in range(num_steps):
        inputs.append(BayesianInput(
            drum_type=random.choice(list(DrumType)),
            velocity=random.randint(40, 127),
            bar=random.randint(1, 4),
            step=random.randint(1, 16)
        ))
    return inputs


def run_benchmark(model_name, model_instance, inputs):
    print(f"--- Benchmarking: {model_name} ---")

    start_time = time.perf_counter()

    # Stats Collectors
    latencies = []
    play_counts = 0
    velocities = []
    channels = []

    for data in inputs:
        step_start = time.perf_counter()

        # --- THE CRITICAL CALL ---
        # Both models must accept exactly the same input object
        output = model_instance.infer(data)

        step_end = time.perf_counter()
        latencies.append((step_end - step_start) * 1000)  # Convert to ms

        # Collect Logic Stats
        if output.should_play:
            play_counts += 1
            velocities.append(output.velocity)
            channels.append(output.channel)

    total_time = time.perf_counter() - start_time

    # Calculate Metrics
    avg_latency = statistics.mean(latencies)
    max_latency = max(latencies)
    play_rate = (play_counts / len(inputs)) * 100
    avg_vel = statistics.mean(velocities) if velocities else 0

    print(f"Total Time:     {total_time:.4f}s")
    print(f"Avg Latency:    {avg_latency:.4f} ms per note")
    print(f"Max Latency:    {max_latency:.4f} ms")
    print(f"Notes Played:   {play_counts} ({play_rate:.1f}%)")
    print(f"Avg Velocity:   {avg_vel:.1f}")
    print(f"Channel Dist:   {dict(Counter(channels))}")
    print("-" * 30)

    return {
        "name": model_name,
        "avg_latency": avg_latency,
        "play_rate": play_rate
    }


def main():
    print("Initializing Models...")
    try:
        old_net = BayesianMusicGenerator()
        new_net = BayesianMusicGeneratorAg()
        baked_net = BakedBayesianGenerator()
    except Exception as e:
        print(f"Error initializing models: {e}")
        return

    # Generate 10,000 random musical events
    N = 10000
    print(f"Generating {N} random inputs...")
    test_data = generate_test_sequence(N)

    # Run Benchmarks
    results_old = run_benchmark("Manual Network", old_net, test_data)
    results_new = run_benchmark("pyAgrum Network", new_net, test_data)
    results_baked = run_benchmark("Baked pyAgrum Network", baked_net, test_data)

if __name__ == "__main__":
    main()