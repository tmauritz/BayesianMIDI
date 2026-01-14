import threading
import heapq
import time
import mido


class MidiScheduler:
    def __init__(self):
        self._queue = []  # Min-heap for events: (timestamp, msg)
        self._condition = threading.Condition()  # For efficient sleeping
        self._active = True
        self.output_port = None

        # Start the single background worker
        self._worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self._worker_thread.start()

    def set_port(self, port):
        """Updates the output port immediately."""
        with self._condition:
            self.output_port = port

    def play_note(self, note, velocity, channel, duration):
        """
        1. Sends Note On INSTANTLY (Zero Latency).
        2. Schedules Note Off for later.
        """
        if not self.output_port:
            return

        # --- A. IMMEDIATE OUTPUT (The Latency Fix) ---
        # We send this right now. No worker, no queue, no waiting.
        # Note: Mido output is thread-safe on RtMidi backend.
        # Adjust channel (Mido is 0-15, your Logic is 1-16)
        msg_on = mido.Message('note_on', note=note, velocity=velocity, channel=channel - 1)
        self.output_port.send(msg_on)

        # --- B. SCHEDULE CLEANUP ---
        # Calculate when the note should end
        off_time = time.time() + duration
        msg_off = mido.Message('note_off', note=note, velocity=0, channel=channel - 1)

        with self._condition:
            # Add to priority queue
            heapq.heappush(self._queue, (off_time, msg_off))
            # Wake up the worker if this new note ends sooner than the current sleeper
            self._condition.notify()

    def _process_queue(self):
        """Single background thread that waits for the next Note Off."""
        while self._active:
            with self._condition:
                if not self._queue:
                    # Nothing to do? Sleep until a note is played.
                    self._condition.wait()
                else:
                    # Look at the earliest event
                    next_time, _ = self._queue[0]
                    now = time.time()

                    if next_time <= now:
                        # It's time! Pop and Send.
                        _, msg = heapq.heappop(self._queue)
                        if self.output_port:
                            self.output_port.send(msg)
                    else:
                        # Sleep exactly until the next event is due
                        self._condition.wait(timeout=next_time - now)

    def stop(self):
        self._active = False
        with self._condition:
            self._condition.notify()