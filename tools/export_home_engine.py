"""Read Unity's cooked meshes without opening or modifying the Unity project."""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

import numpy as np

SOURCE = Path('C:/AllUnityProjects/MainProject/MainProject/Assets/PCProduction/Cooked')
ROOT = Path(__file__).resolve().parents[1]


def read_mesh(path):
    raw = path.read_text(encoding='utf-8')
    count = int(re.search(r'm_VertexCount: (\d+)', raw)[1])
    data = bytes.fromhex(re.search(r'_typelessdata: ([0-9a-fA-F]+)', raw)[1])
    stride = len(data) // count
    if stride != 64:
        raise ValueError(f'Unexpected vertex layout: {stride}')
    vertices = np.frombuffer(data, dtype='<f4').reshape(count, 16)
    indices = np.frombuffer(bytes.fromhex(re.search(r'm_IndexBuffer: ([0-9a-fA-F]+)', raw)[1]), dtype='<u4').reshape(-1, 3).copy()
    positions, normals, uv = vertices[:, :3].copy(), vertices[:, 3:6].copy(), vertices[:, 14:16].copy()
    positions[:, 2] *= -1
    normals[:, 2] *= -1
    uv[:, 1] = 1 - uv[:, 1]
    indices[:, [1, 2]] = indices[:, [2, 1]]
    if not all(np.isfinite(a).all() for a in (positions, normals, uv)) or indices.max() >= count:
        raise ValueError('Invalid mesh data')
    return positions, normals, uv, indices


def export(output):
    files = [SOURCE / f'EngineStages_{i}.asset' for i in range(4)]
    meshes = [read_mesh(p) for p in files]
    low = np.min([m[0].min(axis=0) for m in meshes], axis=0)
    high = np.max([m[0].max(axis=0) for m in meshes], axis=0)
    center = (low + high) / 2
    blob = bytearray()
    doc = dict(asset=dict(version='2.0', generator='simpy2 Unity cooked engine exporter'), scene=0,
               scenes=[dict(nodes=[0])], nodes=[dict(name='Unity Engine', children=[1, 2, 3, 4])],
               meshes=[], buffers=[], bufferViews=[], accessors=[],
               materials=[dict(name='Unity Engine Metal', pbrMetallicRoughness=dict(
                   baseColorFactor=[0.64, 0.7, 0.74, 1], metallicFactor=.65, roughnessFactor=.62,
                   baseColorTexture=dict(index=0)))],
               textures=[dict(source=0, sampler=0)], samplers=[dict(wrapS=10497, wrapT=10497)])

    def view(data, target=None):
        blob.extend(b'\0' * (-len(blob) % 4))
        row = dict(buffer=0, byteOffset=len(blob), byteLength=len(data))
        if target:
            row['target'] = target
        doc['bufferViews'].append(row)
        blob.extend(data)
        return len(doc['bufferViews']) - 1

    def accessor(a, kind, component, target, bounds=False):
        row = dict(bufferView=view(a.tobytes(), target), componentType=component,
                   count=len(a) if kind != 'SCALAR' else a.size, type=kind)
        if bounds:
            row.update(min=a.min(axis=0).tolist(), max=a.max(axis=0).tolist())
        doc['accessors'].append(row)
        return len(doc['accessors']) - 1

    for i, (positions, normals, uv, indices) in enumerate(meshes):
        positions -= center
        attrs = dict(POSITION=accessor(positions, 'VEC3', 5126, 34962, True),
                     NORMAL=accessor(normals, 'VEC3', 5126, 34962),
                     TEXCOORD_0=accessor(uv, 'VEC2', 5126, 34962))
        doc['meshes'].append(dict(name=f'Engine section {i+1}', primitives=[dict(
            attributes=attrs, indices=accessor(indices, 'SCALAR', 5125, 34963), material=0)]))
        doc['nodes'].append(dict(name=f'Engine section {i+1}', mesh=i))
    texture = SOURCE.parents[1] / 'model/Turboprop_Aircraft_Engine_Canada_PT6.obj/engine_fuel_control_unit_color.png'
    doc['images'] = [dict(bufferView=view(texture.read_bytes()), mimeType='image/png')]
    doc['buffers'] = [dict(byteLength=len(blob))]
    encoded = json.dumps(doc, separators=(',', ':')).encode()
    encoded += b' ' * (-len(encoded) % 4)
    blob.extend(b'\0' * (-len(blob) % 4))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(struct.pack('<III', 0x46546c67, 2, 12+8+len(encoded)+8+len(blob)) +
                       struct.pack('<II', len(encoded), 0x4e4f534a) + encoded +
                       struct.pack('<II', len(blob), 0x004e4942) + blob)
    report = dict(source=str(SOURCE / 'EngineStages.prefab'), source_triangles=sum(len(m[3]) for m in meshes),
                  source_vertices=sum(len(m[0]) for m in meshes), parts=4,
                  centered_bounds=[(low-center).tolist(), (high-center).tolist()],
                  source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                  raw_glb_bytes=output.stat().st_size, unity_project_modified=False)
    output.with_suffix('.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / '.cache/home-engine/engine-full.glb')
    export(parser.parse_args().output)
