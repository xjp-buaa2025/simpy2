"""Write local version 4 delivery documentation from completed validation reports."""
import json
import shutil
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / 'results/unity_validation/vr_visual_v4_20261008'
DELIVERY = ROOT / 'builds/UnityVR_20261008_Visual4'

def main():
    DELIVERY.mkdir(parents=True, exist_ok=True)
    from tools import unity_apk_validation as apk_tools
    apk = DELIVERY / 'EngineFactoryVR.apk'
    if apk.exists():
        previous = ROOT / 'builds/UnityVR_20261008_RhinoFix/EngineFactoryVR.apk'
        certs = [apk_tools.command(apk_tools.BUILD_TOOLS / 'apksigner.bat', 'verify', '--print-certs', p) for p in [previous, apk]]
        hashes = [re.search(r'Signer #1 certificate SHA-256 digest: (.+)', c).group(1) for c in certs]
        badging = apk_tools.command(apk_tools.BUILD_TOOLS / 'aapt.exe', 'dump', 'badging', apk)
        checks = dict(same_signer=hashes[0] == hashes[1], versionCode4="versionCode='4'" in badging, version_name="versionName='1.0.20261008.2'" in badging)
        (RESULT / 'apk/upgrade_validation.json').write_text(json.dumps(dict(passed=all(checks.values()), checks=checks, signer_sha256=hashes[1]), indent=2), encoding='utf-8')
        assert all(checks.values()), checks
    comparison = DELIVERY / '画面对比'
    comparison.mkdir(exist_ok=True)
    lines = ['# VR versionCode 4 画面对比', '', '以下为同位置、同方向的 Unity 编辑器单目截图，不能代替头显双目验收。', '']
    for name, title in [('entrance','入口'), ('middle','厂房中部'), ('inspection','终检区'), ('washer','清洗机旁')]:
        lines += [f'## {title}', '', '旧版：', '', f'![旧版](画面对比/before_{name}.png)', '', '新版：', '', f'![新版](画面对比/after_{name}.png)', '']
        for prefix in ['before', 'after']:
            shutil.copy2(RESULT / f'{prefix}_{name}.png', comparison / f'{prefix}_{name}.png')
    for name in ['clip_160', 'clip_350', 'clean_middle', 'clean_washer']:
        shutil.copy2(RESULT / f'{name}.png', comparison / f'{name}.png')
    lines += ['## 远墙裁剪验证', '', '同一入口视角：160 米时远墙被裁掉，350 米时远墙完整。定位与标定组件仍保留。', '', '![160米](画面对比/clip_160.png)', '', '![350米](画面对比/clip_350.png)', '', '## 场景外观参考', '', '以下仅在编辑器截图中隐藏信息牌，方便观察模型；安装包仍保留 VR 信息牌。', '', '![厂房中部](画面对比/clean_middle.png)', '', '![清洗机](画面对比/clean_washer.png)', '']
    (DELIVERY / '画面对比.md').write_text('\n'.join(lines), encoding='utf-8')
    shutil.copy2(ROOT / 'builds/UnityVR_20261008_RhinoFix/simpy_connection.json', DELIVERY / 'simpy_connection.json')
    (DELIVERY / '测试说明.md').write_text('''# Rhino X Pro VR versionCode 4 测试说明

包名：com.xjp.enginefactory.vr；版本：1.0.20261008.2 / versionCode 4。
旧安装包保留。本包沿用原签名，签名校验结果见验证目录。

构建完成，0错误、3条警告：Android 双输入系统兼容提示、SDK ActionBasedController 已弃用提示，以及 SDK 示例变量未使用提示。本轮沿用输入配置；双输入系统对真机输入与性能的影响需实际确认。

## 画面变化

- VR 相机远裁剪改为 350 米，并使用中性灰背景；编辑器入口对照确认远墙不再被裁掉。
- 恢复原设备外形，重设备使用离线减面副本及三级细节；所有 79 个工位保留远景外形。
- 恢复浅灰墙体、柱梁、窗带、灯具、货架与工具柜，保留蓝色工位与安全黄通道；静态厂房使用烘焙光照。
- 无实时动态阴影、实时反射、全屏后处理或 PC 预览相机。PC 场景资源与画质设置校验未变化。

对照图见 [画面对比](画面对比.md)。

## 安装与连接

电脑、头显连接同一局域网，启动 SimPy 网页服务。随包配置目前指向 http://10.33.244.29:8000；电脑 IP 改变时需要更新头显应用文件目录中的 simpy_connection.json。

```powershell
adb install -r EngineFactoryVR.apk
adb push simpy_connection.json /sdcard/Android/data/com.xjp.enginefactory.vr/files/simpy_connection.json
```

推送配置后重新启动应用。网页重新排产及共享时钟已通过回归；VR 仅观看，不接管网页播放时钟。

## 手柄

| 操作 | 效果 |
|---|---|
| 左摇杆前推并保持 | 左手射线选择落点 |
| 左摇杆回中 | 到达有效落点 |
| 瞄准时后拨或侧拨 | 取消，回中不会瞬移 |
| 右摇杆上下 | 调节高度，范围 ±0.9 米 |
| 右摇杆左右 | 每次转向 30° |
| 左摇杆按下 | 恢复高度并取消瞄准 |
| 右摇杆按下 | 返回入口并恢复高度 |
| 右手 B 键 | 打开输入与性能诊断 |

断连、休眠或复位后先松开摇杆，再重新操作。本轮编辑器输入、导航回归通过，未连接头显，真实手柄验收仍待完成。

## 真机验收

1. 在入口、中部、终检区与清洗机旁查看左右眼：无远景白色大片、缺失设备、异常朝向或落地问题。
2. 穿过 15/20 米、45/55 米切换区，检查模型没有持续闪动。检查 AGV 运输、转弯、暂停与完工状态，车体遵循真实遮挡。
3. 测试所有手柄操作、无效落点、取消、断连重连，检查输入诊断中实际摇杆数值和导航阻断原因。
4. 保持应用前台、头显 XR 正常运行至少 15 分 30 秒：先预热 30 秒，再采样 900 秒。沿入口、中部、终检与设备密集区往返，并观察移动中的 AGV。
5. 导出性能记录：

```powershell
adb pull /sdcard/Android/data/com.xjp.enginefactory.vr/files/vr_performance_v4.json .
adb shell dumpsys meminfo com.xjp.enginefactory.vr > device_memory.txt
```

记录包括刷新率、CPU/GPU P95、帧间隔、累计掉帧和 Unity 分配内存峰值。目标 CPU/GPU P95 均低于刷新周期的 80%。CPU 来源为 Unity FrameTimingManager，可能包含等待；GPU 来自 XR 插件。若插件未提供数据，将标记 unavailable/-1，不能判定性能通过。Unity 内存不是头显进程总内存，应结合 dumpsys 结果。

未满 15 分钟退出或休眠会保存部分记录，complete=false。当前只有资源预算、编辑器回归与 APK 校验结果；没有真机双目、温升或帧时间验收结果。
''', encoding='utf-8')
    geometry = []
    for view in ['entrance','middle','inspection','washer','pressure_washer','pressure_cold','pressure_all']:
        data = json.loads((RESULT / f'after_{view}.geometry.json').read_text(encoding='utf-8-sig'))
        geometry.append(dict(view=view, triangles=data['frustum_triangles'], batches=data['batches'], setpass=data['setpass']))
    visual = json.loads((RESULT / 'visual_final.json').read_text(encoding='utf-8-sig'))
    report = dict(validation=json.loads((RESULT / 'validation_all.json').read_text(encoding='utf-8-sig')), geometry=geometry, models=visual['models'], lightmaps=visual['lightmaps'], static_renderers=visual['static_renderers'], hardware_tested=False)
    for name, filename in [('build','vr_build_report.json'), ('apk','apk/apk_validation.json'), ('upgrade','apk/upgrade_validation.json')]:
        path = RESULT / filename
        if path.exists():
            report[name] = json.loads(path.read_text(encoding='utf-8-sig'))
    (RESULT / 'delivery_summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    rows = '\n'.join(f"| {d['view']} | {d['triangles']:,} | {d['batches']} | {d['setpass']} |" for d in geometry)
    doc = f'''# VR 原模型画面改善 versionCode 4

更新：2026-10-08。包：`builds/UnityVR_20261008_Visual4/EngineFactoryVR.apk`，1.0.20261008.2。

## 实现

VR 使用独立生成目录 `Assets/Generated/SimPyVR/Visual4`。原 PC 模型未删除或改写。普通轻量设备共享原形网格，清洗机、液氮柜与测试设备生成三级减面网格。编辑器先清理重复拓扑与微小孤岛，再做 QEM；复杂 CAD 无法达到预算时使用空间聚类补充减面。UV、颜色、法线与操作面保留，离线计算顶点 AO。源资产依赖哈希用于缓存失效。

运行时按距离切换已有 Renderer，不做减面或每工位独立合并网格。近景进入15米、离开20米，中景进入45米、离开55米；所有工位保留远景外形，实际绘制由视锥剔除控制。

| 模型 | 近景三角形 | 中景 | 远景 |
|---|---:|---:|---:|
| 清洗机 | 19,369 | 4,530 | 1,354 |
| 液氮柜 | 11,747 | 3,874 | 1,201 |
| 测试设备 | 12,616 | 2,519 | 1,425 |

原 CAD 总面数包含隐藏组件，本轮减面输入仅包含实际显示的源几何，因此不能用全资产面数直接计算降幅。

厂房结构和装饰在编辑器生成、按材质合并，最终静态厂房11个渲染组件、1张烘焙光照贴图。导航碰撞独立于 LOD。相机远裁剪350米，160/350米同视角对照确认原远墙裁剪问题。SDK 定位层保持启用。设备采用轻量光照与顶点 AO；无实时阴影、反射或后处理。贴图副本限制1024并启用 mipmap/Android压缩。

## 检查结果

79个绑定、模型预算、共享网格、AO、材质、远墙、烘焙光照、静态厂房可见性、全部LOD回差检查通过。输入17项、导航29项、AGV40项，以及PC布局/工位朝向、真实网页重新排产与共享时钟回归通过。测试后恢复原网页参数、暂停位置和速度。四个受保护的PC场景/画质文件哈希一致。

以下是编辑器单目视锥几何和参考批次，不是头显渲染性能：

| 视角 | 三角形 | Batches | SetPass |
|---|---:|---:|---:|
{rows}

采样均低于50万三角形、250批次、80 SetPass；入口SetPass正好80。贴图/材质/阴影没有缺失检查错误。真机双眼效果和15分钟CPU/GPU帧时间未测。

## 交付与复测

安装、手柄、性能记录导出见 `builds/UnityVR_20261008_Visual4/测试说明.md`，四组同视角对照见同目录 `画面对比.md`。APK沿用同包名与签名，旧包保留。

复测入口：`python -X utf8 -m tools.unity_vr_visual4_validation --phase all --web-sync`。结果位于 `results/unity_validation/vr_visual_v4_20261008`。真机记录组件仅在设备VR模式加入，30秒预热+900秒采样，缺失XR计时数据不判断为通过。
'''
    (ROOT / 'docs/UNITY_VR_VISUAL4.md').write_text(doc, encoding='utf-8')
    history = ROOT / 'docs/UNITY_VR_OPTIMIZATION.md'
    content = history.read_text(encoding='utf-8-sig')
    note = '最新：VR 原模型与远景改善已更新至 **versionCode 4**，见 [实现与验证记录](UNITY_VR_VISUAL4.md)。安装包位于 `builds/UnityVR_20261008_Visual4`。以下版本 3 及更早内容为历史记录。\n\n'
    if note not in content:
        content = content.replace('# VR 工厂场景优化\n\n', '# VR 工厂场景优化\n\n' + note, 1)
        history.write_text(content, encoding='utf-8')

if __name__ == '__main__':
    main()
