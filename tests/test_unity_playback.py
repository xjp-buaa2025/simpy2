import pytest
from app.core.unity_playback import UnityPlaybackClock, PlaybackConflict


@pytest.fixture
def setup_clock():
    now = [100.0]
    meta = ["run-a", 200.0]
    clock = UnityPlaybackClock(lambda: tuple(meta), lambda: now[0], lambda: now[0] + 1000)
    return clock, now, meta


def send(clock, **controls):
    state = clock.snapshot()
    return clock.control("pc", state["sim_id"], state["revision"], **controls)


def test_pause_speed_seek_and_completion(setup_clock):
    clock, now, _ = setup_clock
    clock.claim("pc")
    send(clock, minute=30, playing=True, speed=2)
    now[0] += 4
    assert clock.snapshot()["minute"] == 38
    send(clock, speed=10)
    now[0] += 2
    assert clock.snapshot()["minute"] == 58
    send(clock, playing=False)
    now[0] += 3
    assert clock.snapshot()["minute"] == 58
    send(clock, minute=195, playing=True)
    now[0] += 1
    assert clock.snapshot()["minute"] == 200
    assert not clock.snapshot()["playing"]
    send(clock, minute=0, playing=False)
    assert clock.snapshot()["minute"] == 0


def test_single_controller_read_only_viewer_and_lease(setup_clock):
    clock, now, _ = setup_clock
    clock.claim("pc")
    send(clock, playing=True, speed=2)
    with pytest.raises(PlaybackConflict):
        clock.claim("other-pc")
    state = clock.snapshot()
    with pytest.raises(PlaybackConflict):
        clock.control("vr", state["sim_id"], state["revision"], minute=10)
    now[0] += 20
    state = clock.snapshot()
    assert state["minute"] == 24  # Stops at the 12 second lease expiry.
    assert not state["controller_connected"] and not state["playing"]
    clock.claim("other-pc")


def test_new_replay_rejects_stale_controls(setup_clock):
    clock, now, meta = setup_clock
    state = clock.claim("pc")
    send(clock, minute=40, playing=True)
    meta[:] = ["run-b", 500.0]
    fresh = clock.snapshot()
    assert fresh["sim_id"] == "run-b" and fresh["minute"] == 0
    assert not fresh["playing"]
    with pytest.raises(PlaybackConflict):
        clock.control("pc", "run-a", state["revision"], minute=45)
    send(clock, playing=True)
    now[0] += 2
    assert clock.snapshot()["minute"] == 20


def test_nonfinite_and_out_of_range_rejected(setup_clock):
    clock, _, _ = setup_clock
    clock.claim("pc")
    for controls in ({"minute": float("nan")}, {"minute": -1}, {"minute": 201},
                     {"speed": float("inf")}, {"speed": 0}):
        with pytest.raises(ValueError):
            send(clock, **controls)
