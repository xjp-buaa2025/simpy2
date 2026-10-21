"""Generate instructions for the optional PC/VR image relay trial."""
import json
import shutil
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/unity_validation/vr_mirror_20261009'
PC=ROOT/'builds/UnityPC_20261009_MirrorTrial'
VR=ROOT/'builds/UnityVR_20261009_MirrorTrial'


def main():
    for folder in [PC,VR]:folder.mkdir(parents=True,exist_ok=True)
    if (VR/'EngineFactoryVR.apk').exists():
        from tools import unity_apk_validation as apk_tools
        apk_tools.APK=VR/'EngineFactoryVR.apk';apk_tools.OUT=OUT/'apk'
        apk_tools.main()
        previous=ROOT/'builds/UnityVR_20261008_Visual4/EngineFactoryVR.apk'
        certs=[apk_tools.command(apk_tools.BUILD_TOOLS/'apksigner.bat','verify','--print-certs',p) for p in [previous,apk_tools.APK]]
        digests=[re.search(r'Signer #1 certificate SHA-256 digest: (.+)',c).group(1) for c in certs]
        badging=apk_tools.command(apk_tools.BUILD_TOOLS/'aapt.exe','dump','badging',apk_tools.APK)
        checks=dict(same_signer=digests[0]==digests[1],versionCode5="versionCode='5'" in badging,version_name="versionName='1.0.20261009.0'" in badging)
        (OUT/'apk/upgrade_validation.json').write_text(json.dumps(dict(passed=all(checks.values()),checks=checks,signer_sha256=digests[1]),indent=2),encoding='utf-8')
        assert all(checks.values()),checks
    config=dict(serverUrl='http://10.33.244.29:8000',mirrorServerUrl='http://10.33.244.29:8011',vrMirrorEnabled=True)
    (VR/'simpy_connection_mirror_on.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
    config['vrMirrorEnabled']=False
    (VR/'simpy_connection_mirror_off.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
    adb=r'C:\AllUnitys\2021.3.45f2c1\Editor\Data\PlaybackEngines\AndroidPlayer\SDK\platform-tools\adb.exe'
    (VR/'install_and_enable_mirror.bat').write_text(f'''@echo off
cd /d "%~dp0"
"{adb}" install -r EngineFactoryVR.apk
if errorlevel 1 goto failed
"{adb}" shell mkdir -p /sdcard/Android/data/com.xjp.enginefactory.vr/files
"{adb}" push simpy_connection_mirror_on.json /sdcard/Android/data/com.xjp.enginefactory.vr/files/simpy_connection.json
if errorlevel 1 goto failed
echo Installed. Restart the VR application, then select VR mirror in the PC window.
pause
exit /b 0
:failed
echo Installation or configuration failed. Check the connected device and Android permissions.
pause
exit /b 1
'''.replace('\n','\r\n'),encoding='ascii')
    (VR/'disable_mirror.bat').write_text(f'''@echo off
cd /d "%~dp0"
"{adb}" push simpy_connection_mirror_off.json /sdcard/Android/data/com.xjp.enginefactory.vr/files/simpy_connection.json
echo Restart the VR application to apply the configuration.
pause
'''.replace('\n','\r\n'),encoding='ascii')
    (PC/'start_mirror_service.bat').write_text('''@echo off
cd /d "%~dp0..\\.."
call start_vr_mirror.bat
'''.replace('\n','\r\n'),encoding='ascii')
    text='''# VR 画面回传试验版 · 2026-10-09

PC：UnityPC_20261009_MirrorTrial/EngineFactoryPC.exe。
VR：UnityVR_20261009_MirrorTrial/EngineFactoryVR.apk，1.0.20261009.0 / versionCode 5。
旧 EXE、versionCode 4 及更早 APK 均保留。回传是可关闭的试验功能。

## 使用

1. 保持 SimPy 网页服务运行。当前排产端口8000，回传端口8011。电脑与头显连接同一局域网。
2. 运行项目根目录的 start_vr_mirror.bat，或 PC 包内 start_mirror_service.bat。当前电脑测试时已启动回传服务；无需重复启动。此启动脚本依赖当前工作区及现有 Python 环境，不是独立服务器安装包。
3. USB 连接 Rhino X Pro，确认 ADB 已授权。在 VR 包目录运行 install_and_enable_mirror.bat，安装新版并写入启用配置。推送目录不存在时，先启动一次头显应用再重试。配置IP目前10.33.244.29，IP变化时先修改两个JSON文件。
4. 重新启动 VR 应用。新 APK 默认回传关闭，启用配置只在重启后生效。
5. 打开新的 PC EXE，按 V 或点击“第一视角”，再点击小窗标题栏“VR 回传”。收到有效头显帧后标题变为“VR 实时画面 · 左眼”。
6. 点击“本地漫游”即可恢复 WASD 视角；收起窗口停止接收并释放观看租期，头显约1～4秒后停止图像采集。播放、时间轴、速度、排产同步和 AGV 操作继续使用原有功能。

需要彻底关闭头显回传时运行 disable_mirror.bat，并重新启动 VR 应用。

## 这版传什么

读取已有 XR 左眼镜像纹理并编码为 JPEG，经8011端口只保留最新一帧；没有视频队列、录制、云端传输或音频。没有新增运行时观察摄像机，没有重新渲染工厂几何；原 XR 相机、追踪、导航与共享时钟保持原工作方式。

图像保留源宽高比，上限640×480，目标约8帧/秒（网络与处理时间会降低实际帧率）。支持异步 GPU 读回时使用异步方式；设备不支持时降为同步读回约2帧/秒。该方案用于先验证设备兼容与回传流程，不能当作已完成720p/30fps视频串流。

收到超过2秒的旧帧或失去连接时，PC隐藏旧画面并显示等待/断连，不会以本地漫游冒充真实回传。界面“帧龄”估计包含服务器驻留及下行时间，不是完整的头显到PC端到端延迟。

## 已验证

- 服务端：无观看者禁止上传、观看租期、断连失效、单个头显占用、帧序列、防积压、256KiB上限、图像尺寸与格式限制。
- Unity：2D镜像复制、纹理数组指定切片复制、真实HTTP上传/下载及JPEG解码。
- 新PC独立EXE经按钮切换后，实际显示“编辑器回传测试”图像；独立程序回传测试上传150帧，原仿真画面和共享时钟继续正常显示。
- 使用明确标记的编辑器VR画面，1366×768、1920×1080、2560×1440均能显示；本地摄像机在回传时关闭，切回后恢复。
- 断连不显示旧帧；收起后无接收请求、无本地预览渲染需求；没有XR时显示“XR未运行”，不会生成假头显画面。
- PC工位朝向和绑定回归通过；六个受保护的PC/VR场景及画质文件哈希一致。原共享时钟测试通过；SimPy服务未重启、排产参数未修改。

对照截图位于项目 results/unity_validation/vr_mirror_20261009，pc_remote_1366.png 中的小窗是“编辑器回传测试”，并非真实头显。

## 真机检查与失败提示

当前未连接头显，真实XR纹理获取、双目对应、上下方向、网络稳定性与性能开销尚未验收。

右手 B 键打开诊断，查看末行回传状态：

| 提示 | 检查方式 |
|---|---|
| 回传服务未连接 · 8011 | 服务启动、配置IP、同一局域网及8011端口可达性 |
| 待机 · 等待PC请求 | PC打开第一视角小窗并切到VR回传 |
| XR未运行 · 未采集 | 头显SDK启动/定位/追踪状态 |
| SDK未提供左眼镜像纹理 | 当前SDK没有通过Unity镜像接口公开图像，需要真机日志进一步决定厂商投屏接收或Android原生采集方案 |
| GPU图像读回失败 | 保留诊断与日志，检查设备图形接口兼容性 |
| 另一台头显正在回传 | 当前试验服务同时仅允许一台头显，旧连接约3秒后到期 |

转头、瞬移、升降视角时比较PC小窗与头显的工位、AGV、标签；暂停、恢复及切回本地漫游后继续验证原功能。分别关闭/打开回传各运行一轮15分钟性能采样，导出 vr_performance_v4.json 对比CPU/GPU P95及掉帧，确认开销再决定提高画质或改硬件视频编码。

设备输入兼容配置沿用versionCode4，不把本轮测试视为真实手柄问题已经解决。
'''
    for folder in [PC,VR]:(folder/'回传测试说明.md').write_text(text,encoding='utf-8')
    (ROOT/'docs/UNITY_VR_MIRROR.md').write_text(text+'\n## 代码与接口\n\n- Unity: SimPyVRMirror.cs、Resources/SimPyVRMirrorBlit.shader；PC小窗接入点 SimPyReplayFirstPerson.cs。\n- Bootstrap通过本机配置控制vrMirrorEnabled，旧配置默认false；mirrorServerUrl默认同SimPy主机的8011端口。\n- 服务 tools.vr_mirror_server / app.api.vr_mirror，独立于app.main。\n- HTTP路径 /vr-mirror/viewer、publisher、state、frame、frame.jpg。观看者与发布者租期3秒，画面过期2秒；16个观看者上限，服务只保留一帧。\n- 验证命令：python -X utf8 -m pytest tests/test_vr_mirror.py tests/test_unity_playback.py tests/test_unity_playback_api.py -q。Unity/HTTP联调：python -X utf8 -m tools.unity_vr_mirror_validation。\n- 镜像参数使用Unity XRMirrorViewBlitDesc的源矩形及数组切片；仅在XR返回可读源纹理时发送。未覆盖native-only镜像或系统合成后的透视背景。接口参考：https://docs.unity3d.com/2021.3/Documentation/ScriptReference/XR.XRDisplaySubsystem.XRMirrorViewBlitDesc.html\n',encoding='utf-8')

if __name__=='__main__':main()
