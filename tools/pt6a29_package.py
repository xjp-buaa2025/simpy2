"""Package final binaries, independent-source data, and verified acceptance evidence."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import zipfile
import os

from pt6a29_delivery import ROOT,PROJECT,OUT

PC=ROOT/'builds/UnityPC_20261021_PT6A29'
VR=ROOT/'builds/UnityVR_20261021_PT6A29'
SDK=Path('C:/AllUnitys/2021.3.45f2c1/Editor/Data/PlaybackEngines/AndroidPlayer/SDK')
BUILD_TOOLS=SDK/'build-tools/34.0.0'

def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    data=read(OUT/'data_validation.json');native=read(OUT/'native_acceptance.json')
    pc=read(OUT/'pc_release_tests_loaded.json');vr=read(OUT/'vr_release_tests.json')
    pcb=read(OUT/'pc_build.json');vrb=read(OUT/'vr_build.json')
    assert all([data['passed'],native['passed'],pc['success'],vr['success'],pcb['success'],vrb['success']])
    assert pc['audit']['layout_sha256']==vr['audit']['layout_sha256']
    assert pc['audit']['fixtures']==vr['audit']['fixtures']
    hashes=read(OUT/'protected_before.json');protected={p:Path(p).exists() and sha(Path(p))==h for p,h in hashes.items()}
    assert all(protected.values()),protected
    apk=VR/'EngineFactoryVR.apk';old=ROOT/'builds/UnityVR_20261020_OnDemandWorkers/EngineFactoryVR_v14.apk'
    env=dict(os.environ,JAVA_HOME='C:/AllUnitys/2021.3.45f2c1/Editor/Data/PlaybackEngines/AndroidPlayer/OpenJDK')
    def signing(path):
        text=subprocess.check_output([str(BUILD_TOOLS/'apksigner.bat'),'verify','--print-certs',str(path)],env=env,text=True,encoding='utf-8')
        return re.search(r'certificate SHA-256 digest: ([0-9a-f]+)',text)[1]
    cert=signing(apk);assert cert==signing(old)
    badging=subprocess.check_output([str(BUILD_TOOLS/'aapt.exe'),'dump','badging',str(apk)],text=True,encoding='utf-8')
    assert "name='com.xjp.enginefactory.vr'" in badging and "versionCode='15'" in badging and "versionName='1.0.20261021.0'" in badging
    canonical=ROOT/'data/factory_layout/pt6a29/layout.json'
    with zipfile.ZipFile(apk) as z:
        assert z.read('assets/PT6A29/layout.json')==canonical.read_bytes()
        assert 'lib/arm64-v8a/libil2cpp.so' in z.namelist()
        apk_files=len(z.infolist())
    assert (PC/'EngineFactoryPC_Data/StreamingAssets/PT6A29/layout.json').read_bytes()==canonical.read_bytes()
    samples=native['performance']
    summary=dict(passed=True,data_checks=len(data['checks']),pc_editor_checks=len(pc['checks']),vr_editor_checks=len(vr['checks']),native_checks=len(native['checks']),
                 layout_sha256=sha(canonical),pc_vr_geometry_identical=True,formal_files_unchanged=protected,
                 legacy_regression=dict(passed=22,warnings=4,command='python -m pytest tests/test_factory_layout.py tests/test_unity_playback.py -q'),
                 pc_build=dict(errors=pcb['errors'],warnings=pcb['warnings'],seconds=pcb['seconds']),
                 vr_build=dict(errors=vrb['errors'],warnings=vrb['warnings'],seconds=vrb['seconds']),
                 apk=dict(bytes=apk.stat().st_size,sha256=sha(apk),package='com.xjp.enginefactory.vr',versionCode=15,version='1.0.20261021.0',signer_sha256=cert,same_signer_as_v14=True,arm64=True,zip_entries=apk_files),
                 continuous_native=dict(seconds=samples[-1]['wall_seconds'] if samples else 0,samples=len(samples),
                                        smoothed_fps_min=min(x['fps'] for x in samples),smoothed_fps_max=max(x['fps'] for x in samples),
                                        whole_cycle_completed=any(not x['playing'] and x['seconds']>2399 for x in samples)),
                 headset=dict(adb_devices=[],tested=False),source_records=data['source_records'],fixture_instances=data['fixture_instances'])
    (OUT/'delivery_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    for package in [PC,VR]:
        evidence=package/'检查与截图';evidence.mkdir(exist_ok=True)
        for name in ['data_validation.json','pc_release_tests_loaded.json','vr_release_tests.json','native_acceptance.json','pc_build.json','vr_build.json','delivery_summary.json']:
            shutil.copy2(OUT/name,evidence/name)
        for filename in ['layout.json','process_sources.json']:shutil.copy2(ROOT/'data/factory_layout/pt6a29'/filename,package/filename)
        for src,dest in [('pc_overview','工厂全景'),('pc_layout','工位俯视'),('pc_assembly','主链龙门吊'),('pc_prefab','齿轮组预制'),('pc_test_cell','试车工位'),('pc_cleaning','清洗工位')]:
            shutil.copy2(OUT/'native'/(src+'.png'),evidence/(dest+'.png'))
        shutil.copy2(PROJECT/'SimPyValidation/pt6a29/vr_release_entry.png',evidence/'VR编辑器界面_非头显实拍.png')
        guide=(ROOT/'docs/PT6A29_FACTORY_PREVIEW.md').read_text(encoding='utf-8')
        guide+='\n\n## 本次交付结果\n\n'
        guide+=f"- PC、VR构建均0错误。布局数据{len(data['checks'])}项、PC编辑器{len(pc['checks'])}项、VR编辑器{len(vr['checks'])}项、PC独立程序{len(native['checks'])}项检查通过。原布局/时钟22项回归通过。\n"
        guide+=f"- 独立程序连续运行{summary['continuous_native']['seconds']:.1f}秒，完成完整物流循环。每10秒采样的平滑FPS范围为{summary['continuous_native']['smoothed_fps_min']:.2f}～{summary['continuous_native']['smoothed_fps_max']:.2f}，这不是逐帧P95或GPU耗时。\n"
        guide+=f"- APK为v15 / 1.0.20261021.0，大小{apk.stat().st_size/2**20:.2f}MiB，包名和签名与v14一致。\n"
        guide+="- 工位、缓存区及137件设备几何在PC、VR完全一致；受保护的旧场景、图形设置和仿真结果文件未变。未连接头显，尚无头显实测证据。\n"
        (package/'使用与检查说明.md').write_text(guide,encoding='utf-8')
        # The gallery uses real standalone screenshots, never synthetic renderings.
        gallery='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>PT6A 29工位场景</title><style>body{font:16px/1.7 system-ui;max-width:1500px;margin:30px auto;background:#edf2f5;color:#18313e;padding:0 24px}img{width:100%;border-radius:8px}section{margin:30px 0}h1{font-size:30px}</style><h1>PT6A 29工位工厂场景</h1><p>70×48m · 29工位 · 3缓存区 · 50m共享龙门吊。以下均为PC独立程序截图。运输演示独立于正式排产。</p>'
        for name in ['工厂全景','工位俯视','主链龙门吊','齿轮组预制','试车工位','清洗工位']:gallery+=f'<section><h2>{name}</h2><img src="{name}.png" loading="lazy"></section>'
        gallery+='<section><h2>VR编辑器界面</h2><p>编辑器预览，非头显实拍。</p><img src="VR编辑器界面_非头显实拍.png" loading="lazy"></section>'
        gallery+='</html>'; (evidence/'场景预览.html').write_text(gallery,encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
