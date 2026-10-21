"""Reproduce the web engine from Unity source. Node/npm and NumPy are build-time only."""
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from tools.export_home_engine import export

ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT/'.cache/home-engine-tools'
WORK = ROOT/'.cache/home-engine'
THREE = '0.186.1'
GLTF = '4.5.1'


def run(*args):
    subprocess.run(list(map(str,args)), cwd=ROOT, check=True)


def stamp_frontend():
    index = ROOT/'frontend/index.html'
    text = index.read_text(encoding='utf-8')
    def replace(match):
        path = ROOT/'frontend'/match[2]
        token = hashlib.sha256(path.read_bytes()).hexdigest()[:10]
        return f'{match[1]}="{match[2]}?v={token}"'
    text = re.sub(r'(src|href)="((?:js|css)/[^?\"]+\.(?:js|css))\?v=[^\"]+"', replace, text)
    index.write_text(text, encoding='utf-8')


def main():
    run(shutil.which('npm.cmd') or shutil.which('npm'),'install','--prefix',DEPS,'--no-audit','--no-fund',
        f'three@{THREE}',f'@gltf-transform/cli@{GLTF}')
    export(WORK/'engine-full.glb')
    cli = DEPS/'node_modules/@gltf-transform/cli/bin/cli.js'
    run('node',cli,'weld',WORK/'engine-full.glb',WORK/'engine-welded.glb')
    run('node',cli,'simplify',WORK/'engine-welded.glb',WORK/'engine-reduced.glb','--ratio','.122','--error','.005')
    output = ROOT/'frontend/assets/home-engine.glb'
    run('node',cli,'quantize',WORK/'engine-reduced.glb',output,'--quantize-position','16',
        '--quantize-normal','12','--quantize-texcoord','16')
    if output.stat().st_size>12*1024*1024:
        raise ValueError('Published model exceeds the size budget')
    vendor = ROOT/'frontend/vendor/three'
    vendor.mkdir(parents=True,exist_ok=True)
    package = DEPS/'node_modules/three'
    for source in ['build/three.module.js','build/three.core.js','examples/jsm/controls/OrbitControls.js',
                   'examples/jsm/loaders/GLTFLoader.js','examples/jsm/environments/RoomEnvironment.js',
                   'examples/jsm/utils/BufferGeometryUtils.js','examples/jsm/utils/SkeletonUtils.js']:
        target = vendor/Path(source).name
        shutil.copy2(package/source,target)
        if target.name=='GLTFLoader.js':
            target.write_text(target.read_text(encoding='utf-8').replace('../utils/','./'),encoding='utf-8')
    shutil.copy2(package/'LICENSE',vendor/'LICENSE.txt')
    (vendor/'VERSION.txt').write_text(f'three {THREE}\nSource: https://www.npmjs.com/package/three\nLocal GLTFLoader utils import paths adjusted.\n',encoding='utf-8')
    report = json.loads((WORK/'engine-full.json').read_text(encoding='utf-8'))
    import struct
    binary = output.read_bytes()
    doc = json.loads(binary[20:20+struct.unpack_from('<I',binary,12)[0]])
    report.update(three_version=THREE,gltf_transform_version=GLTF,published_bytes=len(binary),
                  published_triangles=sum(doc['accessors'][p['indices']]['count']//3 for m in doc['meshes'] for p in m['primitives']),
                  published_sha256=hashlib.sha256(binary).hexdigest(),simplify_ratio=.122,simplify_error=.005)
    destination = ROOT/'results/home_engine_validation_20261020/model-export.json'
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    stamp_frontend()
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
