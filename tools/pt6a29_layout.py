"""Author the isolated PT6A29 preview and its source index; never touches simulation state."""
from __future__ import annotations

import argparse
import collections
import hashlib
import heapq
import json
import math
from pathlib import Path
import posixpath
import re
import shutil
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path('C:/AllUnityProjects/MainProject/MainProject')
SOURCE = Path('C:/Users/Administrator/Downloads/PT6A27航空发动机工艺流程表.xlsx')
DEST = ROOT / 'data/factory_layout/pt6a29'
EVIDENCE = ROOT / 'results/pt6a29_20261020'
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
GEOMETRY = [
    ('S01',4.5,4,9,6),('GB1',14,4,10,6),('AGB02',28,4,8,6),('PR01',36.5,4,9,6),
    ('ST-B',49.5,4,3.5,12.5),('FU04',53.5,4,8,6),('FU02',62,4,8,6),
    ('R01',4.5,10.5,10,6),('C01',15,10.5,9,6),('AGB01',28,10.5,9,6),('PR02',37.5,10.5,8,6),
    ('FU01',53.5,10.5,9,6),('FU03',63,10.5,7,6),
    ('G01',4.5,21.5,10,6),('G02',15,21.5,9,6),('G03',24.5,21.5,9,6),('G04',34,21.5,10,6),('M05',44.5,21.5,10,6),
    ('ST-A',55,21.5,4,6),('TC01',64,21.5,6,15),
    ('IN01',4.5,31.5,8,6),('T01',13,31.5,9,6),('OL04',26,31.5,8.5,6),('OL03',35,31.5,8,6),('AC01',47,31.5,7.5,6),
    ('ST-C',55,31.5,4,12.5),('IN02',4.5,38,8,6),('T02',13,38,9,6),('OL01',26,38,8.5,6),('OL02',35,38,8,6),('P08',47,38,7.5,6),('CL01',64,37,6,7),
]
NAMES = dict(zip(
    'G01 G02 G03 G04 M05 TC01 CL01 R01 S01 P08 IN01 C01 IN02 GB1 T01 T02 AGB01 AGB02 FU01 FU02 FU03 FU04 OL01 OL02 OL03 OL04 PR01 PR02 AC01 ST-A ST-B ST-C'.split(),
    ['转子-壳体合装','进气机匣对接','燃烧室对接','动力段总装对接','整机点火 / T5装配','试车台地面运转测试','整机清洗与交付',
     '压气机转子部装','壳体静子预装','点火 / T5线束','进气机匣预装','燃烧室本体部装','进气段本体部装','行星减速器部装','动力涡轮转子部装','排气管与定子预装',
     'AGB内部齿轮组','AGB箱体合箱','FCU燃油控制单元','燃油泵与加热器','燃油功能阀组','燃油歧管与喷嘴','滑油泵组','油液阀件','油池壳体及内部组件','滑油冷却器与管路','螺旋桨调速器','反推连杆操纵机构','空气循环冷却系统',
     '整机暂存','燃油组件缓存','滑油 / 冷却 / 线束缓存']))


def sid(code):
    return code if code.startswith(('WS-', 'ST-')) else 'WS-' + code


def normalized(value):
    return re.sub(r'[\u2010-\u2015\u2212\x1e]', '-', re.sub(r'_x001[eE]_', '-', str(value))).strip()


