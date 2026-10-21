"""Author the original-runtime PT6A physical profile without editing the replay.

The bindings below are display placement decisions, not verified process mappings.
Original machine recipes are shared by physical slot; no scheduling capacity follows
from the number of meshes or slots.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import heapq
import json
import math
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'data/factory_layout/pt6a29-original'
ORIGIN_X, ORIGIN_Z = -40.2682724, 32.8180294
AUXILIARY = {'S001', 'S002', 'S003', 'S004', 'Q003', 'Q004'}
ALIASES = {
    'G01': ['P002'], 'G03': ['A001', 'P041', 'P042'],
    'G04': ['A002', 'A003', 'A004'], 'M05': ['A005'],
    'TC01': ['A006', 'A007', 'Q001', 'Q002'],
    'R01': ['P001', 'P003', 'P004', 'P012', 'P013', 'P061', 'P062'],
    'S01': ['P011'], 'C01': ['P021', 'P022', 'P031', 'P032'],
    'GB1': ['G001', 'G002', 'G011', 'G012', 'G013', 'G014', 'G021', 'G022', 'G023', 'G031', 'G032', 'G041', 'G051', 'G052'],
    'T01': ['D001', 'D002', 'D003', 'D004', 'D021', 'D031', 'D041', 'P051'],
    'T02': ['D011', 'D012', 'D013', 'D022', 'D042', 'P052'],
    'AGB01': ['F003', 'F004', 'F011', 'F012', 'F013', 'F021', 'F031', 'F051'],
    'AGB02': ['F001', 'F002', 'F032', 'F041', 'F052', 'F061', 'F062'],
    'FU01': ['B001'], 'FU02': ['B002'], 'OL01': ['B011'],
    'AC01': ['B021'], 'P08': ['B031'], 'PR01': ['B041'],
}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def world(u, v):
    return round(ORIGIN_X + u, 7), round(ORIGIN_Z - v, 7)


def point(x, z):
    return dict(x=round(x, 7), y=-.38, z=round(z, 7))


@lru_cache(maxsize=1)
def original_rows():
    return {s['station_id']:s for s in read(ROOT/'data/factory_layout/default.json')['stations']}


def auxiliary_bounds(profile):
    source=original_rows()
    result=[]
    for row in profile['auxiliary']:
        original=source[row['step_id']];yaw=math.radians(original['yaw']);w=original['base_width']
        # Include the retained original contact shadows conservatively as well
        # as the actual original equipment footprint.
        width=max(original['size_x'],w*(1.12*abs(math.cos(yaw))+.85*abs(math.sin(yaw))))
        depth=max(original['size_z'],w*(1.12*abs(math.sin(yaw))+.85*abs(math.cos(yaw))))
        result.append(dict(step_id=row['step_id'],x=row['x'],z=row['z'],width=width,depth=depth,yaw=row['yaw']))
    return result


def retained_bounds(profile):
    result=[dict(id=b['step_id'],kind='legacy_auxiliary',y=1.25,height=2.5,**b) for b in auxiliary_bounds(profile)]
    for i,item in enumerate(read(ROOT/'data/factory_layout/environment.json')['obstacles']):
        xs,zs=zip(*item['polygon']);kind='storage' if '货架' in item['name'] else 'fixture'
        result.append(dict(id=f'original-fixed-{i:02}',kind=kind,x=(min(xs)+max(xs))/2,z=(min(zs)+max(zs))/2,
                           width=max(xs)-min(xs),depth=max(zs)-min(zs),y=2 if kind=='storage' else 1.5,height=4 if kind=='storage' else 3))
    for i in range(5):
        result.append(dict(id=f'original-product-stage-{i+1}',kind='product_display',x=22+14*i,z=-43,width=10,depth=7,y=1.5,height=3))
    # Bounds measured from BrightFactory/Poles and Shell_10.asset, including
    # the actual nonuniform parent scale and the 90-degree end columns.
    for xlocal in [-29.5,-20,-5,5,20,29.5]:
        for side in [-1,1]:
            end=abs(xlocal)==29.5
            x=-5.268276+4*xlocal+(-.14738524 if xlocal>0 else .14738524) if end else -5.268276+4*xlocal
            z=8.818026+side*30+(0 if end else side*.11053893)
            result.append(dict(id=f'original-column-{xlocal}-{side}',kind='factory_column',x=x,z=z,
                               width=4.2947712 if end else 4.6689104,depth=3.5016828 if end else 3.2210784,y=8.3523953,height=18))
    for u in [4.6,14.7,24.2,33.8,44.2,54.4]:
        for v in [21.2,27.8]:
            x,z=world(u,v)
            result.append(dict(id=f'gantry-column-{u}-{v}',kind='gantry_column',x=x,z=z,width=.38,depth=.38,y=2.8,height=5.6))
    for item in result:
        item.setdefault('step_id','');item.setdefault('yaw',0)
    return result


def clear_of_auxiliary(a,b,profile,margin=0):
    for box in profile.get('obstacles') or retained_bounds(profile):
        n=max(1,math.ceil(math.dist(a,b)/.12))
        for i in range(n+1):
            x=a[0]+(b[0]-a[0])*i/n;z=a[1]+(b[1]-a[1])*i/n
            if math.hypot(max(abs(x-box['x'])-box['width']/2,0),max(abs(z-box['z'])-box['depth']/2,0)) < profile['agv_radius']+margin-1e-5:
                return False
    return True


def idle_models(code):
    if code in {'G01', 'G02', 'G03', 'G04', 'M05'}:
        return ['assembly_repair', 'worktable_repair']
    if code == 'CL01':
        return ['washer_none', 'worktable_repair']
    if code == 'TC01':
        return ['hot_test_repair', 'inspection_inspection']
    if code in {'FU04', 'OL04', 'AC01', 'P08'}:
        return ['worktable_worktable', 'inspection_inspection']
    if code in {'FU01', 'FU02', 'FU03', 'OL01', 'OL02', 'PR01', 'PR02'}:
        return ['worktable_repair', 'inspection_inspection']
    return ['assembly_repair', 'worktable_repair']


def dock_for(z):
    u, v, w, d = (z[k] for k in ['u', 'v', 'width', 'depth'])
    if z['station_id'] == 'ST-B':
        du, dv, yaw = u - 1.4, v + d / 2, 90
    elif z['station_id'] == 'ST-C':
        du, dv, yaw = u + w / 2, v + d + 1.4, 0
    elif z['station_id'] == 'ST-A':
        du, dv, yaw = u + w / 2, v + d + 1.45, 0
    elif z['station_id'] in {'WS-TC01', 'WS-CL01'}:
        du, dv, yaw = u - 1.45, (29.5 if z['station_id'] == 'WS-TC01' else v + d / 2), 90
    elif v == 10.5 or v == 38:
        du, dv, yaw = u + w / 2, v + d + 1.4, 0
    else:
        du, dv, yaw = u + w / 2, v - 1.4, 180
    x, zz = world(du, dv)
    return dict(u=du, v=dv, x=x, z=zz, yaw=yaw)


def pack(recipes, width, depth):
    """Exact small rectangle packing with an explicit operator strip per recipe.

    The smallest original instance of each recipe is retained at its original
    uniform size. Both headings are tried. The 0.7 m working strip is part of
    the packed rectangle, rather than an after-the-fact worker offset.
    """
    margin, gap, operator = .10, .10, .7
    order = sorted(recipes, key=lambda r: (-r['size_x'] * r['size_z'], r['model_key']))
    placed = []

    def solve(i):
        if i == len(order):
            return True
        r = order[i]
        # Original equipment operates on its local +Z face. For the first
        # orientation that is diagram-down (world -Z); for a quarter-turn
        # the working strip is on the right, not incorrectly below the model.
        candidates = [(r['size_x'], r['size_z']+operator,r['size_x'],r['size_z'],180),
                      (r['size_z']+operator,r['size_x'],r['size_z'],r['size_x'],90)]
        xs = sorted({margin, *(p[0] + p[2] + gap for p in placed)})
        ys = sorted({margin, *(p[1] + p[3] + gap for p in placed)})
        for y in ys:
            for x in xs:
                for w, h, body_w, body_d, yaw in candidates:
                    if x + w > width - margin + 1e-6 or y + h > depth - margin + 1e-6:
                        continue
                    if any(x < a + c + gap - 1e-6 and x + w + gap > a + 1e-6 and y < b + e + gap - 1e-6 and y + h + gap > b + 1e-6 for a, b, c, e, *_ in placed):
                        continue
                    placed.append((x, y, w, h, body_w, body_d, yaw, r))
                    if solve(i + 1):
                        return True
                    placed.pop()
        return False

    if not solve(0):
        raise ValueError(f'Cannot pack original recipes into {width} x {depth}: {[r["model_key"] for r in recipes]}')
    return placed


def build_profile():
    source = read(ROOT / 'data/factory_layout/pt6a29/layout.json')
    legacy = read(ROOT / 'data/factory_layout/default.json')
    by_id = {r['station_id']: r for r in legacy['stations']}
    representative = {}
    for r in legacy['stations']:
        if r['model_key'] == 'gantry':
            continue
        old = representative.get(r['model_key'])
        if old is None or (r['size_x'] * r['size_z'], r['station_id']) < (old['size_x'] * old['size_z'], old['station_id']):
            representative[r['model_key']] = r
    # Standard original recipes, never preview/cooked models.
    zones, slots, bindings = [], [], []
    for raw in source['zones']:
        z = {k: raw[k] for k in ['station_id', 'label', 'u', 'v', 'width', 'depth', 'kind']}
        z['x'], z['z'] = world(z['u'] + z['width'] / 2, z['v'] + z['depth'] / 2)
        z['dock'] = dock_for(z)
        zones.append(z)
        if z['kind'] != 'workstation':
            continue
        code = z['station_id'][3:]
        assigned = ALIASES.get(code, [])
        models = {('assembly_repair' if step == 'A001' else by_id[step]['model_key']) for step in assigned}
        if len(models) < 2:
            models.update(idle_models(code))
        recipes = [copy.deepcopy(representative[k]) for k in sorted(models)]
        for recipe in recipes:
            recipe['source_base_width'] = recipe['base_width']
            # The large rotor test table is an original 4.4 m presentation
            # instance; retain its complete recipe and proportions at the
            # same 2.8 m nominal bench width as the neighbouring recipes.
            if recipe['model_key'] == 'rotor_repair':
                factor = 2.8 / recipe['base_width']
                recipe['size_x'] *= factor; recipe['size_z'] *= factor
                recipe['base_width'] = 2.8
        placement = pack(recipes, z['width'], z['depth'])
        model_slots = {}
        for i, (u, v, working_w, h, w, d, yaw, recipe) in enumerate(placement, 1):
            x, zz = world(z['u'] + u + w / 2, z['v'] + v + d / 2)
            ox, oz = world(z['u'] + u + w / 2, z['v'] + v + d + .35) if yaw==180 else world(z['u']+u+w+.35,z['v']+v+d/2)
            sid = f'{z["station_id"]}:{i:02}'
            slots.append(dict(id=sid, zone_id=z['station_id'], model_key=recipe['model_key'],
                              representative_id=recipe['station_id'], x=x, z=zz, yaw=yaw,
                              width=w, depth=d, base_width=recipe['base_width'], scale=1,
                              source_base_width=recipe['source_base_width'],
                              operator_x=ox, operator_z=oz, operator_yaw=(yaw+180)%360,
                              working_width=working_w, working_depth=h, source_yaw=recipe['yaw'],
                              binding_kind='display_placement_only'))
            model_slots[recipe['model_key']] = sid
        for step in assigned:
            model = 'assembly_repair' if step == 'A001' else by_id[step]['model_key']
            bindings.append(dict(step_id=step, zone_id=z['station_id'], slot_id=model_slots[model],
                                 status='display_placement_not_verified_process_mapping'))
    auxiliary = [dict(step_id=s, x=by_id[s]['x'], z=by_id[s]['z'], yaw=by_id[s]['yaw'], model_key=by_id[s]['model_key']) for s in sorted(AUXILIARY)]
    assert {b['step_id'] for b in bindings} | AUXILIARY == set(by_id)
    profile = dict(schema_version=1, profile_id='pt6a29-original', layout_id='pt6a29-original',
                   catalog_version='pt6a29-original-1', revision=0, units='metres',
                   mode='original_runtime_physical_layout', width=70, depth=48,
                   origin_x=ORIGIN_X, origin_z=ORIGIN_Z,
                   mapping_status='display_placement_only_formal_process_mapping_pending',
                   original_layout_sha256=hashlib.sha256((ROOT / 'data/factory_layout/default.json').read_bytes()).hexdigest(),
                   zones=zones, slots=slots, bindings=sorted(bindings, key=lambda b: b['step_id']), auxiliary=auxiliary,
                   models=legacy['models'], agv_radius=1.15, road_width=3.0,
                   agv_start=point(*world(2.25, 19)),
                   gantry=dict(u_min=4.5, u_max=54.5, v_a=21.2, v_b=27.8, rail_height=6,
                               x_min=world(4.5, 0)[0], x_max=world(54.5, 0)[0],
                               z_a=world(0, 21.2)[1], z_b=world(0, 27.8)[1],
                               zones=['WS-G01', 'WS-G02', 'WS-G03', 'WS-G04', 'WS-M05']))
    profile['obstacles']=retained_bounds(profile)
    profile['roads'] = build_roads(profile)
    return profile


def build_roads(profile):
    segments = []

    def add(a, b, kind='production'):
        if math.dist(a, b) < 1e-5:
            return
        segments.append(dict(id=f'road-{len(segments):03}', x1=round(a[0], 7), z1=round(a[1], 7),
                             x2=round(b[0], 7), z2=round(b[1], 7), width=3.0, kind=kind))

    for v, end in [(2, 68.5), (19, 68.5), (29.5, 61.5), (46, 61.5)]:
        add(world(2.25, v), world(end, v))
    for u, a, b in [(2.25, 2, 46), (26, 2, 19), (47.5, 2, 19), (24, 29.5, 46), (45, 29.5, 46), (61.5, 19, 46)]:
        add(world(u, a), world(u, b))
    # Retain only old roads outside the production rectangle, with a safety
    # margin. Old lines that cut through the new workstations are not used.
    env = read(ROOT / 'data/factory_layout/environment.json')
    bounds = (ORIGIN_X - 1.4, ORIGIN_X + 71.4, ORIGIN_Z - 49.4, ORIGIN_Z + 1.4)
    for a, b in env['lines']:
        if abs(a[1] - b[1]) < 1e-5:
            lo, hi = sorted([a[0], b[0]])
            if bounds[2] < a[1] < bounds[3]:
                for left, right in [(lo, min(hi, bounds[0])), (max(lo, bounds[1]), hi)]:
                    if right > left:
                        add((left, a[1]), (right, a[1]), 'original_auxiliary')
            else:
                add(a, b, 'original_auxiliary')
        else:
            lo, hi = sorted([a[1], b[1]])
            if bounds[0] < a[0] < bounds[1]:
                for low, high in [(lo, min(hi, bounds[2])), (max(lo, bounds[3]), hi)]:
                    if high > low:
                        add((a[0], low), (a[0], high), 'original_auxiliary')
            else:
                add(a, b, 'original_auxiliary')
    # The original imported centre lines have 0.5--1 m gaps at a few end
    # junctions. Join those outside the production rectangle explicitly.
    old = [e for e in segments if e['kind'] == 'original_auxiliary']
    for e in old:
        for p in [(e['x1'], e['z1']), (e['x2'], e['z2'])]:
            for other in old:
                if other is e:
                    continue
                q = project(p, other)
                if 1e-5 < math.dist(p, q) <= 1.05:
                    add(p, q, 'original_junction')
    # Two explicit bridges to the retained network. Both remain outside all
    # physical zones. No synthetic shortcut crosses the production rectangle.
    west = world(2.25, 19)
    add(west, (ORIGIN_X - 3.5, west[1]), 'connector')
    add((ORIGIN_X - 3.5, west[1]), (ORIGIN_X - 3.5, 8.400001525878906), 'connector')
    bottom = world(61.5, 46)
    add(bottom, (bottom[0], ORIGIN_Z - 51), 'connector')
    add((bottom[0], ORIGIN_Z - 51), (17.699996948242188, ORIGIN_Z - 51), 'connector')
    add((-106.3,-34),(96.7,-34),'retained_display_bypass')
    docks = {}
    for z in profile['zones']:
        d = z['dock']
        if z['station_id'] == 'ST-B':
            junction = world(47.5, d['v'])
        elif z['station_id'] in {'WS-TC01', 'WS-CL01'}:
            junction = world(61.5, d['v'])
        else:
            road_v = min([2, 19, 29.5, 46], key=lambda v: abs(v - d['v']))
            junction = world(d['u'], road_v)
        add((d['x'], d['z']), junction, 'dock')
        docks[z['station_id']] = (d['x'], d['z'])
    # The old replay ended at several auxiliary machine centres. Keep those
    # machines in place, but move only AGV docking points outside their bounds.
    obstacles=profile['obstacles']
    padded=[]
    for box in obstacles:
        xmin,xmax=box['x']-box['width']/2-1.4,box['x']+box['width']/2+1.4
        zmin,zmax=box['z']-box['depth']/2-1.4,box['z']+box['depth']/2+1.4
        padded.append((xmin,xmax,zmin,zmax))
    def intersects_edge(edge,box):
        xmin,xmax,zmin,zmax=box
        a,b=(edge['x1'],edge['z1']),(edge['x2'],edge['z2'])
        return ((abs(a[1]-b[1])<1e-5 and zmin+1e-6<a[1]<zmax-1e-6 and min(a[0],b[0])<xmax and max(a[0],b[0])>xmin) or
                (abs(a[0]-b[0])<1e-5 and xmin+1e-6<a[0]<xmax-1e-6 and min(a[1],b[1])<zmax and max(a[1],b[1])>zmin))
    relevant={i for i,b in enumerate(padded) if any(intersects_edge(e,b) for e in segments)}
    while True:
        more={i for i,a in enumerate(padded) if i not in relevant and any(a[0]<padded[j][1] and a[1]>padded[j][0] and a[2]<padded[j][3] and a[3]>padded[j][2] for j in relevant)}
        if not more:break
        relevant.update(more)
    for i in sorted(relevant):
        xmin,xmax,zmin,zmax=padded[i];corners=[(xmin,zmin),(xmax,zmin),(xmax,zmax),(xmin,zmax)]
        for a,b in zip(corners,corners[1:]+corners[:1]):add(a,b,'retained_obstacle_bypass')
    # Clip every perimeter against every obstacle. Adding perimeters while
    # clipping would reintroduce paths inside an overlapping neighbour.
    for xmin,xmax,zmin,zmax in padded:
        previous=segments[:];segments.clear()
        for edge in previous:
            a,b=(edge['x1'],edge['z1']),(edge['x2'],edge['z2'])
            if abs(a[1]-b[1])<1e-5 and zmin+1e-6<a[1]<zmax-1e-6:
                lo,hi=sorted([a[0],b[0]])
                if lo<xmax and hi>xmin:
                    if lo<xmin:add((lo,a[1]),(xmin,a[1]),edge['kind'])
                    if hi>xmax:add((xmax,a[1]),(hi,a[1]),edge['kind'])
                    continue
            if abs(a[0]-b[0])<1e-5 and xmin+1e-6<a[0]<xmax-1e-6:
                lo,hi=sorted([a[1],b[1]])
                if lo<zmax and hi>zmin:
                    if lo<zmin:add((a[0],lo),(a[0],zmin),edge['kind'])
                    if hi>zmax:add((a[0],zmax),(a[0],hi),edge['kind'])
                    continue
            add(a,b,edge['kind'])
    for box in auxiliary_bounds(profile):
        yaw=math.radians(box['yaw']);direction=(math.sin(yaw),math.cos(yaw))
        half=abs(direction[0])*box['width']/2+abs(direction[1])*box['depth']/2
        p=(round(box['x']+direction[0]*(half+1.4),7),round(box['z']+direction[1]*(half+1.4),7))
        candidates=sorted(segments,key=lambda e:math.dist(p,project(p,e)))
        for edge in candidates:
            q=project(p,edge)
            paths=[[p,(p[0],q[1]),q],[p,(q[0],p[1]),q]]
            if math.dist(p,q)<1e-5:paths=[[p,(edge['x1'],edge['z1'])],[p,(edge['x2'],edge['z2'])]]
            path=next((path for path in paths if all(clear_of_auxiliary(a,b,profile) for a,b in zip(path,path[1:]))),None)
            if path is not None:
                for a,b in zip(path,path[1:]):add(a,b,'auxiliary_dock')
                docks[box['step_id']]=p;break
        else:raise ValueError('No safe auxiliary dock for '+box['step_id'])
    graph, nodes, edges = graph_from_segments(segments)
    return dict(segments=segments, nodes=[dict(id=f'n{i}', x=p[0], z=p[1]) for i, p in enumerate(nodes)],
                edges=[dict(a=f'n{a}', b=f'n{b}', distance=w) for a, b, w in edges],
                docks=[dict(station_id=s, x=p[0], z=p[1]) for s, p in sorted(docks.items())])


def project(p, e):
    a, b = (e['x1'], e['z1']), (e['x2'], e['z2'])
    dx, dz = b[0] - a[0], b[1] - a[1]
    f = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / (dx * dx + dz * dz)))
    return a[0] + f * dx, a[1] + f * dz


def graph_from_segments(segments):
    points = [set([(e['x1'], e['z1']), (e['x2'], e['z2'])]) for e in segments]
    for i, a in enumerate(segments):
        for j, b in enumerate(segments[:i]):
            ah = abs(a['z1'] - a['z2']) < 1e-5
            bh = abs(b['z1'] - b['z2']) < 1e-5
            if ah != bh:
                h, v = (a, b) if ah else (b, a)
                p = (v['x1'], h['z1'])
                if min(h['x1'], h['x2']) - 1e-5 <= p[0] <= max(h['x1'], h['x2']) + 1e-5 and min(v['z1'], v['z2']) - 1e-5 <= p[1] <= max(v['z1'], v['z2']) + 1e-5:
                    points[i].add(p); points[j].add(p)
            else:
                for p in list(points[i]) + list(points[j]):
                    if math.dist(project(p, a), p) < 1e-5 and math.dist(project(p, b), p) < 1e-5:
                        points[i].add(p); points[j].add(p)
    def key(p): return round(p[0], 5), round(p[1], 5)
    nodes = sorted({key(p) for group in points for p in group})
    indexes = {p: i for i, p in enumerate(nodes)}
    graph, edges = {p: [] for p in nodes}, []
    for group in points:
        row = sorted({key(p) for p in group})
        for a, b in zip(row, row[1:]):
            distance = math.dist(a, b)
            graph[a].append((b, distance)); graph[b].append((a, distance))
            edges.append((indexes[a], indexes[b], distance))
    return graph, nodes, edges


def shortest(graph, a, b):
    start = min(graph, key=lambda p: math.dist(p, a))
    goal = min(graph, key=lambda p: math.dist(p, b))
    if math.dist(start, a) > .001 or math.dist(goal, b) > .001:
        raise ValueError(f'Unconnected endpoint {a}, {b}')
    queue, cost, previous = [(0, start)], {start: 0}, {}
    while queue:
        distance, current = heapq.heappop(queue)
        if current == goal:
            path = [goal]
            while path[-1] != start:
                path.append(previous[path[-1]])
            return list(reversed(path))
        if distance != cost[current]:
            continue
        for nxt, weight in graph[current]:
            candidate = distance + weight
            if candidate < cost.get(nxt, float('inf')):
                cost[nxt] = candidate; previous[nxt] = current
                heapq.heappush(queue, (candidate, nxt))
    raise ValueError(f'No connected route from {a} to {b}')


def rounded_path(path, profile):
    """Round long orthogonal bends, retaining stop-turn corners on short docks."""
    if len(path) < 3:
        return path
    result = [path[0]]
    radius = 1.5
    for a, b, c in zip(path, path[1:], path[2:]):
        la, lb = math.dist(a, b), math.dist(b, c)
        if min(la, lb) < radius * 2 + .05:
            result.append(b); continue
        incoming = ((b[0]-a[0])/la, (b[1]-a[1])/la)
        outgoing = ((c[0]-b[0])/lb, (c[1]-b[1])/lb)
        dot = incoming[0]*outgoing[0] + incoming[1]*outgoing[1]
        cross = incoming[0]*outgoing[1] - incoming[1]*outgoing[0]
        if abs(dot) > .001 or abs(cross) < .999:
            result.append(b); continue
        start = (b[0]-incoming[0]*radius, b[1]-incoming[1]*radius)
        center = (start[0]+outgoing[0]*radius, start[1]+outgoing[1]*radius)
        angle = math.atan2(start[1]-center[1], start[0]-center[0])
        arc = [(center[0]+radius*math.cos(angle+cross*math.pi*.5*i/18),
                center[1]+radius*math.sin(angle+cross*math.pi*.5*i/18)) for i in range(19)]
        clear = True
        for x,z in arc:
            for zone in profile['zones']:
                left,top=world(zone['u'],zone['v']);right,bottom=world(zone['u']+zone['width'],zone['v']+zone['depth'])
                if math.hypot(max(left-x,0,x-right),max(bottom-z,0,z-top)) < profile['agv_radius']+.015:
                    clear=False;break
            if not clear:break
        if clear:clear=all(clear_of_auxiliary(p,p,profile,.015) for p in arc)
        result.extend(arc if clear else [b])
    result.append(path[-1])
    return [p for i,p in enumerate(result) if i==0 or math.dist(p,result[i-1])>.00001]


def reroutes(profile, replay):
    graph, _, _ = graph_from_segments(profile['roads']['segments'])
    docks = {d['station_id']: (d['x'], d['z']) for d in profile['roads']['docks']}
    aliases = {b['step_id']: b['zone_id'] for b in profile['bindings']}
    docks.update({s: docks[z] for s, z in aliases.items()})
    docks['AGV_START'] = (profile['agv_start']['x'], profile['agv_start']['z'])
    result = []
    for i, trip in enumerate(replay['transfers']):
        source, target = trip['source_station'], trip['target_station']
        if source not in docks or target not in docks:
            raise ValueError(f'Transfer endpoint has no physical binding: {source}, {target}')
        internal = aliases.get(source, source) == aliases.get(target, target)
        path = [docks[source], docks[target]] if internal else rounded_path(shortest(graph, docks[source], docks[target]), profile)
        if len(path) == 1:
            path.append(path[0])
        result.append(dict(trip_id=trip.get('trip_id', str(i)), trip_index=i,
                           source_station=source, target_station=target,
                           source_zone=aliases.get(source, source), target_zone=aliases.get(target, target),
                           internal_transfer=internal, points=[point(*p) for p in path],
                           distance=round(sum(math.dist(a, b) for a, b in zip(path, path[1:])), 6),
                           corner_mode='round_long_turns_stop_on_short_dock', corner_radius=1.5))
    return result


def author():
    profile = build_profile()
    replay = read(ROOT / 'results/unity_validation/replay.json')
    profile['sim_id'] = replay['sim_id']
    profile['replay_sha256'] = hashlib.sha256((ROOT / 'results/unity_validation/replay.json').read_bytes()).hexdigest()
    profile['reroutes'] = reroutes(profile, replay)
    write(DEST / 'layout.json', profile)
    write(DEST / 'display_placement.json', dict(status=profile['mapping_status'], bindings=profile['bindings'], slots=profile['slots'], auxiliary=profile['auxiliary']))
    source = ROOT / 'data/factory_layout/pt6a29/process_sources.json'
    if source.exists():
        (DEST / 'process_sources.json').write_bytes(source.read_bytes())
    return profile


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    result = author()
    print(json.dumps(dict(profile_id=result['profile_id'], zones=len(result['zones']), slots=len(result['slots']), bindings=len(result['bindings']), routes=len(result['reroutes'])), ensure_ascii=False))
