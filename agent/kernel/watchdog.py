class Watchdog:
    def __init__(self, timeout_s, on_trip):
        self.timeout = timeout_s
        self.on_trip = on_trip
        self.last_kick = 0

    def kick(self, now):
        self.last_kick = now

    def check(self, now):
        if self.last_kick > 0 and now - self.last_kick > self.timeout:
            self.on_trip("watchdog_timeout")
            self.last_kick = now
