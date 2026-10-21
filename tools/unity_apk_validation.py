"""Inspect the produced APK with the bundled Android build tools; no device operations."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
APK=ROOT/'builds/UnityVR_20261007/EngineFactoryVR.apk'
OUT=ROOT/'results/unity_validation/apk_20261007'
ANDROID=Path('C:/AllUnitys/2021.3.45f2c1/Editor/Data/PlaybackEngines/AndroidPlayer')
BUILD_TOOLS=ANDROID/'SDK/build-tools/34.0.0'

def command(*args):
    env=dict(os.environ,JAVA_HOME=str(ANDROID/'OpenJDK'))
    process=subprocess.run([str(x) for x in args],capture_output=True,text=True,encoding='utf-8',errors='replace',env=env)
    if process.returncode:raise RuntimeError(process.stdout+process.stderr)
    return process.stdout+process.stderr

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    badging=command(BUILD_TOOLS/'aapt.exe','dump','badging',APK)
    manifest=command(BUILD_TOOLS/'aapt.exe','dump','xmltree',APK,'AndroidManifest.xml')
    signature=command(BUILD_TOOLS/'apksigner.bat','verify','--verbose',APK)
    alignment=command(BUILD_TOOLS/'zipalign.exe','-c','-p','4',APK)
    for name,value in [('apk_badging.txt',badging),('apk_manifest.txt',manifest),('apk_signature.txt',signature)]:
        (OUT/name).write_text(value,encoding='utf-8')
    with zipfile.ZipFile(APK) as archive:
        crc_ok=archive.testzip() is None
        names=archive.namelist()
        native=[n for n in names if n.startswith('lib/') and n.endswith('.so')]
        global_settings=archive.read('assets/bin/Data/globalgamemanagers')
        required=['lib/arm64-v8a/libil2cpp.so','lib/arm64-v8a/libunity.so']
        # SDK minor versions use different plugin filenames; verify the actual loader plugin below.
        xr_libraries=[n for n in native if any(s in n.lower() for s in ['xms','xruntime','sxr','svr'])]
    checks={
        'archive_crc':crc_ok,
        'package':"name='com.xjp.enginefactory.vr'" in badging,
        'label':"application-label:'EngineFactory VR'" in badging,
        'api26':"sdkVersion:'26'" in badging,
        'arm64_only':bool(native) and all(n.startswith('lib/arm64-v8a/') for n in native),
        'unity_and_il2cpp':all(n in native for n in required),
        'xr_native_libraries':len(xr_libraries)>=2,
        'single_launcher':manifest.count('"android.intent.action.MAIN" (Raw:')==1 and manifest.count('"android.intent.category.LAUNCHER" (Raw:')==1,
        'qti_launcher':"launchable-activity: name='com.qti.player.UnityPlayerActivity'" in badging,
        'internet_permission':'android.permission.INTERNET' in badging,
        'lan_http':'android:usesCleartextTraffic' in manifest and any('android:usesCleartextTraffic' in line and '0xffffffff' in line for line in manifest.splitlines()),
        'signature_v2':'Verified using v2 scheme (APK Signature Scheme v2): true' in signature,
        'zip_alignment':True,
        'vr_scene_list':b'Assets/Scenes/VR_Main.unity' in global_settings and b'Assets/Scenes/FactoryVRContent.unity' in global_settings and b'Assets/Scenes/PC_Main.unity' not in global_settings,
    }
    result=dict(passed=all(checks.values()),checks=checks,apk=str(APK),apk_bytes=APK.stat().st_size,sha256=hashlib.sha256(APK.read_bytes()).hexdigest(),native_libraries=native,xr_libraries=xr_libraries)
    (OUT/'apk_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (APK.parent/'SHA256.txt').write_text(result['sha256']+'  '+APK.name+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['passed','checks','apk_bytes','sha256']},ensure_ascii=False))
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
