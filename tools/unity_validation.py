"""Build and serve a UTF-8 replay snapshot from the currently exported process.

This adapter leaves the scheduling algorithm unchanged. AGV trips are presentation
tasks on a sequential demonstration timeline, not material availability constraints.
"""
import argparse
import csv
import functools
import hashlib
import json
import pathlib
import heapq
import logging
import os
import tempfile
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "unity_validation"
PLAYER_REPLAY = pathlib.Path("C:/AllUnityProjects/MainProject/MainProject/Assets/StreamingAssets/simpy_replay.json")
# Also protects success/failure markers written by the HTTP request handler.
publication_lock = threading.RLock()
SCENE_SOURCE = pathlib.Path("C:/AllUnityProjects/MainProject/MainProject/PlantSimulationImport/psfile_current")

# Plant Simulation's physical stations are finer grained than SimPy's areas.
# A few logical areas need an explicit display anchor in an adjacent physical area.
STATION_BINDINGS = {
    "ST01": ("工位1", "零部件预检与清洁", (0, 0)),
    "ST03": ("工位2", "轴流压气机装配", (0, 0)),
    "ST04": ("工位11221", "齿轮箱壳体组装", (0, 0)),
    "ST05": ("工位111", "涡轮盘与轴的安装定位", (0, 0)),
    "ST06": ("工位1121", "行星齿轮组装配", (0, 0)),
    "ST07": ("工位2211", "燃油系统总成工区", (0, 0)),
    "ST08": ("工位22111", "气动系统显示锚点", (-7, -4)),
    "ST09": ("工位221", "滑油系统显示锚点", (-8, -5)),
    "ST10": ("工位22111", "电气与控制系统显示锚点", (5, 0)),
    "ST11": ("工位22", "发动机总成装配工区", (0, 0)),
    "ST13": ("工位211111", "试车与终检显示锚点", (5, -4)),
}


def road_route(source, target, tracks, root):
    """Shortest centerline route through the 12 recovered Plant Simulation tracks."""
    a = (source["x"], source["z"])
    b = (target["x"], target["z"])
    lines = []
    for track in tracks:
        p = (track["start"][0] + root["x"], track["start"][2] + root["z"])
        q = (track["end"][0] + root["x"], track["end"][2] + root["z"])
        lines.append((p, q))
    points = [[p, q] for p, q in lines]
    def project(point, line):
        (x, z), (u, v) = line
        factor = max(0, min(1, ((point[0]-x)*(u-x)+(point[1]-z)*(v-z))/((u-x)**2+(v-z)**2)))
        return (x+factor*(u-x), z+factor*(v-z))
    attachments = []
    for point in (a, b):
        index = min(range(len(lines)), key=lambda i: sum((x-y)**2 for x, y in zip(project(point, lines[i]), point)))
        projected = project(point, lines[index]); points[index].append(projected); attachments.append(projected)
    for i, (p, q) in enumerate(lines):
        for j in range(i+1, len(lines)):
            r, s = lines[j]
            if abs(p[1]-q[1])<.01 and abs(r[0]-s[0])<.01:
                crossing = (r[0], p[1])
            elif abs(p[0]-q[0])<.01 and abs(r[1]-s[1])<.01:
                crossing = (p[0], r[1])
            else:
                continue
            if sum((x-y)**2 for x, y in zip(project(crossing,(p,q)),crossing))<2.25 and sum((x-y)**2 for x, y in zip(project(crossing,(r,s)),crossing))<2.25:
                points[i].append(crossing);points[j].append(crossing)
    def key(p):return (round(p[0],1),round(p[1],1))
    graph={}
    for line, vertices in zip(lines, points):
        vertices=sorted({key(v) for v in vertices},key=lambda v:(v[0]-line[0][0])**2+(v[1]-line[0][1])**2)
        for u,v in zip(vertices,vertices[1:]):
            cost=((u[0]-v[0])**2+(u[1]-v[1])**2)**.5
            graph.setdefault(u,[]).append((v,cost));graph.setdefault(v,[]).append((u,cost))
    origin,destination=map(key,attachments)
    queue=[(0,origin)];distance={origin:0};previous={}
    while queue:
        length,u=heapq.heappop(queue)
        if length>distance[u]:continue
        if u==destination:break
        for v,cost in graph.get(u,[]):
            if length+cost<distance.get(v,float("inf")):
                distance[v]=length+cost;previous[v]=u;heapq.heappush(queue,(length+cost,v))
    if destination not in distance:
        raise ValueError(f"No connected Plant Simulation track from {a} to {b}")
    path=[destination]
    while path[-1]!=origin:path.append(previous[path[-1]])
    path.reverse()
    route=[a]+path+[b]
    return [{"x":x,"y":-0.38,"z":z} for x,z in route]