def read_workbook(path):
    """Read source cells only, including sheets whose header does not begin on row one."""
    with zipfile.ZipFile(path) as z:
        strings = [''.join(e.itertext()) for e in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        rels = {r.attrib['Id']: posixpath.normpath('xl/' + r.attrib['Target']) for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        sheets = {}
        for sheet in ET.fromstring(z.read('xl/workbook.xml')).find('s:sheets', NS):
            rows = []
            rid = sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
            for row in ET.fromstring(z.read(rels[rid])).findall('s:sheetData/s:row', NS):
                values = {}
                for cell in row.findall('s:c', NS):
                    v = cell.find('s:v', NS)
                    value = v.text if v is not None else ''
                    if cell.attrib.get('t') == 's' and value:
                        value = strings[int(value)]
                    elif cell.attrib.get('t') == 'inlineStr':
                        value = ''.join(cell.find('s:is', NS).itertext())
                    if value:
                        values[re.sub(r'\d', '', cell.attrib['r'])] = value
                if values:
                    rows.append((int(row.attrib['r']), values))
            sheets[sheet.attrib['name']] = rows
    return sheets


def source_index(sheets):
    stations, records = {}, []
    for name, rows in sheets.items():
        station_id = normalized(name)
        if not station_id.startswith('WS-'):
            continue
        header = next((n for n, r in rows if r.get('A') == '工位编号' and '工步' in r.get('B', '')), None)
        assert header is not None, name
        stations[station_id] = dict(station_id=station_id, source_sheet=name, header_row=header)
        for number, r in rows:
            if number <= header or not r.get('B') or normalized(r.get('A', '')) != station_id:
                continue
            records.append(dict(source_id=f'{station_id}:{number}', workstation_id=station_id,
                                source_sheet=name, source_row=number, original_step=r['B'],
                                step_name=r.get('C', ''), person=r.get('D', ''), behavior=r.get('E', ''),
                                description=r.get('F', ''), duration_raw=r.get('G', ''),
                                sequencing_raw=r.get('H', ''), bottleneck_raw=r.get('I', ''),
                                scheduling_status='source_only'))
    assert len(stations) == 29, len(stations)
    return dict(schema_version=1, source=str(SOURCE), source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                status='source_index_not_an_executable_process', stations=list(stations.values()), steps=records,
                legacy_process_mapping=[dict(step_id=code, status='pending', workstation_id='')
                                        for code in json.loads((ROOT/'tools/factory_process_mapping.json').read_text(encoding='utf-8'))])


def fixtures(code, width, depth):
    rows = []
    def add(model, x, v, yaw=0, role='equipment'):
        rows.append(dict(instance_id=f'{sid(code)}:{len(rows)+1:02}', model=model, x=x, v=v, yaw=yaw, role=role))
    if code.startswith('ST-'):
        # Narrow stores use two longitudinal shelves and discrete pallet bays.
        add('rack', -width/2+.5, -depth/2+1.7, 90)
        add('rack', -width/2+.5, depth/2-1.7, 90)
        add('pallet', .45, 0, 0, 'buffer')
        if depth > 8:
            add('pallet', .45, -2.6, 0, 'buffer'); add('pallet', .45, 2.6, 0, 'buffer')
    elif code in {'G01','G02','G03','G04','M05'}:
        add('assembly', 0, .1); add('worktable', -2.7, -1.9); add('worktable', 2.7, -1.9)
        add('cabinet', width/2-.65, .3); add('handoff', -width/2+.85, 1.85, role='handoff')
        if code == 'G04': add('worktable', 2.7, 1.9)
        if code == 'M05': add('inspection', 2.1, 1.85)
    elif code in {'R01','S01','IN01','IN02','C01','GB1','T01','T02','AGB02','OL03'}:
        add('support', -.25, 0); add('worktable', -2.15, -1.9); add('worktable', 2.15, -1.9)
        add('cart', -width/2+.8, 1.8, role='handoff')
        if code in {'R01','T01'}: add('balance', 2.3, .75)
    elif code in {'AGB01','FU01','FU02','FU03','OL01','OL02','PR01','PR02'}:
        add('worktable', -1.65, -1.9); add('worktable', 1.65, -1.9)
        add('inspection', 1.7, .75); add('cabinet', -width/2+.65, 1.1)
        if code == 'AGB01': add('press', -.2, .6)
    elif code in {'FU04','OL04','AC01','P08'}:
        add('worktable', -1.75, -1.9); add('worktable', 1.75, -1.9)
        add('inspection', 2.1, 1.4); add('harness' if code == 'P08' else 'pipe', -1.5, .7)
    elif code == 'TC01':
        add('teststand', 0, 0); add('console', -1.6, -5.3); add('utilities', 1.9, 4.5)
    elif code == 'CL01':
        add('wash', -.2, -.2); add('tank', 1.8, 1.8); add('cart', -1.85, 2.2)
    return rows


def dock(code, u, v, w, d):
    if code in {'TC01', 'CL01'}: return u-1.45, v+d/2, 90
    if code == 'ST-A': return u+w+1.45, v+d/2, 270
    if code == 'M05': return u+w/2, v-1.45, 180
    if code == 'ST-C': return u+w+1.2, v+d/2, 270
    if code == 'ST-B': return u-1.2, v+d/2, 90
    if v in (4, 31.5): return u+w/2, v-1.2, 180
    if v in (10.5, 38): return u+w/2, v+d+1.2, 0
    return u+w/2, v-1.2, 180


def distance_to_rect(u, v, r):
    return math.hypot(max(r['u']-u, 0, u-r['u']-r['width']), max(r['v']-v, 0, v-r['v']-r['depth']))


def safe_point(p, zones, posts, radius=1.1):
    u,v = p
    if min(u, v, 70-u, 48-v) < radius - 1e-5: return False
    if any(distance_to_rect(u,v,r) < radius-1e-5 for r in zones): return False
    return all(math.hypot(max(abs(u-a)-.275,0),max(abs(v-b)-.275,0)) >= radius-1e-5 for a,b in posts)


def points_on(a,b,step=.1):
    n=max(1,math.ceil(math.dist(a,b)/step))
    return [(a[0]+(b[0]-a[0])*i/n,a[1]+(b[1]-a[1])*i/n) for i in range(n+1)]


def routing(roads, ports, zones, posts):
    graph=collections.defaultdict(dict)
    splits=[{tuple(r[0]),tuple(r[1])} for r in roads]
    def project(p,r):
        a,b=r; dv=(b[0]-a[0], b[1]-a[1]);t=max(0,min(1,((p[0]-a[0])*dv[0]+(p[1]-a[1])*dv[1])/(dv[0]**2+dv[1]**2)))
        return round(a[0]+t*dv[0],5),round(a[1]+t*dv[1],5)
    for i,r in enumerate(roads):
        for j,s in enumerate(roads[:i]):
            p=(r[0][0],s[0][1]) if r[0][0]==r[1][0] else (s[0][0],r[0][1])
            if project(p,r)==p and project(p,s)==p: splits[i].add(p);splits[j].add(p)
    attachments={}
    for name,p in ports.items():
        options=[]
        for i,r in enumerate(roads):
            q=project(p,r)
            if all(safe_point(x,zones,posts) for x in points_on(p,q)):
                options.append((math.dist(p,q),i,q))
        assert options, ('no approach', name, p)
        _,i,q=min(options);splits[i].add(q);attachments[name]=(tuple(p),q)
    def connect(a,b):
        if a==b:return
        assert all(safe_point(p,zones,posts) for p in points_on(a,b)), (a,b)
        graph[a][b]=graph[b][a]=math.dist(a,b)
    for r, vertices in zip(roads,splits):
        ordered=sorted(vertices,key=lambda p:math.dist(p,r[0]))
        for a,b in zip(ordered,ordered[1:]): connect(a,b)
    for p,q in attachments.values(): connect(p,q)
    def route(a,b,radius=1.1):
        start,end=attachments[a][0],attachments[b][0]
        queue=[(0,start)];dist={start:0};previous={}
        while queue:
            cost,p=heapq.heappop(queue)
            if cost>dist[p]:continue
            if p==end:break
            for q,d in graph[p].items():
                if cost+d<dist.get(q,math.inf): dist[q]=cost+d;previous[q]=p;heapq.heappush(queue,(cost+d,q))
        assert end in dist, (a,b)
        result=[end]
        while result[-1]!=start:result.append(previous[result[-1]])
        result.reverse()
        # Remove graph subdivisions along the same line before rounding turns.
        compact=[]
        for p in result:
            while len(compact)>1:
                x,y=compact[-2:]
                if abs((y[0]-x[0])*(p[1]-y[1])-(y[1]-x[1])*(p[0]-y[0]))>1e-5:break
                compact.pop()
            compact.append(p)
        rounded=[compact[0]]
        for a,p,b in zip(compact,compact[1:],compact[2:]):
            da,db=math.dist(a,p),math.dist(p,b);turn_radius=1.5
            if min(da,db)>=3.01:
                x=((a[0]-p[0])/da,(a[1]-p[1])/da);y=((b[0]-p[0])/db,(b[1]-p[1])/db)
                center=(p[0]+turn_radius*(x[0]+y[0]),p[1]+turn_radius*(x[1]+y[1]))
                start_arc=(p[0]+turn_radius*x[0],p[1]+turn_radius*x[1]);end_arc=(p[0]+turn_radius*y[0],p[1]+turn_radius*y[1])
                theta=math.atan2(start_arc[1]-center[1],start_arc[0]-center[0]);endtheta=math.atan2(end_arc[1]-center[1],end_arc[0]-center[0])
                delta=(endtheta-theta+math.pi)%(2*math.pi)-math.pi
                arc=[(center[0]+turn_radius*math.cos(theta+delta*i/24),center[1]+turn_radius*math.sin(theta+delta*i/24)) for i in range(25)]
                if all(safe_point(q,zones,posts,radius) for q in arc):rounded.extend(arc);continue
            rounded.append(p)
        rounded.append(compact[-1]);assert all(safe_point(p,zones,posts,radius) for a,b in zip(rounded,rounded[1:]) for p in points_on(a,b)),('loaded envelope',a,b,radius)
        return rounded
    return route


def make_timeline(zones, roads, posts):
    byid={r['station_id']:r for r in zones};ports={k:(r['dock']['u'],r['dock']['v']) for k,r in byid.items()}
    ports['HOME']=(2.25,19)
    route=routing(roads,ports,zones,posts)
    steps=[];frames=[];clock=0.;heading=90.;position=ports['HOME'];current='HOME'
    handoffs=[]
    def frame(t,p,yaw):return dict(t=round(t,5),u=round(p[0],5),v=round(p[1],5),yaw=round(yaw%360,5))
    def step(kind, source, target, payload, loaded, path=None, duration=2):
        nonlocal clock,heading,position
        local=[frame(0,position,heading)];time=0
        if path:
            for a,b in zip(path,path[1:]):
                length=math.dist(a,b)
                if length<1e-5:continue
                angle=math.degrees(math.atan2(b[0]-a[0],-(b[1]-a[1])))%360
                delta=abs((angle-heading+180)%360-180)
                if delta>8:
                    time+=delta/90;local.append(frame(time,a,angle))
                # Rounded samples turn gradually while driving; hard turns stop first.
                time+=length;heading=angle;position=b;local.append(frame(time,b,heading))
            duration=max(.001,time)
        else:
            local.append(frame(duration,position,heading))
        steps.append(dict(kind=kind,source=source,target=target,payload=payload,loaded=loaded,envelope_radius=1.3 if loaded and payload=='整机总成' else 1.1,start=round(clock,5),duration=round(duration,5),keyframes=local))
        clock+=duration
    def deliver(a,b,payload):
        nonlocal current
        a,b=sid(a),sid(b)
        if current!=a:step('empty',current,a,'',False,route(current,a))
        step('load',a,b,payload,True)
        step('loaded',a,b,payload,True,route(a,b,1.3 if payload=='整机总成' else 1.1))
        step('unload',a,b,payload,True)
        current=b;handoffs.append(dict(source=a,target=b,payload=payload,transport='agv'))
    def crane(a,b):
        a,b=sid(a),sid(b)
        # Hoist at source, traverse with clearance, lower and release at destination.
        steps.append(dict(kind='gantry',source=a,target=b,payload='主链整机总成',loaded=False,start=round(clock,5),duration=16+abs(byid[b]['u']+byid[b]['width']/2-byid[a]['u']-byid[a]['width']/2)/.5,keyframes=[]))
        nonlocal_clock[0]=steps[-1]['duration']
        handoffs.append(dict(source=a,target=b,payload='主链整机总成',transport='gantry'))
    # Explicit user routing, independently of the legacy CSV process graph.
    for a in ['R01','S01']:deliver(a,'G01',NAMES[a])
    for a in ['IN01','IN02']:deliver(a,'G02',NAMES[a])
    nonlocal_clock=[0];crane('G01','G02');clock+=nonlocal_clock[0]
    for a in ['C01','T01','T02']:deliver(a,'G03',NAMES[a])
    crane('G02','G03');clock+=nonlocal_clock[0]
    deliver('AGB01','AGB02','AGB内部齿轮子组件')
    for a in ['GB1','AGB02','PR01','PR02']:deliver(a,'G04',NAMES[a])
    for a in ['FU01','FU02','FU03','FU04']:
        deliver(a,'ST-B',NAMES[a]);deliver('ST-B','G04',NAMES[a])
    for a in ['OL01','OL02','OL03','OL04','AC01']:
        deliver(a,'ST-C',NAMES[a]);deliver('ST-C','G04',NAMES[a])
    crane('G03','G04');clock+=nonlocal_clock[0]
    deliver('P08','ST-C',NAMES['P08']);deliver('ST-C','M05',NAMES['P08'])
    crane('G04','M05');clock+=nonlocal_clock[0]
    for a,b in [('M05','ST-A'),('ST-A','TC01'),('TC01','CL01')]:deliver(a,b,'整机总成')
    return dict(duration=round(clock,5),agv_speed_mps=1,turn_speed_dps=90,load_seconds=2,unload_seconds=2,initial_u=2.25,initial_v=19,initial_yaw=90,steps=steps),handoffs


def generate():
    DEST.mkdir(parents=True,exist_ok=True);EVIDENCE.mkdir(parents=True,exist_ok=True)
    protected=[PROJECT/p for p in ['Assets/Scenes/PC_Main.unity','Assets/Scenes/FactoryContent.unity','Assets/Scenes/VR_Main.unity','Assets/Scenes/FactoryVRContent.unity','ProjectSettings/QualitySettings.asset','ProjectSettings/GraphicsSettings.asset']]
    protected += [ROOT/'data/factory_layout/default.json',ROOT/'data/factory_layout/environment.json',ROOT/'results/unity_validation/replay.json']
    protected += list((ROOT/'results/factory_layout').glob('*.json'))
    baseline=EVIDENCE/'protected_before.json'
    if not baseline.exists():baseline.write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected if p.exists()},indent=2),encoding='utf-8')
    sheets=read_workbook(SOURCE);index=source_index(sheets)
    purposes={}
    for _,r in sheets['工位工序步骤']:
        match=re.match(r'WS-([A-Z0-9]+)',normalized(r.get('A','')))
        if match:purposes[sid(match[1])]=r.get('C','')
    zones=[]
    for code,u,v,w,d in GEOMETRY:
        du,dv,yaw=dock(code,u,v,w,d)
        zones.append(dict(station_id=sid(code),label=NAMES[code],kind='buffer' if code.startswith('ST-') else 'workstation',
                          u=u,v=v,width=w,depth=d,area=w*d,purpose=purposes.get(sid(code),NAMES[code]),
                          dock=dict(u=du,v=dv,yaw=yaw),fixtures=fixtures(code,w,d),
                          worker_slots=[dict(x=-.7,v=.85),dict(x=.7,v=.85)],capacity_status='not_configured',
                          source_sheet=next((x['source_sheet'] for x in index['stations'] if x['station_id']==sid(code)),'')))
    roads=[((2.25,2),(68.5,2)),((2.25,19),(68.5,19)),((2.25,29.5),(61.5,29.5)),((2.25,46),(61.5,46)),
           ((2.25,2),(2.25,46)),((61.5,19),(61.5,46)),((26,2),(26,19)),((47.5,2),(47.5,19)),((24,29.5),(24,46)),((45,29.5),(45,46))]
    posts=[(u,v) for u in [4.5,14.5,24.5,34.5,44.5,54.5] for v in [21.2,27.8]]
    timeline,handoffs=make_timeline(zones,roads,posts)
    doc=dict(schema_version=2,layout_id='pt6a29',revision=1,units='metres',mode='layout_preview',
             width=70,depth=48,height=8,origin_u=35,origin_v=24,source_sha256=index['source_sha256'],
             zones=zones,roads=[dict(u1=a[0],v1=a[1],u2=b[0],v2=b[1]) for a,b in roads],
             gantry=dict(start_u=4.5,end_u=54.5,north_v=21.2,south_v=27.8,rail_height=6,
                         posts=[dict(u=u,v=v,width=.55,depth=.55) for u,v in posts],stations=[sid(x) for x in ['G01','G02','G03','G04','M05']]),
             handoffs=handoffs,timeline=timeline,spawn=dict(u=2.25,v=24.5,yaw=90))
    for filename,data in [('layout.json',doc),('process_sources.json',index)]:
        path=DEST/filename;path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        target=PROJECT/'Assets/StreamingAssets/PT6A29'/filename;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
        if filename=='layout.json':
            embedded=PROJECT/'Assets/Generated/PT6A29/layout.json';embedded.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,embedded)
    report=validate(doc,index)
    (EVIDENCE/'data_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if not report['passed']:raise SystemExit(1)


def validate(doc,index):
    checks=[]
    def check(name,ok,detail=''):checks.append(dict(name=name,passed=bool(ok),detail=detail))
    zones=doc['zones'];byid={z['station_id']:z for z in zones}
    check('29_unique_workstations',len([z for z in zones if z['kind']=='workstation'])==29 and len(byid)==32)
    check('3_buffer_zones',sum(z['kind']=='buffer' for z in zones)==3)
    overlaps=[]
    for i,a in enumerate(zones):
        for b in zones[:i]:
            if min(a['u']+a['width'],b['u']+b['width'])>max(a['u'],b['u']) and min(a['v']+a['depth'],b['v']+b['depth'])>max(a['v'],b['v']):overlaps.append([a['station_id'],b['station_id']])
    check('no_zone_overlap',not overlaps,overlaps)
    check('all_zones_inside_70x48',all(z['u']>=0 and z['v']>=0 and z['u']+z['width']<=70 and z['v']+z['depth']<=48 for z in zones))
    check('29_source_sheets',set(x['station_id'] for x in index['stations'])==set(z['station_id'] for z in zones if z['kind']=='workstation'))
    check('unique_source_records',len({x['source_id'] for x in index['steps']})==len(index['steps']))
    check('c01_header_offset_detected',next(x['header_row'] for x in index['stations'] if x['station_id']=='WS-C01')==8)
    check('legacy_mapping_pending',all(x['status']=='pending' and not x['workstation_id'] for x in index['legacy_process_mapping']))
    check('gantry_span_50m',doc['gantry']['end_u']-doc['gantry']['start_u']==50)
    posts=[(x['u'],x['v']) for x in doc['gantry']['posts']]
    invalid=[];samples=0;last_end=0
    for i,step in enumerate(doc['timeline']['steps']):
        if abs(step['start']-last_end)>.001:invalid.append(('timeline_gap',i))
        last_end=step['start']+step['duration']
        fs=step['keyframes']
        for a,b in zip(fs,fs[1:]):
            if b['t']<=a['t']:invalid.append(('non_monotonic',i))
            for p in points_on((a['u'],a['v']),(b['u'],b['v'])):
                samples+=1
                if not safe_point(p,zones,posts,step.get('envelope_radius',1.1)):invalid.append(('collision',i,p));break
        if step['kind'] in ('loaded','empty') and step['source']==step['target']:invalid.append(('internal_transfer',i))
    check('swept_disc_all_moves_and_turns',not invalid,dict(samples=samples,errors=invalid[:20],empty_radius_m=1.1,engine_loaded_radius_m=1.3))
    delivered={s['source'] for s in doc['handoffs']}|{s['target'] for s in doc['handoffs']}
    check('every_zone_participates_in_demo',set(byid)==delivered,sorted(set(byid)-delivered))
    check('finishes_at_cl01',doc['timeline']['steps'][-1]['target']=='WS-CL01')
    protected=json.loads((EVIDENCE/'protected_before.json').read_text(encoding='utf-8'))
    check('formal_state_files_unchanged',all(Path(p).exists() and hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in protected.items()))
    return dict(passed=all(c['passed'] for c in checks),checks=checks,workstations=29,buffers=3,
                fixture_instances=sum(len(z['fixtures']) for z in zones),source_records=len(index['steps']),
                demo_seconds=doc['timeline']['duration'],demo_steps=len(doc['timeline']['steps']),handoffs=len(doc['handoffs']))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.parse_args();generate()
