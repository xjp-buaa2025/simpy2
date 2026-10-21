"""Build fresh PC/VR packages for the visually verified upright model corrections."""
import hashlib
import json
import re
import shutil
import time
from pathlib import Path
from tools import unity_navigation_validation as nav
from tools import unity_pc_ui_validation as review
from tools import unity_apk_validation as apk
from tools.unity_model_axis_repair import OUT

PC=nav.ROOT/'builds/UnityPC_20261009_AxesFixed'
VR=nav.ROOT/'builds/UnityVR_20261009_AxesFixed'
def build(kind,operation='build',output=None):
    folder=nav.PROJECT/'SimPyValidation'/('pc_build' if kind=='pc' else 'vr_build')
    report=folder/'build_report.json';report.unlink(missing_ok=True)
    request=folder/'build.request.json'
    if request.exists():raise RuntimeError('Existing build request')
    review.atomic_json(request,dict(operation=operation,output=str(output) if output else None))
    end=time.monotonic()+1200
    phase=None
    while time.monotonic()<end:
        if report.exists():
            try:r=json.loads(report.read_text(encoding='utf-8-sig'))
            except json.JSONDecodeError:time.sleep(.5);continue
            if r['phase']!=phase:
                phase=r['phase'];print(kind,phase,flush=True)
            if phase in ['complete','failed','pc_restored']:
                shutil.copy2(report,OUT/(kind+'_'+operation+'_report.json'))
                if r.get('result')!='Succeeded':raise RuntimeError(r)
                print(kind,r.get('errors',0),'errors',r.get('warnings',0),'warnings',flush=True)
                return r
        time.sleep(1)
    raise TimeoutError(kind+' build')
def main():
    assert json.loads((OUT/'validation.json').read_text())['passed']
    assert json.loads((OUT/'fixed_vr_navigation_fresh.json').read_text())['passed']
    assert json.loads((OUT/'fixed_vr_lods.json').read_text())['passed']
    nav.control('axes_delivery_stop','set_play',play=False)
    build('pc',output=PC/'EngineFactoryPC.exe')
    try:build('vr',output=VR/'EngineFactoryVR.apk')
    finally:build('vr',operation='restore_pc')
    apk.APK=VR/'EngineFactoryVR.apk';apk.OUT=OUT/'apk';apk.main()
    old=nav.ROOT/'builds/UnityVR_20261009_MirrorTrial/EngineFactoryVR.apk'
    certificates=[re.search(r'Signer #1 certificate SHA-256 digest: (.+)',apk.command(apk.BUILD_TOOLS/'apksigner.bat','verify','--print-certs',p)).group(1) for p in [old,apk.APK]]
    badging=apk.command(apk.BUILD_TOOLS/'aapt.exe','dump','badging',apk.APK)
    upgrade=dict(same_signer=certificates[0]==certificates[1],versionCode6="versionCode='6'" in badging,version_name="versionName='1.0.20261009.1'" in badging)
    (OUT/'apk/upgrade.json').write_text(json.dumps(upgrade,indent=2),encoding='utf-8');assert all(upgrade.values())
    old_vr=old.parent
    for name in ['install_and_enable_mirror.bat','disable_mirror.bat','simpy_connection_mirror_on.json','simpy_connection_mirror_off.json']:
        shutil.copy2(old_vr/name,VR/name)
    shutil.copy2(nav.ROOT/'builds/UnityPC_20261009_MirrorTrial/start_mirror_service.bat',PC/'start_mirror_service.bat')
    guide='''# 模型朝向修正版 · 2026-10-09

PC：EngineFactoryPC.exe，保留整个文件夹后运行。
VR：EngineFactoryVR.apk，1.0.20261009.1 / versionCode 6，与上一版同包名、同签名，旧包保留。

修正清洗机、液氮柜、测试台的侧放和工具台倒置；检测台柜体、夹具、探头已贴合台面。备用六自由度云台的姿态配置也已修正，当前未显示该模板。
原工位平面位置与方向、SimPy通讯、AGV、PC控制、VR导航和可选回传继续使用。原模型及VR三级网格保留，资源预算没有增加。

APK 可使用 adb install -r 覆盖安装，配置目录保持原位置。若需要回传，可运行 install_and_enable_mirror.bat；它会覆盖连接配置，执行前先核对 JSON 中的电脑IP。回传默认关闭，PC按V打开小窗后切换“VR回传”。服务器启动说明同原回传试验版。

本版完成编辑器几何、场景与构建检查，未连接头显。请真机检查两个眼睛的设备台面、冷冻槽开口、近中远切换、手柄瞬移与高度调节。
完整检查和截图见项目 docs/UNITY_MODEL_AXES_FIXED.md 及 results/unity_validation/model_axes_fixed_20261009。
'''
    for folder in [PC,VR]:(folder/'测试说明.md').write_text(guide,encoding='utf-8')
    before=json.loads((OUT/'protected_before.json').read_text())
    protected={p:hashlib.sha256((nav.PROJECT/p).read_bytes()).hexdigest()==sha for p,sha in before.items()}
    assert all(protected.values()),protected
    (OUT/'delivery.json').write_text(json.dumps(dict(pc=str(PC/'EngineFactoryPC.exe'),vr=str(apk.APK),protected=protected,hardware_tested=False),ensure_ascii=False,indent=2),encoding='utf-8')
    print('Packages complete',flush=True)
if __name__=='__main__':main()
