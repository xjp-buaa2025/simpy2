"""Offline, node-by-node reduction of the imported CAD gantry. Original FBX stays intact."""
import argparse
import hashlib
import json
import mmap
import struct
import sys
import zlib
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path('C:/AllUnityProjects/MainProject/MainProject')
SOURCE = PROJECT / 'Assets/model/上下料龙门吊(简化).fbx'
OUT = ROOT / 'results/unity_validation/gantry_20261012'
sys.path.insert(0, str(ROOT / '.cache/gantry_libs'))


class Node:
    def __init__(self, data, offset):
        self.data = data
        self.end, self.count, size, length = struct.unpack_from('<QQQB', data, offset)
        self.name = data[offset+25:offset+25+length].decode('utf8')
        self.properties = offset+25+length
        self.children_at = self.properties+size

    def children(self):
        offset = self.children_at
        while offset+25 < self.end:
            node = Node(self.data, offset)
            if not node.end:
                break
            yield node
            offset = node.end

    def values(self):
        at = self.properties
        values = []
        types = {'Y': ('<h', 2), 'C': ('<?', 1), 'I': ('<i', 4), 'F': ('<f', 4), 'D': ('<d', 8), 'L': ('<q', 8)}
        for _ in range(self.count):
            code = chr(self.data[at]); at += 1
            if code in types:
                fmt, size = types[code]
                values.append(struct.unpack_from(fmt, self.data, at)[0]); at += size
            elif code in 'SR':
                size = struct.unpack_from('<I', self.data, at)[0]; at += 4
                value = self.data[at:at+size]; at += size
                values.append(value.decode('utf8', errors='replace') if code == 'S' else value)
            elif code in 'fdlibc':
                count, encoding, size = struct.unpack_from('<III', self.data, at); at += 12
                raw = self.data[at:at+size]; at += size
                if encoding: raw = zlib.decompress(raw)
                values.append(np.frombuffer(raw, dtype={'f':'<f4','d':'<f8','l':'<i8','i':'<i4','b':'u1','c':'u1'}[code], count=count))
            else:
                raise ValueError(code)
        return values


def geometry_nodes(data):
    at = 27
    while at+25 < len(data):
        node = Node(data, at)
        if not node.end: break
        if node.name == 'Objects':
            yield from (child for child in node.children() if child.name == 'Geometry')
        at = node.end


def read_geometry(node):
    children = {c.name:c for c in node.children()}
    points = children['Vertices'].values()[0].reshape(-1, 3).copy()*.001
    # Source Z-up to Unity Y-up, reflected handedness. Winding is swapped below.
    points = points[:, [0,2,1]]
    indices = children['PolygonVertexIndex'].values()[0]
    ends = np.flatnonzero(indices < 0)
    starts = np.r_[0, ends[:-1]+1]
    counts = ends-starts+1
    normalized = np.where(indices < 0, -indices-1, indices)
    if np.all(counts == 3):
        faces = normalized.reshape(-1,3).copy()
    else:
        # CAD export mostly triangles/quads; fan triangulation is independent per polygon.
        arrays = []
        for k in range(1, int(counts.max())-1):
            selected = starts[counts > k+1]
            arrays.append(np.stack([normalized[selected],normalized[selected+k],normalized[selected+k+1]],axis=1))
        faces = np.concatenate(arrays)
    faces = faces[:, [0,2,1]]
    return points, faces


def inspect(data):
    rows=[]
    for index,node in enumerate(geometry_nodes(data)):
        children={c.name:c for c in node.children()}
        v=children['Vertices'].values()[0].reshape(-1,3)[:,[0,2,1]]*.001
        indices=children['PolygonVertexIndex'].values()[0]
        triangles=int(len(indices)-2*np.count_nonzero(indices<0))
        lo=v.min(axis=0);hi=v.max(axis=0)
        rows.append(dict(index=index,id=node.values()[0],name=node.values()[1],vertices=len(v),triangles=triangles,min=lo.tolist(),max=hi.tolist(),center=((lo+hi)*.5).tolist(),size=(hi-lo).tolist()))
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'source_geometry.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
    print('Source:',len(rows),'meshes;',sum(r['triangles'] for r in rows),'triangles')
    for row in sorted(rows,key=lambda r:r['triangles'],reverse=True)[:22]: print(row)
    return rows


def cluster(points,faces,cell):
    lo=points.min(axis=0)
    keys=np.rint((points-lo)/cell).astype(np.int32)
    _,inverse=np.unique(keys,axis=0,return_inverse=True)
    count=np.bincount(inverse)
    p=np.stack([np.bincount(inverse,weights=points[:,i])/count for i in range(3)],axis=1)
    f=inverse[faces]
    f=f[(f[:,0]!=f[:,1])&(f[:,1]!=f[:,2])&(f[:,0]!=f[:,2])]
    _,first=np.unique(np.sort(f,axis=1),axis=0,return_index=True)
    return p,f[np.sort(first)]


def group_for(row):
    # Six huge rail meshes: two fixed X rails, two pairs of travelling Z beams.
    if row['index'] in (1424,1427):return 'BridgeA'
    if row['index'] in (1425,1426):return 'BridgeB'
    if row['index']==962:return 'HookA'
    if row['index']==1208:return 'HookB'
    lo=np.array(row['min']);hi=np.array(row['max']);c=np.array(row['center'])
    if lo[1]<3.5 or row['size'][0]>2:return 'Frame'
    a='A' if c[0]<-1.35 else 'B'
    x=-2.988 if a=='A' else .512
    if lo[0]>=x-.9 and hi[0]<=x+.9:
        if max(abs(lo[2]),abs(hi[2]))<1.1:return 'Trolley'+a
        if lo[1]>5.9:return 'Bridge'+a
    return 'Frame'


