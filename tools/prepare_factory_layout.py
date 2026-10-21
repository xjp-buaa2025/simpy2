"""Freeze actual generated PC station geometry into the versioned layout catalog."""
import json,math,shutil
from pathlib import Path
from tools import unity_validation as adapter
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/unity_validation/layout_20261015'
DEST=ROOT/'data/factory_layout'

def main():
    DEST.mkdir(parents=True,exist_ok=True)
    document=json.loads((OUT/'default_layout.raw.json').read_text())
    geometry=json.loads((adapter.PROJECT/'SimPyValidation/factory_layout/baseline_pc.json').read_text()) if hasattr(adapter,'PROJECT') else json.loads(Path('C:/AllUnityProjects/MainProject/MainProject/SimPyValidation/factory_layout/baseline_pc.json').read_text())
    byid={r['station_id']:r for r in geometry['geometry']};models={m['key']:m for m in document['models']}
    for model in models.values():model['width_ratio']=model['depth_ratio']=0
    for row in document['stations']:
        g=byid[row['station_id']];sx,sz=g['size']['x'],g['size']['z']
        if abs(math.sin(math.radians(g['yaw'])))>.5:sx,sz=sz,sx
        row.update(size_x=sx,size_z=sz,center_x=0.,center_z=0.)
        model=models[row['model_key']];model['width_ratio']=max(model['width_ratio'],sx/row['base_width']);model['depth_ratio']=max(model['depth_ratio'],sz/row['base_width'])
    document['stations'].sort(key=lambda r:r['station_id'])
    (DEST/'default.json').write_text(json.dumps(document,ensure_ascii=False,indent=2),encoding='utf-8')
    root=json.loads((adapter.SCENE_SOURCE/'root_transform.json').read_text()) if (adapter.SCENE_SOURCE/'root_transform.json').exists() else None
    # The adapter root is saved in scene_probe.json; use the same source transform.
    scene=json.loads(Path('C:/AllUnityProjects/MainProject/MainProject/SimPyValidation/scene_probe.json').read_text())
    plant=next(o for o in scene['objects'] if o['name']=='psfile_PlantSimulation')
    root=plant['position']
    tracks=json.loads((adapter.SCENE_SOURCE/'appearance_tracks.json').read_text())['tracks']
    lines=[[[t['start'][0]+root['x'],t['start'][2]+root['z']],[t['end'][0]+root['x'],t['end'][2]+root['z']]] for t in tracks]
    from app.core.factory_layout import box
    roads=[]
    for index,(a,b) in enumerate(lines):
        roads.append(dict(name='物流通道'+str(index+1),polygon=box((a[0]+b[0])/2,(a[1]+b[1])/2,abs(a[0]-b[0])+.8,abs(a[1]-b[1])+.8)))
    obstacles=[]
    for x in [-99,-75,-51,-27,-3,21,45,69,87]:obstacles.append(dict(name='北侧货架',polygon=box(x,57,10,2)))
    for x in [-98,-80,-62,-44,-26,-8]:obstacles.append(dict(name='南侧货架',polygon=box(x,-43,11,2)))
    for x,z in [(-106,17),(-104,-14),(-7,56),(90,1)]:obstacles.append(dict(name='工具柜',polygon=box(x,z,2.55,.95)))
    for x,z in [(-104,39),(-104,-24)]:obstacles.append(dict(name='固定工具台',polygon=box(x,z,3,6)))
    environment=dict(min_x=-125,max_x=114,min_z=-48,max_z=65,lines=lines,roads=roads,obstacles=obstacles,agv_start=[8.011127471923828,4.330870628356934])
    (DEST/'environment.json').write_text(json.dumps(environment,ensure_ascii=False,indent=2),encoding='utf-8')
    target=Path('C:/AllUnityProjects/MainProject/MainProject/Assets/StreamingAssets/factory_layout_default.json')
    shutil.copy2(DEST/'default.json',target)
    print('default rows:',len(document['stations']),'models:',len(models),'tracks:',len(lines))
if __name__=='__main__':main()
