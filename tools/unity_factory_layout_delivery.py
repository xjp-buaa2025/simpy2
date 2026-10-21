import hashlib,json,re,shutil
from tools import unity_model_axis_delivery as builder
from tools import unity_navigation_validation as nav
from tools import unity_apk_validation as apk
OUT=nav.ROOT/'results/unity_validation/layout_20261015'
PC=nav.ROOT/'builds/UnityPC_20261015_Layout'
VR=nav.ROOT/'builds/UnityVR_20261015_Layout'

def main():
    assert json.loads((OUT/'unity_validation.json').read_text())['pc']
    assert json.loads((OUT/'regression.json').read_text())['passed']
    before={p:hashlib.sha256((nav.PROJECT/p).read_bytes()).hexdigest() for p in ['Assets/Scenes/PC_Main.unity','Assets/Scenes/FactoryContent.unity','Assets/Scenes/VR_Main.unity','Assets/Scenes/FactoryVRContent.unity','ProjectSettings/QualitySettings.asset','ProjectSettings/GraphicsSettings.asset']}
    (OUT/'protected_before.json').write_text(json.dumps(before,indent=2))
    builder.OUT=OUT;nav.control('layout_delivery_stop','set_play',play=False)
    builder.build('pc',output=PC/'EngineFactoryPC.exe')
    shutil.copytree(nav.ROOT/'builds/UnityPC_20261014_Mirror20FPS/VRMirrorService',PC/'VRMirrorService')
    try:builder.build('vr',output=VR/'EngineFactoryVR.apk')
    finally:builder.build('vr',operation='restore_pc')
    apk.APK=VR/'EngineFactoryVR.apk';apk.OUT=OUT/'apk';apk.main()
    old=nav.ROOT/'builds/UnityVR_20261014_Mirror20FPS/EngineFactoryVR.apk'
    signatures=[re.search(r'Signer #1 certificate SHA-256 digest: (.+)',apk.command(apk.BUILD_TOOLS/'apksigner.bat','verify','--print-certs',p)).group(1) for p in [old,apk.APK]]
    badging=apk.command(apk.BUILD_TOOLS/'aapt.exe','dump','badging',apk.APK)
    checks=dict(same_signer=signatures[0]==signatures[1],version_code_10="versionCode='10'" in badging,version_name="versionName='1.0.20261015.0'" in badging,protected=all(hashlib.sha256((nav.PROJECT/p).read_bytes()).hexdigest()==sha for p,sha in before.items()))
    assert all(checks.values()),checks
    for folder in [PC,VR]:
        shutil.copy2(nav.ROOT/'docs/UNITY_FACTORY_LAYOUT.md',folder/'工厂布局使用说明.md')
        shutil.copy2(nav.ROOT/'data/factory_layout/template.xlsx',folder/'工厂布局模板.xlsx')
        shutil.copy2(nav.ROOT/'data/factory_layout/default.json',folder/'默认布局.json')
    shutil.copy2(old.parent/'安装APK.bat',VR/'安装APK.bat')
    config_before=json.loads((OUT/'editor_config_before.json').read_text());configs=nav.PROJECT/'SimPyValidation/mirror_auto_editor'
    for role,text in config_before.items():
        path=configs/(role+'.json')
        if text is None:path.unlink(missing_ok=True)
        else:path.write_text(text)
    report=dict(pc=str(PC/'EngineFactoryPC.exe'),apk=str(apk.APK),checks=checks,headset_tested=False)
    (OUT/'delivery.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(report,flush=True)
if __name__=='__main__':main()
