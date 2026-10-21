"""Build the local PC release gallery and report from completed acceptance evidence."""
from pathlib import Path
import json,shutil,hashlib,html
from tools.unity_pc_cells_validation import OUT,PACKAGE
PROJECT=Path('C:/AllUnityProjects/MainProject/MainProject')
ROOT=OUT.parents[2]

def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))

def main():
    perf=read(OUT/'native_control/soak15.performance.json');segments=read(OUT/'native_control/soak15.segments.json')['segments']
    assert perf['completed'] and perf['seconds']>=900 and all(s['focused'] for s in segments)
    native=read(OUT/'native/full_regression.json');integration=read(OUT/'integration/functional_summary.json');preview=read(OUT/'layout_preview/functional_summary.json');mirror=read(OUT/'mirror_regression.json');motion=read(OUT/'motion_summary.json')
    assert all(x['passed'] for x in [native,integration,preview,mirror]);assert all(x['valid_contacts']>0 and x['max_error']<=.03 for x in motion.values())
    baseline=read(OUT.parent/'pc_bright_20261017/protected_before.json');protected={k:hashlib.sha256((PROJECT/k).read_bytes()).hexdigest()==v for k,v in baseline.items()};assert all(protected.values())
    (OUT/'protected.json').write_text(json.dumps(protected,indent=2))
    by_resolution={}
    for width in [1920,2560]:
        rows=[s for s in segments if s['width']==width]
        by_resolution[width]=dict(seconds=sum(s['seconds'] for s in rows),fps=sum(s['frames'] for s in rows)/sum(s['seconds'] for s in rows),lowest=min(s['fps'] for s in rows),p95_highest=max(s['p95_ms'] for s in rows))
    scene=read(OUT/'after/overview.json');lod=read(PROJECT/'SimPyValidation/pc_cells/lod_audit.json')
    summary=dict(performance=perf,by_resolution=by_resolution,native_checks=len(native['checks']),integration_checks=len(integration['checks']),preview_checks=len(preview['checks']),mirror_checks=len(mirror['checks']),motion=motion,protected=protected,cell_props=scene['cell_props'],shared_groups=scene['cell_shared_groups'])
    (OUT/'delivery_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    evidence=PACKAGE/'画面对比与动作';evidence.mkdir(exist_ok=True)
    sections=[];camera_deltas={}
    for key,label in [('overview','全厂全景'),('area','清洗工区'),('washer','清洗工位'),('nitrogen','压装工位'),('test','检测工位'),('assembly','龙门架工位')]:
        for suffix in ['before','after']:shutil.copy2(OUT/suffix/(key+'.png'),evidence/(key+'_'+suffix+'.png'))
        b=read(OUT/'before'/(key+'.json'));a=read(OUT/'after'/(key+'.json'));camera_deltas[key]=sum((a['camera_position'][axis]-b['camera_position'][axis])**2 for axis in ['x','y','z'])**.5
        sections.append(f'<section><h2>{label}</h2><div class="pair"><figure><figcaption>调整前</figcaption><a href="{key}_before.png"><img src="{key}_before.png" loading="lazy"></a></figure><figure><figcaption>调整后</figcaption><a href="{key}_after.png"><img src="{key}_after.png" loading="lazy"></a></figure></div></section>')
    for sid,label in [('S002','清洗机操作'),('P011','密封环冷冻安装'),('F013','氦质谱检测'),('P001','转子叶片装配'),('A001','龙门架对接作业')]:
        source=OUT/'films'/('motion_'+sid+'.mp4');shutil.copy2(source,evidence/source.name)
        sections.append(f'<section><h2>{sid} · {label}</h2><video controls preload="metadata" src="{source.name}"></video></section>')
    gallery='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>PC 生产单元与人物动作</title><style>body{font:16px/1.65 system-ui;background:#edf1f4;color:#233541;max-width:1600px;margin:28px auto;padding:0 22px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}figure{margin:0}figcaption{font-weight:600;margin:8px}img,video{width:100%;border-radius:8px}section{margin:36px 0}aside{background:white;padding:18px;border-radius:8px}@media(max-width:900px){.pair{grid-template-columns:1fr}}</style><h1>PC 工人动作与生产单元 · 前后对比</h1><aside>对比图采用相同仿真时间、分辨率及取景流程。保留原工位坐标，补充工装、备料、工具柜和工区分区。下方为真实 PC 程序录制的动作片段（约 10 秒，录制目标 12 FPS），不是头显画面；精确接触点属于生产展示示意。</aside>'''+''.join(sections)+'</html>'
    (evidence/'画面对比与动作.html').write_text(gallery,encoding='utf-8')
    def f(w,k):return by_resolution[w][k]
    contact=max(x['max_error'] for x in motion.values())*1000
    lod_lines='\n'.join('| '+r['name']+' | '+' | '.join(f'{n:,}' for n in r['triangles'])+' |' for r in lod['rows'])
    report=f'''# PC 工人动作与生产单元升级（2026-10-18）

## 使用效果

- 生产详情显示“当前投入 N 人”，按当前加工记录去重统计，排除休息事件；缺少人员字段时显示“暂无人员数据”。不再显示员工编号或动作名称。
- 装配、单手面板、俯身检测、待机、休息采用五个 PC 专用动画片段。接触阶段加入手部位置和掌面朝向修正；多人分开操作与观察，休息人员使用独立侧边位置。
- 人物保留真实 worker_ids 和统一身高。暂停冻结动作，拖动时间轴定位新姿态，播放速度限制在自然范围；不可达目标采用放松站姿。
- 当前默认布局生成 {scene['cell_props']} 个附属设施，其中共享备料点 {scene['cell_shared_groups']} 个，包含工作台、独立工具洞洞板、承托架和料架。为全部工位整理单元分区，空间不足处减少附件。
- 保留现有 79 个工位的坐标、朝向、主设备尺寸和 AGV 停靠点；厂房仍保持原有尺度与通道间距，通过生产单元组织减少零散感。

## 性能与资源

RTX 5070 Ti / Core Ultra 7 265K，独立 EXE 高画质，目标 60 FPS、VSync 关闭。连续 {perf['seconds']:.1f} 秒，30 秒窗口交替全景、清洗/检测/龙门架特写及本地漫游，1080p 与 1440p 轮换；全部采样窗口均在前台。

| 分辨率 | 采样秒数 | 平均 FPS | 最低 30 秒平均 | 窗口 P95 最高值 |
|---|---:|---:|---:|---:|
| 1920×1080 | {f(1920,'seconds'):.1f} | {f(1920,'fps'):.2f} | {f(1920,'lowest'):.2f} | {f(1920,'p95_highest'):.2f} ms |
| 2560×1440 | {f(2560,'seconds'):.1f} | {f(2560,'fps'):.2f} | {f(2560,'lowest'):.2f} | {f(2560,'p95_highest'):.2f} ms |

全程平均 {perf['average_fps']:.2f} FPS，帧间隔 P95 {perf['p95_frame_ms']:.2f} ms，最大单帧 {perf['max_frame_ms']:.2f} ms。
Unity 分配内存 {perf['allocated_start']/2**30:.2f} → {perf['allocated_end']/2**30:.2f} GiB；进程私有内存 {perf['private_start']/2**30:.2f} → {perf['private_end']/2**30:.2f} GiB。保留切换时的波动，未将窗口最高 P95 当作全程 P95。
当前包无法取得可靠的独立 CPU/GPU FrameTiming，因此不把帧间隔当作 GPU 执行时间。

首轮连续测试发现全景加本地漫游约 37～40 FPS；已为 PC 附属模型增加分级副本，并限制漫游相机对 45 米外小型附件的绘制。主设备和厂房仍显示，近景保留原模型；工区线合并为一个共享网格。优化前原始记录保留在证据目录。

| 附属模板 | 近景原模型三角形 | 中景副本 | 远景副本 |
|---|---:|---:|---:|
{lod_lines}

## 验证结果

- 客户端 {len(native['checks'])} 项检查通过：工位选择、环绕、全景/工区、暂停/拖轴/变速、真实人员绑定、人数口径、材质、接地、附件避让和三种 UI 分辨率。
- 真实隔离 SimPy 服务的 {len(integration['checks'])} 项发布/回退/版本冲突/重新排产/旧数据兼容检查通过。测试使用 8042，普通连接配置沿用原值。
- 另有 {len(preview['checks'])} 项预览与取消检查通过，包含 17° 旋转、1.1 倍缩放及连续五次切换；预览不发布，取消恢复原布局和时间。
- 五类工位动作采样通过，接触阶段手部控制点到配置接触点的最大误差约 {contact:.2f} 毫米。该数值是骨骼控制点误差，不能替代真实装配精度；录像同时检查脚底、手腕、多人和休息位置。
- 回传服务 {len(mirror['checks'])} 项检查通过，测试图片源接收采样（包含冷启动窗口）为 {', '.join(str(x) for x in mirror['received_fps'])} FPS，按 HTTP 429 进行 {mirror.get('expected_rate_backoffs',0)} 次退避，无其他上传错误。测试源、服务及关闭清理正常；未连接头显，不能代替真实图像采集验收。
- VR_Main、FactoryVRContent、FactoryContent、全局画质及层配置校验值保持不变；原 FBX 保留。本轮没有 APK，也没有头显真机测试。
- 构建成功，0 错误，31 条既有 SDK/凸碰撞网格警告。旧 PC 包保留。

最终重建仅调整专用验收入口，使预览期间也能调用取消操作；生产渲染、人物动画及资源与上述性能测试版本一致。原生鼠标取消检查受到 Windows 首次网络访问提示遮挡，改由相同 UI 处理函数的验收入口验证，未操作系统网络权限。

## 启动与查看

1. 关闭旧版 PC 程序，运行本目录 EngineFactoryPC.exe；复制到其他电脑时复制整个目录。
2. 首次运行如出现 Windows 网络访问提示，请自行确认所需权限；局域网发现与回传需要允许相应网络访问。
3. 点击设备或标签查看生产特写，右键环绕、滚轮缩放；Esc 返回全景。
4. “工区视角”查看单元组织；V 打开本地漫游或现有 VR 回传小窗。
5. 双击“画面对比与动作/画面对比与动作.html”查看前后图和五段动作视频。

人员动作属于生产过程展示，没有增加跨工位寻路，也不改变工序耗时。PC 单元配置和动画保存在 Assets/PCProduction/ProductionCells；继续复用 Quaternius CC0 人物，许可文件随包提供。
'''
    (PACKAGE/'新版使用与测试说明.md').write_text(report,encoding='utf-8');(OUT/'交付与测试报告.md').write_text(report,encoding='utf-8');(ROOT/'docs/UNITY_PC_PRODUCTION_CELLS.md').write_text(report,encoding='utf-8')
    (OUT/'comparison_camera_deltas.json').write_text(json.dumps(camera_deltas,indent=2))
    for src,name in [(OUT/'native/full_regression.json','客户端检查.json'),(OUT/'integration/functional_summary.json','排产联动检查.json'),(OUT/'layout_preview/functional_summary.json','布局预览检查.json'),(OUT/'motion_summary.json','动作接触检查.json'),(OUT/'mirror_regression.json','回传检查.json'),(OUT/'native_control/soak15.performance.json','连续性能.json'),(OUT/'native_control/soak15.segments.json','连续性能分段.json'),(OUT/'delivery_summary.json','交付汇总.json'),(OUT/'protected.json','兼容校验.json'),(PROJECT/'SimPyValidation/pc_build/build_report.json','构建报告.json'),(PROJECT/'SimPyValidation/pc_cells/lod_audit.json','附属模型分级.json')]:shutil.copy2(src,evidence/name)
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
