import time

class TempoEngine:
    def __init__(self, bpm=120, steps_per_beat=4):
        self.bpm = bpm
        self.steps_per_beat = steps_per_beat
        self.interval = (60.0 / self.bpm) / self.steps_per_beat
        self.last_tick_time = time.perf_counter()
        self.step_counter = 0

    def set_bpm(self, new_bpm):
        self.bpm = new_bpm
        self.interval = (60.0 / self.bpm) / self.steps_per_beat

    def check_tick(self):
        now = time.perf_counter()
        if now - self.last_tick_time >= self.interval:
            self.last_tick_time += self.interval
            self.step_counter += 1
            return True
        return False

    def reset(self):
        self.step_counter = 0
        self.last_tick_time = time.perf_counter()