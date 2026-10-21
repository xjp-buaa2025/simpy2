"""Build tested gantry/animation revision and retain all older packages."""
import hashlib
import json
import re
import shutil
from tools import unity_model_axis_delivery as delivery
from tools import unity_apk_validation as apk
from tools import unity_navigation_validation as nav
from tools.unity_gantry_validation import OUT

PC=nav.ROOT/'builds/UnityPC_20261012_Gantry'
VR=nav.ROOT/'builds/UnityVR_20261012_Gantry'


def main():
    assert json.loads((OUT/'validation.json').read_text(encoding='utf8'))['passed']
    delivery.OUT=OUT
    nav.control('gantry_delivery_stop','set_play',play=False)
    delivery.build('pc',output=PC/'EngineFactoryPC.exe')
    try:delivery.build('vr',output=VR/'EngineFactoryVR.apk')
    finally:delivery.build('vr',operation='restore_pc')
    apk.APK=VR/'EngineFactoryVR.apk';apk.OUT=OUT/'apk';apk.main()
    old=nav.ROOT/'builds/UnityVR_20261009_AxesFixed/EngineFactoryVR.apk'
    signers=[re.search(r'Signer #1 certificate SHA-256 digest: (.+)',apk.command(apk.BUILD_TOOLS/'apksigner.bat','verify','--print-certs',path)).group(1) for path in [old,apk.APK]]
    badging=apk.command(apk.BUILD_TOOLS/'aapt.exe','dump','badging',apk.APK)
    upgrade=dict(same_signer=signers[0]==signers[1],versionCode7="versionCode='7'" in badging,version_name="versionName='1.0.20261012.0'" in badging)
    assert all(upgrade.values()),upgrade
    (OUT/'apk/upgrade.json').write_text(json.dumps(upgrade,indent=2),encoding='utf8')
    for name in ['enable_mirror_only.bat','check_mirror_connection.bat','install_and_enable_mirror.bat','disable_mirror.bat','simpy_connection_mirror_on.json','simpy_connection_mirror_off.json']:
        shutil.copy2(old.parent/name,VR/name)
    shutil.copy2(nav.ROOT/'builds/UnityPC_20261009_AxesFixed/start_mirror_service.bat',PC/'start_mirror_service.bat')
    guide='''# 龙门架与工位动画 · 2026-10-12

PC：保留整个目录后运行 EngineFactoryPC.exe。
VR：EngineFactoryVR.apk，versionCode 7 / 1.0.20261012.0，与 versionCode 6 同包名、同签名，可 adb install -r 覆盖安装。

A001「核心机与动力涡轮对接」增加双桥龙门架，一套吊具吊运模块、下降对接并回位，另一套停放。蓝色底座保留，原模型与旧吊车资源保留。
龙门架主体近景7470三角形，中远景1999；材质3个。按原CAD每个零件的外轮廓重建轻量网格，小螺纹、内部槽、5cm以下细件被简化。附加模块、绳和支架为低面示意件。
P003/P012压头、P004/F061转子、P013/A006探头随工序进度动作；现有同类动作也统一随仿真时钟。暂停静止，拖动时间轴直接显示对应姿态。发动机筛选不改变设备实际活动。

若当前为月末暂停，吊具停放、模块已对接是正常状态。可在PC回到起点播放，或查看项目 results/unity_validation/gantry_20261012/pc_gantry_animation.gif 的编辑器动作示意；GIF为进度采样，不是头显实拍。
VR只读跟随PC。瞬移、高度调整和画面回传沿用原功能；只有柱脚和装配台阻挡落点，架下空地可进入。

仅 adb install 不会开启回传。已经配置过回传的设备会保留配置；如未开启，可运行 enable_mirror_only.bat（备份/保留原服务器地址），随后重启头显应用，PC按V切到“VR回传”。不要在IP变化后直接推送旧JSON。

完成编辑器动作、79工位几何、VR导航、包结构与签名检查。未连接头显，请真机检查双眼外形、LOD、架下落点、手柄、AGV与实际帧时间。详见 docs/UNITY_GANTRY_ANIMATION.md。
'''
    for folder in [PC,VR]:(folder/'测试说明.md').write_text(guide,encoding='utf8')
    before=json.loads((OUT/'protected_before.json').read_text())
    protected={p:hashlib.sha256((nav.PROJECT/p).read_bytes()).hexdigest()==sha for p,sha in before.items()}
    assert all(protected.values())
    (OUT/'delivery.json').write_text(json.dumps(dict(pc=str(PC/'EngineFactoryPC.exe'),vr=str(apk.APK),protected=protected,hardware_tested=False),ensure_ascii=False,indent=2),encoding='utf8')
    print('Gantry packages complete',flush=True)


if __name__=='__main__':main()
