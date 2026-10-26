"""One playback clock for the PC controller and read-only XR viewers.

This clock consumes the published replay; it never changes scheduling results.
Monotonic time drives playback. Wall time is only a timestamp for clients.
"""
import math
import threading
import time


class PlaybackConflict(Exception):
    pass


class UnityPlaybackClock:
    def __init__(self, replay_metadata, monotonic=time.monotonic, wall=time.time):
        self._metadata = replay_metadata
        self._now = monotonic
        self._wall = wall
        self._lock = threading.RLock()
        self.sim_id = ""
        self.publication_id = ''
        self.duration = 0.0
        self.minute = 0.0
        self.playing = False
        self.speed = 10.0
        self.anchor = self._now()
        self.revision = 0
        self.controller = ""
        self.lease_until = 0.0
        self.lease_seconds = 12.0

    def _refresh(self):
        metadata=self._metadata()
        sim_id, duration = metadata[:2]
        publication_id=metadata[2] if len(metadata)>2 else ''
        now = self._now()
        if sim_id != self.sim_id or publication_id!=self.publication_id:
            self.sim_id, self.duration = sim_id, max(0.0, float(duration))
            self.publication_id=publication_id
            self.minute, self.playing, self.anchor = 0.0, False, now
            self.controller, self.lease_until = '', 0.0
            self.revision += 1
        if self.controller and now >= self.lease_until:
            # Freeze at lease expiry, not at the time the next viewer polls.
            self.minute = self._value(self.lease_until)
            self.anchor, self.playing, self.controller = now, False, ""
            self.revision += 1

    def _value(self, now):
        return min(self.duration, max(0.0, self.minute +
                   (max(0.0, now - self.anchor) * self.speed if self.playing else 0)))

    def _snapshot(self):
        value = self._value(self._now())
        return dict(schema_version=1, sim_id=self.sim_id, minute=value,
                    playing=self.playing and value < self.duration,
                    speed=self.speed, duration=self.duration, revision=self.revision,
                    controller_id=self.controller, controller_connected=bool(self.controller),
                    server_unix_ms=self._wall() * 1000)

    def snapshot(self):
        with self._lock:
            self._refresh()
            return self._snapshot()

    def claim(self, client_id):
        if not client_id or len(client_id) > 100:
            raise ValueError("Invalid controller ID")
        with self._lock:
            self._refresh()
            if self.controller and self.controller != client_id:
                raise PlaybackConflict("Another PC controls playback")
            self.controller = client_id
            self.lease_until = self._now() + self.lease_seconds
            return self._snapshot()

    def control(self, client_id, sim_id, revision, minute=None, playing=None, speed=None):
        with self._lock:
            self._refresh()
            if self.controller != client_id or not self.controller:
                raise PlaybackConflict("Claim the playback controller first")
            if sim_id != self.sim_id or revision != self.revision:
                raise PlaybackConflict("Replay or playback changed; read the current state")
            for value in (minute, speed):
                if value is not None and not math.isfinite(value):
                    raise ValueError("Playback values must be finite")
            if minute is not None and not 0 <= minute <= self.duration:
                raise ValueError("Minute outside replay duration")
            if speed is not None and not 0.1 <= speed <= 1000:
                raise ValueError("Speed must be between 0.1 and 1000")
            now = self._now()
            if any(value is not None for value in (minute, playing, speed)):
                self.minute = self._value(now) if minute is None else minute
                self.anchor = now
                if playing is not None:
                    self.playing = playing
                if speed is not None:
                    self.speed = speed
                self.revision += 1
            self.lease_until = now + self.lease_seconds
            return self._snapshot()