def simplify(points,faces,budget):
    import fast_simplification
    if len(faces)<=budget:return points,faces
    p,f=fast_simplification.simplify(np.ascontiguousarray(points,dtype=np.float64),np.ascontiguousarray(faces,dtype=np.int32),target_count=int(budget),agg=8)
    if len(f)>budget:
        # Cluster only reduced intermediates; retain every structural source component.
        cell=max(np.ptp(p,axis=0).max()/300,.001)
        for _ in range(12):
            p,f=cluster(p,f,np.full(3,cell))
            if len(f)<=budget:break
            cell*=1.5
    return p,f


def generate(data):
    rows=json.loads((OUT/'source_geometry.json').read_text(encoding='utf8'))
    lo=np.min([r['min'] for r in rows],axis=0);hi=np.max([r['max'] for r in rows],axis=0)
    origin=np.array([(lo[0]+hi[0])/2,lo[1],(lo[2]+hi[2])/2])
    pivots={'Frame':np.zeros(3),'BridgeA':np.array([-2.988,6.099,.2668])-origin,'BridgeB':np.array([.512,6.099,.2668])-origin,
            'TrolleyA':np.array([-3.1,6.05,-.04])-origin,'TrolleyB':np.array([.4,6.05,-.04])-origin,
            'HookA':np.array([-3.1,5.5634,-.04])-origin,'HookB':np.array([.4,5.5634,-.04])-origin}
    retained=[r for r in rows if max(r['size'])>=.05]
    # Source rods retain their outer shape; lightweight extending cables are added at runtime.
    weights={r['index']:max(.01,float(np.linalg.norm(r['size']))) for r in retained}
    total=sum(weights.values())
    groups={key:[] for key in pivots};piece_report=[]
    wanted=19000
    folder=OUT/'meshes';folder.mkdir(exist_ok=True)
    for index,node in enumerate(geometry_nodes(data)):
        row=rows[index]
        if index not in weights:continue
        from scipy.spatial import ConvexHull,QhullError
        children={c.name:c for c in node.children()}
        points=children['Vertices'].values()[0].reshape(-1,3)[:,[0,2,1]]*.001
        # CAD export has dense disconnected surface seams. Reconstruct each small solid's
        # outer envelope first, preserving its world placement rather than welding a broken shell.
        step=max(1,len(points)//4000);sample=np.concatenate([points[::step],points[np.r_[points.argmin(0),points.argmax(0)]]])
        points=np.unique(np.round(sample,5),axis=0)
        try:
            hull=ConvexHull(points)
        except QhullError:
            # Retain thin CAD plates as a closed box with their original bounds.
            loPart=np.array(row['min']);hiPart=np.array(row['max']);hiPart=np.maximum(hiPart,loPart+.001)
            points=np.array([[x,y,z] for x in [loPart[0],hiPart[0]] for y in [loPart[1],hiPart[1]] for z in [loPart[2],hiPart[2]]]);hull=ConvexHull(points)
        faces=hull.simplices.copy();normal=np.cross(points[faces[:,1]]-points[faces[:,0]],points[faces[:,2]]-points[faces[:,0]])
        flip=np.einsum('ij,ij->i',normal,hull.equations[:,:3])<0
        faces[flip]=faces[flip][:,[0,2,1]]
        target=max(12,int(wanted*weights[index]/total))
        points,faces=simplify(points,faces,target)
        group=group_for(row);points=points-origin-pivots[group]
        groups[group].append((points,faces))
        piece_report.append(dict(index=index,group=group,source=row['triangles'],near=len(faces)))
        if len(piece_report)%100==0:print('Reduced',len(piece_report),'/',len(retained),flush=True)
    entries=[]
    for group,pieces in groups.items():
        points=[];faces=[];offset=0
        for p,f in pieces:points.append(p);faces.append(f+offset);offset+=len(p)
        p=np.concatenate(points);f=np.concatenate(faces)
        # Preserve groups independently at every level; the hooks never disappear.
        near_target={'Frame':11500,'BridgeA':3200,'BridgeB':3200,'TrolleyA':2100,'TrolleyB':2100,'HookA':500,'HookB':500}[group]
        p,f=simplify(p,f,near_target)
        near=len(f)
        # The middle model already meets the far budget. Reuse its silhouette instead of
        # collapsing long thin structural members into open/degenerate far meshes.
        for level,ratio in enumerate([1,.29,.29]):
            a,b=(p,f) if level==0 else simplify(p,f,max(40,int(near*ratio)))
            path=folder/f'{group}_{level}.meshbin'
            with path.open('wb') as stream:
                stream.write(struct.pack('<II',len(a),len(b)*3));stream.write(np.asarray(a,dtype='<f4').tobytes());stream.write(np.asarray(b,dtype='<i4').tobytes())
            entries.append(dict(group=group,level=level,pivot=pivots[group].tolist(),file=str(path),vertices=len(a),triangles=len(b)))
    manifest=dict(source=str(SOURCE),sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),source_triangles=sum(r['triangles'] for r in rows),size=(hi-lo).tolist(),entries=entries,retained=len(retained),removed=len(rows)-len(retained),counts=[sum(e['triangles'] for e in entries if e['level']==l) for l in range(3)])
    assert all(n<=limit for n,limit in zip(manifest['counts'],[25000,8000,2500])),manifest['counts']
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    (OUT/'pieces.json').write_text(json.dumps(piece_report,ensure_ascii=False),encoding='utf8')
    print('Generated:',manifest['counts'],flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=['inspect','generate']);args=parser.parse_args()
    with SOURCE.open('rb') as stream,mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ) as data:
        if args.operation=='inspect': inspect(data)
        else: generate(data)


if __name__=='__main__': main()
