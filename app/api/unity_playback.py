"""PC playback control and XR read-only clock endpoints."""
import json
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.core.unity_playback import UnityPlaybackClock, PlaybackConflict

router = APIRouter()
_replay_path = Path(os.getenv('SIMPY_REPLAY_PATH', str(Path(__file__).resolve().parents[2] / "results/unity_validation/replay.json")))
_cached_stamp = None
_cached_metadata = ("", 0.0)


def replay_metadata():
    global _cached_stamp, _cached_metadata
    try:
        stat = _replay_path.stat()
        stamp = (stat.st_mtime_ns, stat.st_size)
        if stamp != _cached_stamp:
            data = json.loads(_replay_path.read_text(encoding="utf-8-sig"))
            _cached_metadata = (data["sim_id"], float(data["duration"]))
            _cached_stamp = stamp
    except (OSError, ValueError, KeyError):
        pass  # Keep the last valid snapshot during an atomic publication.
    return _cached_metadata


clock = UnityPlaybackClock(replay_metadata)


class ControllerRequest(BaseModel):
    client_id: str


class ControlRequest(ControllerRequest):
    sim_id: str
    revision: int
    minute: Optional[float] = None
    playing: Optional[bool] = None
    speed: Optional[float] = None


@router.get("/playback.json")
def playback_state():
    return clock.snapshot()


@router.post("/playback/claim")
def claim_controller(request: ControllerRequest):
    try:
        return clock.claim(request.client_id)
    except PlaybackConflict as error:
        raise HTTPException(409, str(error))
    except ValueError as error:
        raise HTTPException(400, str(error))


@router.put("/playback")
def control_playback(request: ControlRequest):
    try:
        return clock.control(**request.model_dump())
    except PlaybackConflict as error:
        raise HTTPException(409, str(error))
    except ValueError as error:
        raise HTTPException(400, str(error))
