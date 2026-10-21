"""Install small, backed-up integration points in the original Unity runtime."""
from pathlib import Path
import hashlib, json, shutil

PROJECT=Path('C:/AllUnityProjects/MainProject/MainProject')
OUT=Path(__file__).resolve().parents[1]/'results/pt6a29_original_20261021'
BACKUP=OUT/'source_before'

def edit(name, changes):
    path=PROJECT/'Assets/Scripts'/name
    original=path.read_text(encoding='utf-8-sig')
    backup=BACKUP/name
    if not backup.exists():
        backup.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,backup)
    text=original
    for old,new in changes:
        if new in text: continue
        if text.count(old)!=1: raise RuntimeError(f'{name}: expected one occurrence: {old[:95]!r}, got {text.count(old)}')
        text=text.replace(old,new)
    if text!=original:path.write_text(text,encoding='utf-8')

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    protected=[PROJECT/'Assets/Scenes'/n for n in ['PC_Main.unity','VR_Main.unity','FactoryContent.unity','FactoryVRContent.unity']]
    root=Path(__file__).resolve().parents[1]
    protected += [root/'results/unity_validation/replay.json',root/'data/factory_layout/default.json',root/'data/factory_layout/environment.json',root/'3.csv']
    baseline=OUT/'protected_before.json'
    if not baseline.exists():baseline.write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected if p.exists()},indent=2),encoding='utf-8')
    edit('SimPyReplayRuntime.cs',[
      ('            try\n            {\n                replay=ParseReplay(json);','            yield return LoadPT29Profile();\n            try\n            {\n                replay=ParseReplay(json);'),
      ('BuildBars();BuildOverview();BuildPresentation();BuildFactoryDressing();','BuildBars();PT29PrepareBindings();PT29ApplyRoutes();BuildOverview();BuildPresentation();BuildFactoryDressing();'),
      ('BuildPcVisuals();if(IsVrViewer)FinishVrPresentation();','BuildPcVisuals();if(PT29Active)BuildPT29Geometry();if(IsVrViewer)FinishVrPresentation();'),
      ('foreach(var renderer in bar.models)if(renderer&&(!IsVrViewer||renderer.enabled))','foreach(var renderer in bar.models)if(!PT29Active&&renderer&&(!IsVrViewer||renderer.enabled))'),
      ('        if(summaryLabel)summaryLabel.text="蓝：加工 "+running+','        if(PT29Active)PT29RefreshOwners();\n        if(summaryLabel)summaryLabel.text="蓝：加工 "+running+'),
      ('bool visible=!followAgv&&PcLabelRelevant(bar)&&','bool visible=!followAgv&&(!PT29Active||PT29IsDisplayed(bar.id))&&PcLabelRelevant(bar)&&'),
    ])
    edit('SimPyReplayDressing.cs',[
      ('var model=BuildSemanticEquipment(binding,item);','var model=PT29Active?PT29BuildEquipment(binding,item):BuildSemanticEquipment(binding,item);'),
      ('        LayoutBuiltMaterials(layoutMaterialStart);','        if(PT29Active)PT29FinishEquipment();\n        LayoutBuiltMaterials(layoutMaterialStart);'),
    ])
    edit('SimPyFactoryLayout.cs',[
      ('get{return layoutActive==null?-1:layoutActive.revision;}','get{return PT29Active?pt29Profile.revision:layoutActive==null?-1:layoutActive.revision;}'),
      ('public Transform FactoryStationRoot(string id){Transform root;','public Transform FactoryStationRoot(string id){if(PT29Active)return PT29PhysicalRoot(id);Transform root;'),
      ('LayoutRow LayoutStation(string id){var doc=','LayoutRow LayoutStation(string id){if(PT29Active)return PT29LayoutStation(id);var doc='),
      ('LayoutModel LayoutModelFor(string id){var doc=','LayoutModel LayoutModelFor(string id){if(PT29Active)return PT29LayoutModelFor(id);var doc='),
      ('bool LayoutClockBlocked {get{return layoutPreviewing||','bool LayoutClockBlocked {get{if(PT29Active)return layoutPreviewing;return layoutPreviewing||'),
      ('    IEnumerator WatchFactoryLayout(){\n','    IEnumerator WatchFactoryLayout(){\n        if(PT29Requested){yield return WatchPT29Profile();yield break;}\n'),
      ('    void RefreshLayoutNavigation(){\n','    void RefreshLayoutNavigation(){\n        if(PT29Active){RefreshPT29Navigation();return;}\n'),
      ('public void ApplyFactoryLayout(LayoutSnapshot snapshot){\n','public void ApplyFactoryLayout(LayoutSnapshot snapshot){\n        if(PT29Active)throw new InvalidOperationException("29工位配置请使用物理布局文档，不能导入旧79设备布局");\n'),
    ])
    edit('SimPyReplayPCVisuals.cs',[
      ('if(binding.id=="A001"&&(configured==null||configured.key=="gantry"))','if(!PT29Active&&binding.id=="A001"&&(configured==null||configured.key=="gantry"))'),
    ])
    edit('SimPyReplayEquipmentAnimation.cs',[
      ('        if(!gantryRoot)return;var gantrySettings=','        if(UpdatePT29GantryMotion())return;\n        if(!gantryRoot)return;var gantrySettings='),
    ])
    edit('SimPyReplayPCWorkers.cs',[
      ('bool show=active!=null&&bars.ContainsKey(active.station_id);','bool show=active!=null&&bars.ContainsKey(active.station_id)&&(!PT29Active||PT29IsDisplayed(active.station_id));'),
      ('foreach(var entry in pcOperationPoses){var piece=','foreach(var entry in pcOperationPoses){if(PT29Active&&!PT29IsDisplayed(entry.Key))continue;var piece='),
      ('        bool recorded=replay.events.Any(t=>t.station_id==id&&t.worker_ids!=null);','        if(PT29Active){var tasks=replay.events.Where(t=>t.station_id==id&&IsWorkEvent(t)&&IsTaskActive(t)&&t.worker_ids!=null);return replay.events.Any(t=>t.station_id==id&&t.worker_ids!=null)?"当前投入 "+tasks.SelectMany(t=>t.worker_ids).Distinct().Count()+" 人":"暂无人员数据";}\n        bool recorded=replay.events.Any(t=>t.station_id==id&&t.worker_ids!=null);'),
    ])
    edit('SimPyReplayPCCells.cs',[
      ('    void RefreshPcProductionCells(){\n','    void RefreshPcProductionCells(){\n        if(PT29Active){RefreshPT29ProductionCells();return;}\n'),
    ])
    edit('SimPyReplayPCProduction.cs',[
      ('        foreach(var station in dressedStations){\n            var row=LayoutStation(station.bar.id);Transform root;','        var pt29Picked=new HashSet<Transform>();\n        foreach(var station in dressedStations){\n            var row=LayoutStation(station.bar.id);Transform root;'),
      ('            if(!root)continue;\n            var b=StationProductionBounds','            if(!root||PT29Active&&!pt29Picked.Add(root))continue;\n            var b=StationProductionBounds'),
      ('        if(!first){pcProductionBounds.Expand','        if(PT29Active){PT29RegisterIdlePicks();pcProductionBounds=new Bounds(new Vector3(-5.2682724f,2,8.8180294f),new Vector3(76,8,54));first=false;}\n        if(!first){pcProductionBounds.Expand'),
      ('    bool PcLabelRelevant(Bar bar)\n    {','    bool PcLabelRelevant(Bar bar)\n    {\n        if(PT29Active&&!PT29IsDisplayed(bar.id))return false;'),
      ('foreach(var station in dressedStations)if(station.bar.id!=pcFocusStation){','foreach(var station in dressedStations)if(station.bar.id!=pcFocusStation&&(!PT29Active||FactoryStationRoot(station.bar.id)!=FactoryStationRoot(pcFocusStation))){'),
    ])
    edit('SimPyReplayExperience.cs',[
      ('void SelectStation(string id) {selectedStation=id;','void SelectStation(string id) {if(PT29Active){if(PT29SelectIdleZone(id))return;if(!bars.ContainsKey(id))id=PT29ResolveSelection(id);}selectedStation=id;if(PT29Active)PT29RefreshOwners();OpenPcDrawer(0);'),
    ])
    edit('SimPyReplaySync.cs',[
      ('if(status.layout_revision>=0)layoutDesiredRevision=status.layout_revision;','if(!PT29Active&&status.layout_revision>=0)layoutDesiredRevision=status.layout_revision;'),
      ('RestoreLayoutNames();layoutReady=false;layoutAppliedSim="";','RestoreLayoutNames();layoutReady=false;layoutAppliedSim="";if(PT29Active){PT29PrepareBindings();PT29ApplyRoutes();layoutReady=true;layoutAppliedSim=CurrentSimulationId;}'),
    ])
    edit('SimPyReplayVRFactory.cs',[
      ('        foreach(var station in dressedStations) {\n','        var pt29LodRoots=new HashSet<Transform>();\n        foreach(var station in dressedStations) {\n            if(PT29Active&&!pt29LodRoots.Add(FactoryStationRoot(station.bar.id)))continue;\n'),
    ])
    edit('SimPyReplayFirstPerson.cs',[
      ('firstPersonCamera.transform.position=new Vector3(-75,firstPersonEyeHeight,-25);','firstPersonCamera.transform.position=PT29Active?new Vector3(-38.0182724f,firstPersonEyeHeight,8.3180294f):new Vector3(-75,firstPersonEyeHeight,-25);'),
    ])
    print('Original runtime integration hooks installed; backups:',BACKUP)

if __name__=='__main__':main()
