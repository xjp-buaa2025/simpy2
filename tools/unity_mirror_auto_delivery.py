"""Package the auto-connect client and its standalone relay; keep older builds."""
import hashlib
import json
import re
import shutil
import time
from tools import unity_model_axis_delivery as delivery
from tools import unity_apk_validation as apk
from tools import unity_navigation_validation as nav
from tools.unity_mirror_auto_validation import OUT

PC=nav.ROOT/'builds/UnityPC_20261013_AutoConnect'
VR=nav.ROOT/'builds/UnityVR_20261013_AutoConnect'

def main():
    assert json.loads((OUT/'validation.json').read_text(encoding='utf8'))['passed']
    assert json.loads((OUT/'portable_validation.json').read_text())['passed']
    delivery.OUT=OUT
    nav.control('mirror_delivery_stop','set_play',play=False)
    delivery.build('pc',output=PC/'EngineFactoryPC.exe')
    shutil.copytree(OUT/'portable/VRMirrorRelay',PC/'VRMirrorService',dirs_exist_ok=True)
    target=VR/'EngineFactoryVR.apk'
    staging=VR/('.staging_'+str(time.time_ns()))/'EngineFactoryVR.apk' if target.exists() else target
    try:delivery.build('vr',output=staging)
    finally:delivery.build('vr',operation='restore_pc')
    if staging!=target:
        shutil.copy2(target,OUT/('preliminary_apk_'+str(time.time_ns())+'.apk'))
        shutil.move(str(staging),str(target))
    finalize()

def finalize():
    apk.APK=VR/'EngineFactoryVR.apk';apk.OUT=OUT/'apk';apk.main()
    old=nav.ROOT/'builds/UnityVR_20261012_Gantry/EngineFactoryVR.apk'
    signers=[re.search(r'Signer #1 certificate SHA-256 digest: (.+)',apk.command(apk.BUILD_TOOLS/'apksigner.bat','verify','--print-certs',p)).group(1) for p in [old,apk.APK]]
    badging=apk.command(apk.BUILD_TOOLS/'aapt.exe','dump','badging',apk.APK)
    upgrade=dict(same_signer=signers[0]==signers[1],versionCode8="versionCode='8'" in badging,version_name="versionName='1.0.20261013.0'" in badging)
    assert all(upgrade.values()),upgrade
    (OUT/'apk/upgrade.json').write_text(json.dumps(upgrade,indent=2))
    for folder in [PC,VR]:shutil.copy2(nav.ROOT/'docs/UNITY_VR_AUTO_CONNECT.md',folder/'使用说明.md')
    # Installation requires the user's own authorized ADB; no development paths embedded.
    (VR/'安装APK.bat').write_text('@echo off\r\nchcp 65001 >nul\r\nwhere adb >nul 2>nul\r\nif errorlevel 1 (echo 请使用已配置的ADB运行 adb install -r EngineFactoryVR.apk & pause & exit /b 1)\r\nadb install -r "%~dp0EngineFactoryVR.apk"\r\npause\r\n',encoding='utf8')
    protected=json.loads((OUT/'protected_before.json').read_text())
    protected={p:hashlib.sha256((nav.PROJECT/p).read_bytes()).hexdigest()==sha for p,sha in protected.items()}
    assert all(protected.values()),protected
    (OUT/'delivery.json').write_text(json.dumps(dict(pc=str(PC/'EngineFactoryPC.exe'),vr=str(apk.APK),protected=protected,hardware_tested=False),ensure_ascii=False,indent=2),encoding='utf8')
    print('Auto-connect packages complete',flush=True)

if __name__=='__main__':main()
