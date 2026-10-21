"""Apply narrowly scoped Unity layout integration edits, preserving unrelated work."""
from pathlib import Path
PROJECT = Path('C:/AllUnityProjects/MainProject/MainProject')

def replace(path, old, new):
    p = PROJECT / path
    text = p.read_text(encoding='utf-8-sig')
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f'Patch anchor missing: {path}: {old[:70]}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')

if __name__ == '__main__':
    replace('Assets/Scripts/SimPyReplayRuntime.cs', 'StartCoroutine(Load());StartCoroutine(WatchReplay());StartCoroutine(WatchPlaybackClock());', 'StartCoroutine(Load());StartCoroutine(WatchReplay());StartCoroutine(WatchPlaybackClock());StartCoroutine(WatchFactoryLayout());')
    replace('Assets/Scripts/SimPyReplayRuntime.cs', 'if(replay==null)return;\n        AdvanceClock();', 'if(replay==null)return;\n        AdvanceClock();')
    replace('Assets/Scripts/SimPyReplayPCVisuals.cs', 'float StationWidth(StationBinding binding) {float nearest=8;', 'float StationWidth(StationBinding binding) {var layout=LayoutStation(binding.id);if(layout!=null)return layout.base_width;float nearest=8;')
    replace('Assets/Scripts/SimPyReplayPCVisuals.cs', 'float StationHeading(string id) {return SimPyStationOrientation.Yaw(id);}', 'float StationHeading(string id) {var layout=LayoutStation(id);return layout==null?SimPyStationOrientation.Yaw(id):layout.yaw;}')
    replace('Assets/Scripts/SimPyReplayPCVisuals.cs', 'string kind=EquipmentCategory(binding.label);equipmentDescriptions[binding.id]=kind;', 'var configured=LayoutModelFor(binding.id);string kind=configured==null?EquipmentCategory(binding.label):configured.category;if(configured!=null)library=System.Array.Find(processModelBindings,p=>p.kind==configured.library_kind&&p.model);equipmentDescriptions[binding.id]=kind;')
    replace('Assets/Scripts/SimPyReplayPCVisuals.cs', 'if(binding.id=="A001"){BuildGantry', 'if(binding.id=="A001"&&(configured==null||configured.key=="gantry")){BuildGantry')
    replace('Assets/Scripts/SimPyReplayDressing.cs', 'foreach(var binding in stationBindings) {\n            Bar bar;', 'int layoutMaterialStart=ownedMaterials.Count;\n        foreach(var binding in stationBindings) {\n            Bar bar;')
    replace('Assets/Scripts/SimPyReplayDressing.cs', 'if(!IsVrViewer) {\n        // Perimeter', 'LayoutBuiltMaterials(layoutMaterialStart);\n        if(!IsVrViewer) {\n        // Perimeter')
    replace('Assets/Scripts/SimPyReplayDressing.cs', 'if(dressingToggleText)dressingToggleText.text=', 'if(layoutActive!=null){foreach(var pair in layoutRoots){var row=LayoutStation(pair.Key);if(pair.Value)pair.Value.gameObject.SetActive(factoryDressing&&row.show_model);}}\n        if(dressingToggleText)dressingToggleText.text=')
    replace('Assets/Scripts/SimPyReplayClock.cs', 'get{return playbackRole==PlaybackRole.Local||clockAuthority;}', 'get{return !layoutPreviewing&&(playbackRole==PlaybackRole.Local||clockAuthority);}')
    replace('Assets/Scripts/SimPyReplayClock.cs', 'if(!clockDirty){currentMinute=state.minute;', 'if(!clockDirty&&!LayoutClockBlocked){currentMinute=state.minute;')
    replace('Assets/Scripts/SimPyReplayClock.cs', 'void AdvanceClock() {\n        if(playbackRole', 'void AdvanceClock() {\n        if(LayoutClockBlocked){playing=false;return;}\n        if(playbackRole')
    replace('Assets/Scripts/SimPyReplaySync.cs', 'public string sim_id,message;', 'public string sim_id,message;public int layout_revision=-1;')
    replace('Assets/Scripts/SimPyReplaySync.cs', 'if(status.sim_id==replay.sim_id){', 'if(status.layout_revision>=0)layoutDesiredRevision=status.layout_revision;\n                if(status.sim_id==replay.sim_id){')
    replace('Assets/Scripts/SimPyReplaySync.cs', 'currentMinute=0;tripIndex=0;playing=', 'RestoreLayoutNames();layoutReady=false;layoutAppliedSim="";\n                    currentMinute=0;tripIndex=0;playing=')
    replace('Assets/Scripts/SimPyVRDetail.cs', 'if(!IsVrViewer||!vrOptimizedFactory||trip.route', 'if(layoutReady)return trip.route;\n        if(!IsVrViewer||!vrOptimizedFactory||trip.route')
    replace('Assets/Scripts/SimPyReplayEquipmentAnimation.cs', 'gantryRoot.SetPositionAndRotation(new Vector3(binding.anchor.position.x,.05f,binding.anchor.position.z),Quaternion.identity);', 'gantryRoot.localPosition=Vector3.zero;gantryRoot.localRotation=Quaternion.Euler(0,90,0);')
    replace('Assets/Scripts/SimPyReplayEquipmentAnimation.cs', 'foreach(float x in new[]{-3.913f,0,3.913f})foreach(float z in new[]{-2.91f,2.91f})gantryFloorObstacles.Add(new Bounds(gantryRoot.position+new Vector3(x,1.45f,z),new Vector3(.34f,2.9f,.34f)));\n        gantryFloorObstacles.Add(new Bounds(gantryRoot.position+new Vector3(0,.9f,0),new Vector3(2.65f,1.55f,.8f)));', 'RefreshGantryFloorObstacles();')
    replace('Assets/Scripts/SimPyReplayEquipmentAnimation.cs', 'var task=motion.bar.physicalTask;', 'var row=LayoutStation(motion.bar.id);if(row!=null&&!row.animation)continue;\n            var task=motion.bar.physicalTask;')
    replace('Assets/Scripts/SimPyReplayEquipmentAnimation.cs', 'if(!gantryRoot)return;var bar=', 'if(!gantryRoot)return;var gantrySettings=LayoutStation("A001");if(gantrySettings!=null&&!gantrySettings.animation)return;var bar=')
    replace('Assets/Scripts/SimPyReplayPCConsole.cs', 'pcDrawer,pcSettingsMenu,pcSpeedMenu,pcJumpMenu,pcEngineMenu})if(panel&&panel.gameObject.activeInHierarchy', 'pcDrawer,pcSettingsMenu,pcSpeedMenu,pcJumpMenu,pcEngineMenu,layoutPanel})if(panel&&panel.gameObject.activeInHierarchy')
    replace('Assets/Scripts/SimPyReplayRuntime.cs', 'foreach(var x in new float[]{-114,94})foreach(var z in new float[]{-40,68})foreach(var y in new float[]{0,5})', 'foreach(var x in new float[]{layoutReviewBounds.min.x,layoutReviewBounds.max.x})foreach(var z in new float[]{layoutReviewBounds.min.z,layoutReviewBounds.max.z})foreach(var y in new float[]{0,layoutReviewBounds.max.y})')
    replace('Assets/Scripts/SimPyReplayRuntime.cs', 'remaining-=segment;\n        }\n    }', 'remaining-=segment;\n        }\n        ApplyLayoutDockFacing(trip,raw);\n    }')
    replace('Assets/Editor/SimPyVRBuild.cs', 'PlayerSettings.bundleVersion="1.0.20261014.0";', 'PlayerSettings.bundleVersion="1.0.20261015.0";')
    replace('Assets/Editor/SimPyVRBuild.cs', 'PlayerSettings.Android.bundleVersionCode=9;', 'PlayerSettings.Android.bundleVersionCode=10;')