def build(csv_path=None, *, result=None, rows=None):
    """Build and publish a standalone replay, including its ready marker."""
    with publication_lock:
        payload = _build(csv_path, result=result, rows=rows)
        _mark_ready(payload)
        return payload


def _build(csv_path=None, *, result=None, rows=None):
    if rows is None:
        rows = list(csv.DictReader(pathlib.Path(csv_path).read_text(encoding="utf-8-sig").splitlines()))
    nodes = {row["step_id"]: row for row in rows}
    assert len(nodes) == len(rows), "Duplicate process step IDs"
    if result is None:
        result = json.loads((OUTPUT / "current_result.json").read_text(encoding="utf-8"))["data"]
    events = []
    for index, event in enumerate(result["gantt_events"]):
        node = nodes[event["step_id"]]
        assert event["end_time"] >= event["start_time"]
        if event["event_type"] == "NORMAL":
            assert event["task_name"] == node["task_name"], "Result differs from current process"
        events.append(dict(event, event_id=str(index), station_id=node.get("workstation_id") or node["step_id"],
                           area_id=node.get("area_id") or node["station"]))
    events.sort(key=lambda e: (e["start_time"], e["end_time"], e["event_id"]))
    station_ids = sorted({row["station"] for row in rows})
    # Complete logical-area mapping for the current HelloUnity scene.
    scene = json.loads(pathlib.Path("C:/AllUnityProjects/MainProject/MainProject/SimPyValidation/scene_probe.json").read_text(encoding="utf-8"))
    objects = {obj["path"]: obj for obj in scene["objects"]}
    scene_nodes = {item["name"]:item for item in json.loads((SCENE_SOURCE/"objects.json").read_text(encoding="utf-8"))}
    mapping=json.loads((ROOT/"tools/factory_process_mapping.json").read_text(encoding="utf-8"))
    if set(mapping) != set(nodes):
        unbound = sorted(set(nodes)-set(mapping))
        absent = sorted(set(mapping)-set(nodes))
        raise ValueError("工序与 Unity 工位映射不一致；未绑定工序: " + (", ".join(unbound) or "无")
                         + "；场景对应但流程已缺少的工序: " + (", ".join(absent) or "无"))
    root=objects["psfile_PlantSimulation"]["position"]
    def factory_position(name):
        p=json.loads(scene_nodes[name]["Position"])
        return {"x":p[0]+root["x"],"y":p[2]+root["y"],"z":p[1]+root["z"]}
    stations = []
    for index, node in enumerate(rows):
        sid = node["step_id"]
        binding=mapping[sid]
        added=isinstance(binding,dict)
        name=binding["template"] if added else binding
        position=factory_position(binding["near"] if added else name)
        if added:position["x"]+=binding["offset"][0];position["z"]+=binding["offset"][1]
        path="psfile_PlantSimulation/"+name
        resource_station=result.get("config",{}).get("capacity_model",{}).get("workstations",{}).get(sid,{})
        effective_sid = node.get("workstation_id") or sid
        effective_station = result.get("resource_snapshot",{}).get("effective_workstations",{}).get(effective_sid,{})
        stations.append({"station_id": sid, "area_id":resource_station.get("area_id") or node.get("area_id") or node["station"], "scene_path": path, "scene_label": node["task_name"],
                         "capacity":effective_station.get("capacity",resource_station.get("capacity",1)),
                         "anchor_kind": "added_factory_equipment" if added else "existing_factory_equipment",
                         "position": position})
    locations={station["station_id"]:station["position"] for station in stations}
    root=objects["psfile_PlantSimulation"]["position"]
    tracks=json.loads((SCENE_SOURCE/"appearance_tracks.json").read_text(encoding="utf-8"))["tracks"]
    def display_route(source, target):
        return road_route(source,target,tracks,root)
    completed = {(e["engine_id"], e["step_id"]): e for e in events if e["event_type"] == "NORMAL"}
    transfers, seen = [], set()
    for event in events:
        if event["event_type"] != "NORMAL" or event["engine_id"] != 1:
            continue
        for predecessor in nodes[event["step_id"]]["predecessors"].split(";"):
            source = completed.get((1, predecessor.strip()))
            if not source or source["station_id"] == event["station_id"]:
                continue
            key = (predecessor, event["station_id"])
            if key in seen:
                continue
            seen.add(key)
            transfers.append({"source_station": source["station_id"], "target_station": event["station_id"],
                              "trigger_time": source["end_time"], "source_step": predecessor,
                              "target_step": event["step_id"], "engine_id": 1,
                              "route": display_route(locations[source["station_id"]],locations[event["station_id"]])})
    # Start with a visible empty drive from the AGV's saved scene position.
    # This avoids snapping the model to the first pickup station.
    agv_start={"x":8.011127471923828,"y":-0.3840000033378601,"z":4.330870628356934}
    schedule=[]
    available=0
    if transfers:
        first_source=min(transfers,key=lambda x:(x["trigger_time"],x["target_station"]))["source_station"]
        initial_route=display_route(agv_start,locations[first_source])
        schedule=[{"trip_id":"initial-empty","source_station":"AGV_START","target_station":first_source,
                   "source_step":"","target_step":"","engine_id":1,"loaded":False,
                   "trigger_time":0,"start_time":0,"end_time":20,"route":initial_route}]
        available=20
    previous_target=None
    for index, trip in enumerate(sorted(transfers, key=lambda x: (x["trigger_time"], x["target_station"]))):
        if previous_target and previous_target!=trip["source_station"]:
            empty_route=display_route(locations[previous_target],locations[trip["source_station"]])
            schedule.append({"trip_id":f"empty-{index}","source_station":previous_target,"target_station":trip["source_station"],
                             "source_step":"","target_step":"","engine_id":1,"loaded":False,
                             "trigger_time":available,"start_time":available,"end_time":available+20,"route":empty_route})
            available+=20
        trip["trip_id"] = f"loaded-{index}"
        trip["loaded"]=True
        trip["start_time"] = max(available, trip["trigger_time"])
        trip["end_time"] = trip["start_time"] + 20
        available = trip["end_time"]
        schedule.append(trip)
        previous_target=trip["target_station"]
    config=result["config"]
    hours=config["work_hours_per_day"]
    days=config["work_days_per_month"]
    horizon=hours*60*days
    authority = {int(e["engine_id"]): e["end_time"] for e in result.get("engine_completion_events", [])}
    has_authority = "engine_completion_events" in result
    engine_completion=[]
    for engine_id in sorted({e["engine_id"] for e in events}):
        own=[e for e in events if e["engine_id"]==engine_id and e["event_type"] in ("NORMAL","REWORK")]
        def milestone(step):
            return max((e["end_time"] for e in own if e["step_id"]==step and e["event_type"]=="NORMAL"),default=-1)
        covered={e["step_id"] for e in own if e["event_type"]=="NORMAL"}
        finished = authority.get(engine_id, -1) if has_authority else (max((e["end_time"] for e in own),default=-1) if covered==set(nodes) else -1)
        engine_completion.append({"engine_id":engine_id,"assembly":milestone("A005"),"inspection":milestone("Q003"),"finished":finished})
    actual=sum(e["finished"]>=0 and e["finished"]<=horizon for e in engine_completion)
    if actual!=result["engines_completed"]:
        raise ValueError(f"Engine completion differs from scheduler: {actual} vs {result['engines_completed']}")
    payload = {"schema_version": 3, "sim_id": result["sim_id"], "time_unit": "minute",
               "duration": horizon, "work_hours_per_day":hours,"work_days_per_month":days,
               "engines_completed":result["engines_completed"],
               "engine_completion":engine_completion,"stations": stations,
               "events": events, "transfers": schedule,
               "station_constraint_mode": config["station_constraint_mode"],
               "area_stats":result.get("area_stats",[]),
               "area_completion_events":result.get("area_completion_events",[]),
               "evaluation_context":result.get("evaluation_context",{}),
               "resource_snapshot":result.get("resource_snapshot",{}),
               "agv_mode": "presentation_only", "source_scene": scene["scene"]}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    atomic_write(OUTPUT / "replay.json",encoded)
    import io
    csv_stream=io.StringIO()
    csv_writer=csv.DictWriter(csv_stream,fieldnames=list(rows[0]))
    csv_writer.writeheader()
    for row in rows:
        csv_row = dict(row)
        tools = csv_row.get("required_tools", [])
        if isinstance(tools, list):
            csv_row["required_tools"] = ";".join(tools)
        csv_writer.writerow(csv_row)
    atomic_write(OUTPUT / "current_process.csv",csv_stream.getvalue().encode("utf-8-sig"))
    with (OUTPUT/"process_station_mapping.csv").open("w",encoding="utf-8-sig",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=["station_id","area_id","scene_label","scene_path","capacity","anchor_kind","position"])
        writer.writeheader();writer.writerows(stations)
    audit = {"sim_id": result["sim_id"], "nodes": len(nodes), "events": len(events),
             "stations": len(stations), "mapped_stations": len(stations), "loaded_transfers":len(transfers),
             "empty_returns":len(schedule)-len(transfers), "demo_transfers":len(schedule),
             "utf8_replacement_characters": encoded.decode("utf-8").count("\ufffd"),
             "sha256": hashlib.sha256(encoded).hexdigest(), "bytes": len(encoded)}
    (OUTPUT / "adapter_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit), flush=True)
    return payload


def _mark_ready(payload):
    atomic_write(OUTPUT / "sync_status.json", json.dumps(
        {"success": True, "sim_id": payload["sim_id"], "message": "ready"},
        ensure_ascii=False).encode("utf-8"))


def atomic_write(path, content):
    """Replace a complete snapshot, tolerating brief Windows reader locks."""
    path = pathlib.Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = pathlib.Path(stream.name)
            stream.write(content)
        for attempt in range(21):
            try:
                os.replace(temporary, path)
                return
            except OSError as error:
                if getattr(error, "winerror", None) not in (5, 32, 33) or attempt == 20:
                    raise
                time.sleep(0.1)
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                logging.getLogger(__name__).warning(
                    "Could not remove publication temporary file %s", temporary, exc_info=True)


def supports_legacy_replay(process):
    """Only the exact legacy process can address the old Unity scene."""
    mapping = json.loads((ROOT / "tools/factory_process_mapping.json").read_text(encoding="utf-8"))
    return {node.step_id for node in process.nodes} == set(mapping)


def publish_result(result, process):
    """Publish one web run without interleaving files from another publication."""
    with publication_lock:
        rows = [node.model_dump(mode="json") for node in process.nodes]
        progress = result.get("station_progress")
        progress_url = "/api/simulation/unity/station-progress.json"
        if progress is not None:
            # The PT6A29 scene uses WS-* station IDs. It does not consume the
            # old 79-step replay or its shared playback clock.
            mapping = json.loads((ROOT / "tools/factory_process_mapping.json").read_text(encoding="utf-8"))
            if {row.get("step_id") for row in rows} != set(mapping):
                atomic_write(OUTPUT / "station_progress.json", json.dumps(
                    progress, ensure_ascii=False, allow_nan=False).encode("utf-8"))
                return {"success": True, "sim_id": result["sim_id"],
                        "mode": "station_progress_only", "legacy_replay_published": False,
                        "station_progress_url": progress_url,
                        "stations": len(progress["stations"]),
                        "engines_completed": result["engines_completed"]}
        payload = _build(result=result, rows=rows)
        atomic_write(OUTPUT / "current_result.json", json.dumps(
            {"success": True, "data": result}, ensure_ascii=False).encode("utf-8"))
        if PLAYER_REPLAY.parent.exists():
            atomic_write(PLAYER_REPLAY, json.dumps(
                payload, ensure_ascii=False, indent=2).encode("utf-8"))
        if progress is not None:
            atomic_write(OUTPUT / "station_progress.json", json.dumps(
                progress, ensure_ascii=False, allow_nan=False).encode("utf-8"))
        _mark_ready(payload)
        return {"success": True, "sim_id": payload["sim_id"],
                "mode": "legacy_replay", "legacy_replay_published": True,
                **({"station_progress_url": progress_url} if progress is not None else {}),
                "stations": len(payload["stations"]), "engines_completed": payload["engines_completed"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=18765)
    args = parser.parse_args()
    if args.csv:
        build(args.csv)
    if args.serve:
        handler = functools.partial(SimpleHTTPRequestHandler, directory=str(OUTPUT))
        server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
        print(f"Unity replay: http://127.0.0.1:{args.port}/replay.json", flush=True)
        server.serve_forever()
