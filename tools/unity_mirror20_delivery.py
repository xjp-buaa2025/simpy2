"""Deliver the verified 20 FPS relay clients without replacing older packages."""
import hashlib,json,re,shutil
from tools import unity_model_axis_delivery as build
from tools import unity_apk_validation as apk
from tools import unity_navigation_validation as nav
from tools.unity_mirror20_validation import OUT

PC=nav.ROOT/'builds/UnityPC_20261014_Mirror20FPS'
VR=nav.ROOT/'builds/UnityVR_20261014_Mirror20FPS'

def finalize():
    apk.APK=VR/'EngineFactoryVR.apk';apk.OUT=OUT/'apk';apk.main()
    old=nav.ROOT/'builds/UnityVR_20261013_AutoConnect/EngineFactoryVR.apk'
    signatures=[re.search(r'Signer #1 certificate SHA-256 digest: (.+)',apk.command(apk.BUILD_TOOLS/'apksigner.bat','verify','--print-certs',p)).group(1) for p in [old,apk.APK]]
    badging=apk.command(apk.BUILD_TOOLS/'aapt.exe','dump','badging',apk.APK)
    upgrade=dict(same_signer=signatures[0]==signatures[1],versionCode9="versionCode='9'" in badging,version_name="versionName='1.0.20261014.0'" in badging)
    assert all(upgrade.values()),upgrade;(OUT/'apk/upgrade.json').write_text(json.dumps(upgrade,indent=2))
    for folder in [PC,VR]:shutil.copy2(nav.ROOT/'docs/UNITY_VR_MIRROR20.md',folder/'使用说明.md')
    shutil.copy2(old.parent/'安装APK.bat',VR/'安装APK.bat')
    before=json.loads((OUT/'protected_before.json').read_text());protected={p:hashlib.sha256((nav.PROJECT/p).read_bytes()).hexdigest()==sha for p,sha in before.items()};assert all(protected.values())
    (OUT/'delivery.json').write_text(json.dumps(dict(pc=str(PC/'EngineFactoryPC.exe'),apk=str(apk.APK),protected=protected,hardware_tested=False),ensure_ascii=False,indent=2),encoding='utf8')

def main():
    assert json.loads((OUT/'validation.json').read_text())['passed']
    assert json.loads((OUT/'portable_validation.json').read_text())['passed']
    build.OUT=OUT;nav.control('mirror20_delivery_stop','set_play',play=False)
    build.build('pc',output=PC/'EngineFactoryPC.exe');shutil.copytree(OUT/'portable_final/VRMirrorRelay',PC/'VRMirrorService',dirs_exist_ok=True)
    try:build.build('vr',output=VR/'EngineFactoryVR.apk')
    finally:build.build('vr',operation='restore_pc')
    finalize();print('Mirror20 packages complete',flush=True)

if __name__=='__main__':main()
