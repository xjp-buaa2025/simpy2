"""Assemble evidence and user-facing notes for the PC-only bright factory release."""
from pathlib import Path
import json, shutil, hashlib, html

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/unity_validation/pc_bright_20261017'
PACKAGE=ROOT/'builds/UnityPC_20261017_Bright'
PROJECT=Path('C:/AllUnityProjects/MainProject/MainProject')

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def main():
    perf=read(OUT/'native_control/soak15.performance.json')
    segments=read(OUT/'native_control/soak15.segments.json')['segments']
    assert perf['completed'] and perf['seconds']>=900
    assert all(s['focused'] for s in segments), 'Foreground benchmark lost focus'
    functional=read(OUT/'native/full_regression.json')
    integration=read(OUT/'integration/functional_summary.json')
    mirror=read(OUT/'mirror_regression.json')
    vr=read(OUT/'vr/smoke_summary.json')
    assert all(x['passed'] for x in [functional,integration,mirror,vr])
    protected={}
    for path,digest in read(OUT/'protected_before.json').items():
        actual=hashlib.sha256((PROJECT/path).read_bytes()).hexdigest()
        protected[path]=dict(unchanged=actual==digest,sha256=actual)
    assert all(p['unchanged'] for p in protected.values())
    (OUT/'protected_after.json').write_text(json.dumps(protected,indent=2),encoding='utf-8')
    by_resolution={}
    for width in [1920,2560]:
        rows=[r for r in segments if r['width']==width]
        by_resolution[str(width)]=dict(seconds=sum(r['seconds'] for r in rows),
            average_fps=sum(r['frames'] for r in rows)/sum(r['seconds'] for r in rows),
            lowest_30s_fps=min(r['fps'] for r in rows),
            highest_segment_p95_ms=max(r['p95_ms'] for r in rows),
            segments=len(rows))
    summary=dict(performance=perf,by_resolution=by_resolution,
        native_checks=len(functional['checks']),integration_checks=len(integration['checks']),
        mirror_checks=len(mirror['checks']),vr_hardware_tested=False,protected=protected)
    (OUT/'delivery_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    shutil.copy2(PROJECT/'SimPyValidation/pc_build/build_report.json',OUT/'build_report.json')
    for name in ['cook','agv_cook','setup']:
        shutil.copy2(PROJECT/f'SimPyValidation/pc_bright/{name}.json',OUT/f'{name}.json')
    evidence=PACKAGE/'画面对比与测试'
    evidence.mkdir(exist_ok=True)
    pairs=[('全景','before/bright_baseline.png','native/overview.png'),
           ('清洗工位','before/focus_S002.png','native/focus_S002.png'),
           ('检测工位','before/focus_F013.png','native/focus_F013.png'),
           ('龙门架','before/focus_A001.png','native/focus_A001.png')]
    sections=[]
    for index,(label,before,after) in enumerate(pairs):
        names=[]
        for suffix,source in [('before',before),('after',after)]:
            name=f'{index}_{suffix}.png';shutil.copy2(OUT/source,evidence/name);names.append(name)
        sections.append(f'<section><h2>{html.escape(label)}</h2><div class="pair"><figure><figcaption>优化前</figcaption><img src="{names[0]}" loading="lazy"></figure><figure><figcaption>优化后</figcaption><img src="{names[1]}" loading="lazy"></figure></div></section>')
    for label,name in [('本地漫游：完整厂房','local_preview'),('AGV 与载物台','agv_follow')]:
        shutil.copy2(OUT/f'native/{name}.png',evidence/f'{name}.png')
        sections.append(f'<section><h2>{label}</h2><img src="{name}.png" loading="lazy"></section>')
    gallery='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>PC 明亮厂房画面对比</title><style>body{background:#e7edf0;color:#23323c;font:16px/1.65 system-ui;margin:28px auto;max-width:1600px;padding:0 20px}h1,h2{line-height:1.3}.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}figure{margin:0}img{width:100%;border-radius:8px}section{margin:36px 0}figcaption{font-weight:600;margin:8px}aside{padding:16px;background:white;border-radius:8px}@media(max-width:900px){.pair{grid-template-columns:1fr}}</style><h1>PC 明亮真实厂房 · 画面对比</h1><aside>全景使用相同回放时间、分辨率、朝向和 FOV；自动取景位置相差约 0.14 米。特写为同一工位与事件，优化后调整了操作面机位，不能作为完全相同相机的像素对比。布局坐标保持原样，因此全厂仍保留原有通道和设备间距。</aside>'''+''.join(sections)+'</html>'
    (evidence/'画面对比.html').write_text(gallery,encoding='utf-8')
    def f(width,key):return by_resolution[str(width)][key]
    report=f'''# PC 明亮厂房升级：交付与验证

## 已完成

- PC 独立材质副本恢复原模型颜色、顶点色、贴图和透明参数；金属、喷漆、橡胶、玻璃与屏幕分别保留材质层次。
- 浅灰纹理地坪、柔和主光与补光、PC 专属厂房烘焙光照、静态反射和设备接触阴影；轻量 AO、泛光及中性色调。
- 全景隐藏顶棚和近侧墙，漫游相机显示完整柱梁、墙板、门、窗带及顶灯；原厂房与模型保留。
- 工装、安全帽、手套人员替换机器人外观，继续使用真实 worker_ids 和暂停、拖轴、变速驱动；调整操作点与手部目标。
- 空闲工位使用紧凑标记；加工、等待及选中工位展开信息；全部名称模式、工区、特写及现有图表保留。
- PC 模型合并材质等价零件并共享资源，保留设备形状与源文件。发动机 604 个渲染对象合并为 4 组；AGV 2,835 个有效渲染对象合并为 6 组。载物箱按车体顶部落位，测试间隙约 1 厘米。

## 性能实测

Windows 独立 EXE，RTX 5070 Ti / Core Ultra 7 265K，高画质、目标帧率 60、VSync 关闭；持续 {perf['seconds']:.1f} 秒，所有 30 秒采样窗口均保持前台。
每 30 秒切换全景、清洗、检测、龙门架特写及本地漫游，并跳转回放位置、以 20 倍速度播放。分辨率在 1080p 和 1440p 间轮换。

| 分辨率 | 有效采样秒数 | 加权平均 FPS | 最低 30 秒平均 FPS | 各窗口 P95 的最高值 |
|---|---:|---:|---:|---:|
| 1920×1080 | {f(1920,'seconds'):.1f} | {f(1920,'average_fps'):.2f} | {f(1920,'lowest_30s_fps'):.2f} | {f(1920,'highest_segment_p95_ms'):.2f} ms |
| 2560×1440 | {f(2560,'seconds'):.1f} | {f(2560,'average_fps'):.2f} | {f(2560,'lowest_30s_fps'):.2f} | {f(2560,'highest_segment_p95_ms'):.2f} ms |

全程平均 {perf['average_fps']:.2f} FPS，帧间隔 P95 {perf['p95_frame_ms']:.2f} ms，最大单帧 {perf['max_frame_ms']:.2f} ms。
Unity 分配内存 {perf['allocated_start']/2**30:.2f} → {perf['allocated_end']/2**30:.2f} GiB；进程私有内存 {perf['private_start']/2**30:.2f} → {perf['private_end']/2**30:.2f} GiB。
帧时间包括镜头/分辨率切换；表中窗口 P95 最高值不是全程 P95。CPU/GPU FrameTiming 在此包不可用，不把帧间隔当作 GPU 执行时间。
原版同机 1080p 前台全景短测约 26.5 FPS（20 秒）；新版短测约 60 FPS。不同长度的短测只作参考，以本次连续测试数据为主。

## 功能与兼容

- 独立 EXE：{len(functional['checks'])} 项检查通过，覆盖 79 工位、工位点击/特写、环绕、缩放、返回全景、工区、AGV、暂停/拖轴、过滤、三种 UI 分辨率和材质有效性。
- 真实隔离 SimPy 服务：{len(integration['checks'])} 项检查通过，覆盖布局发布/回退/版本冲突、网页重新排产、每日工作时间、月末计数、自定义名称保留与旧数据兼容。
- 独立打包回传服务：{len(mirror['checks'])} 项检查通过，包括冷启动、首帧展开、JPEG 接收和退出清理；使用测试图片源，不能替代头显真实采集测试。
- 现有 VR 场景编辑器冒烟通过，未连接 Rhino X Pro。VR 场景、FactoryContent、FactoryVRContent、全局画质和层配置哈希保持不变；本轮没有 APK。
- 构建成功，0 错误，31 条既有 SDK 废弃接口/凸碰撞网格警告。旧 PC 包保留。

## 使用

1. 关闭旧版 PC 程序，运行本目录 EngineFactoryPC.exe。复制到其他电脑时复制整个目录。
2. 正常启动沿用已保存的 SimPy 地址；本轮测试地址通过专用命令行与测试配置隔离，未写入普通 EXE 配置。
3. 单击工位设备或标签看特写；右键环绕，滚轮缩放，Esc 或“返回全景”退出；“工区视角”查看区域。
4. V 打开/收起第一视角，本地漫游继续使用 WASD；显示设置中可切换高/标准画质和全部名称。
5. 双击“画面对比与测试/画面对比.html”查看前后图；测试原始 JSON 同目录保留。

## 范围和限制

保持现有工位坐标、占地、AGV 停靠点及生产逻辑，因此没有通过缩小厂房或压缩站距制造密集视觉效果。
静态厂房烘焙光照不随布局重烘焙，可移动设备使用独立光照与随站点移动的接触阴影。
人员是生产展示动作，不进行跨工位寻路；工装人物源模型为低多边形风格。
回归期间曾因旧 PC 窗口快捷键误触导致生产回放短暂继续，已暂停并恢复到原 8230.161 分钟、速度 10；未重新排产。完整观察/恢复记录在证据目录。之后测试全部使用隔离服务。

## 人物来源

Worker by Quaternius，Ultimate Modular Men Pack，CC0 1.0。
https://quaternius.com/packs/ultimatemodularcharacters.html
https://creativecommons.org/publicdomain/zero/1.0/
人物经过 PC 专用工作服材质、手套和动作适配；其他原项目资源继续沿用其原许可。
'''
    (OUT/'交付与测试报告.md').write_text(report,encoding='utf-8')
    (ROOT/'docs/UNITY_PC_BRIGHT.md').write_text(report,encoding='utf-8')
    (PACKAGE/'新版使用与测试说明.md').write_text(report,encoding='utf-8')
    for source in [OUT/'delivery_summary.json',OUT/'build_report.json',OUT/'native/full_regression.json',OUT/'integration/functional_summary.json',OUT/'mirror_regression.json',OUT/'protected_after.json',OUT/'native_control/soak15.performance.json',OUT/'native_control/soak15.segments.json']:
        target='integration_summary.json' if source.parent.name=='integration' else source.name
        shutil.copy2(source,evidence/target)
    shutil.copy2(PROJECT/'Assets/PCProduction/WorkerSource/SOURCE_AND_LICENSE.txt',PACKAGE/'人物素材来源与许可.txt')
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
