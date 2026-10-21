"""Thread-safe, short-lived run progress; independent from simulation results."""
from threading import RLock
from time import monotonic


class RunProgressStore:
    def __init__(self):
        self.records = {}
        self.lock = RLock()

    def start(self, run_id):
        with self.lock:
            now = monotonic()
            self.records = {key: value for key, value in self.records.items()
                            if value["status"] == "running" or now - value["updated"] < 900}
            if run_id in self.records:
                raise ValueError("进度编号已使用，请重新提交")
            self.records[run_id] = dict(status="running", percent=1, phase="准备仿真",
                                        stage="prepare", started=now, updated=now,
                                        simulation_minute=0, total_minutes=0)

    def update(self, run_id, percent, phase, stage, **details):
        if not run_id:
            return
        with self.lock:
            record = self.records.get(run_id)
            if not record or record["status"] != "running":
                return
            record.update(details, percent=max(record["percent"], min(100, percent)),
                          phase=phase, stage=stage, updated=monotonic())

    def finish(self, run_id, success, message=""):
        if not run_id:
            return
        with self.lock:
            record = self.records.get(run_id)
            if record:
                record.update(status="completed" if success else "failed",
                              phase="仿真计算完成" if success else message or "仿真失败",
                              stage="complete" if success else "failed", updated=monotonic())
                if success:
                    record["percent"] = 100

    def snapshot(self, run_id):
        with self.lock:
            record = self.records.get(run_id)
            if not record or (record["status"] != "running" and monotonic() - record["updated"] >= 900):
                return None
            return {key: value for key, value in record.items() if key not in ("started", "updated")} | {
                "elapsed_seconds": round(monotonic() - record["started"], 1)}


run_progress = RunProgressStore()


def attach_progress_observer(engine):
    """Observe model time without sampling randomness or changing any resources."""
    callback = getattr(engine, "progress_callback", None)
    if callback is None:
        return
    horizon = engine.config.sim_time_minutes
    if horizon <= 0:
        return

    def observe():
        for step in range(101):
            callback(min(engine.env.now / horizon, 1), engine.env.now, horizon)
            yield engine.env.timeout(horizon / 100)

    engine.env.process(observe())
