import mido
import time

def print_midi_message(msg):
    """
    This is your callback function.
    It will trigger every time a message arrives.
    """
    # We filter out 'active_sensing' because some gear sends it
    # every 300ms and it clutters the console.
    if msg.type != 'active_sensing':
        print(f"[{time.strftime('%H:%M:%S')}] {msg}")


def start_midi_monitor():
    # 1. List available ports so you can verify the SPD-SX name
    print("Available Inputs:", mido.get_input_names())

    port_name = mido.get_input_names()[1]  # Picks the first one, change as needed
    print(f"\n--- Opening: {port_name} ---")

    try:
        # 2. Open the input with the callback assigned
        inport = mido.open_input(port_name, callback=print_midi_message)

        # 3. DISABLE THE FILTER (The most important part)
        # We check both common mido attribute names for the backend object
        backend_object = getattr(inport, '_rt', getattr(inport, 'callback_port', None))

        if backend_object:
            # timing=False means "Do NOT ignore clock/start/stop"
            # active_sense=True means "DO ignore the keep-alive pulses"
            backend_object.ignore_types(timing=False, sysex=False, active_sense=True)
            print("Successfully unblocked MIDI Clock pulses.\n")
        else:
            print("Warning: Could not access backend filters. Clocks might be hidden.")

        print("Monitoring... Press Ctrl+C to stop.")

        # Keep the main thread alive while the callback runs in the background
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nClosing port and exiting...")
    finally:
        inport.close()


if __name__ == "__main__":
    start_midi_monitor()