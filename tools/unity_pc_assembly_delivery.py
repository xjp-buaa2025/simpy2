from pathlib import Path
import json,shutil,hashlib,subprocess
P=Path('C:/AllUnityProjects/MainProject/MainProject');OUT=Path('C:/xjp/simpy2/results/unity_validation/pc_assembly_mocap_20261019');PACKAGE=Path('C:/xjp/simpy2/builds/UnityPC_20261019_AssemblyMoCap');OLD=PACKAGE.parent/'UnityPC_20261019_SubtleWorkers'
def main():
    baseline=json.loads((OUT/'protected_before.json').read_text());protected={f:hashlib.sha256((P/f).read_bytes()).hexdigest()==h for f,h in baseline.items()};assert all(protected.values());(OUT/'protected.json').write_text(json.dumps(protected,indent=2))
    checks={name:json.loads((OUT/path).read_text(encoding='utf-8-sig')) for name,path in [('assembly','assembly_summary.json'),('functional','native/full_regression.json'),('layout','layout_preview/functional_summary.json'),('hidden','hidden_support/functional_summary.json')]};assert all(x['passed'] for x in checks.values())
    cycles=json.loads((P/'SimPyValidation/pc_assembly_mocap/cycles.json').read_text());assert cycles['success'];shutil.copy2(P/'SimPyValidation/pc_assembly_mocap/cycles.json',OUT/'cycles.json');shutil.copy2(P/'SimPyValidation/pc_assembly_mocap/import.json',OUT/'import.json');shutil.copy2(P/'SimPyValidation/pc_build/build_report.json',OUT/'build_report.json')
    shutil.copytree(OLD/'VRMirrorService',PACKAGE/'VRMirrorService',dirs_exist_ok=True)
    for name in ['工厂布局使用说明.md','工厂布局模板.xlsx','模型清单.md','默认布局.json','人物素材来源与许可.txt','工作动画许可.txt']:shutil.copy2(OLD/name,PACKAGE/name)
    sources=PACKAGE/'原始装配动作';sources.mkdir(exist_ok=True);metadata=json.loads((P/'Assets/PCProduction/AssemblyMoCap/SOURCE.json').read_text(encoding='utf-8'))
    for name in ['TVBS01P03R01.bvh','TV_S01P01R01.bvh','SOURCE.json']:shutil.copy2(P/'Assets/PCProduction/AssemblyMoCap'/name,sources/name)
    for record in metadata['selected']:assert hashlib.sha256((sources/Path(record['name']).name).read_bytes()).hexdigest()==record['sha256']
    attribution="""# 装配动作来源与许可

Brenda Elizabeth Olivas-Padilla, Sotiris Manitsaris, Alina Glushkova, Dimitrios Menychtas.
Motion Capture Benchmark of Industrial Tasks for Ergonomic Assessment and European Historic Crafts. Version V01 (2021).
Centre for Robotics, MINES ParisTech, PSL Université.

来源：https://doi.org/10.5281/zenodo.5356992
许可：Creative Commons Attribution 4.0 International (CC BY 4.0)
许可条款：https://creativecommons.org/licenses/by/4.0/

原始文件：TVBS01P03R01.bvh（连接、组装部件并放置）；TV_S01P01R01.bvh（将螺钉放上电动工具并拧紧）。原文件未修改，校验值见 SOURCE.json。

集成处理：坐标与单位转换、Unity Humanoid 骨骼重定向、从原始记录选取重复操作段；上肢遮罩播放，腿、躯干、头部保持站姿。未自行制作工作关键帧、修改动作幅度、拼接操作姿态或添加接触 IK。源片段是电视生产现场记录，用于本工程的通用作业展示，不代表发动机工艺动作的精确复现。

待机姿态仍使用 KayKit Character Animations Free 1.1，Kay Lousberg，CC0；人物继续使用 Quaternius 工人，许可随包保留。
"""
    (sources/'来源与许可.md').write_text(attribution,encoding='utf-8')
    media=PACKAGE/'动作与接地预览';media.mkdir(exist_ok=True);cards=[];ffmpeg=Path('C:/xjp/simpy2/.cache/pc_cells_video/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe')
    for sid,name in [('S002','清洗工位'),('P001','装配工位'),('F013','检测工位'),('A001','总装工位')]:
        shutil.copy2(OUT/'films'/('motion_'+sid+'.mp4'),media/('motion_'+sid+'.mp4'));shutil.copy2(OUT/'assembly'/('motion_'+sid+'.png'),media/('motion_'+sid+'.png'))
        subprocess.run([str(ffmpeg),'-v','error','-i',str(media/('motion_'+sid+'.mp4')),'-f','null','-'],check=True)
        cards.append(f'<section><h2>{sid} · {name}</h2><video controls loop muted preload="metadata" poster="motion_{sid}.png" src="motion_{sid}.mp4"></video></section>')
    (media/'动作与接地预览.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>现成装配动作与接地检查</title><style>body{font:16px system-ui;background:#edf1f2;color:#25343b;max-width:1400px;margin:36px auto;padding:0 20px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(480px,1fr));gap:20px}section{background:white;padding:16px;border-radius:10px}video{width:100%}h2{font-size:18px}p{line-height:1.7}</style><h1>现成装配动作与接地检查</h1><p>使用原库的双手组装、电动工具拧紧记录。上肢播放，身体站稳；按两只鞋的实际鞋底校正高度。</p><p>以下为独立 PC 程序录制，每段约 10 秒，采样 12 FPS；录像采样频率不表示程序渲染帧率。</p><main>'+''.join(cards)+'</main><footer><p>动作：Olivas-Padilla 等，Industrial Tasks MoCap V01，<a href="https://doi.org/10.5281/zenodo.5356992">原库</a>，<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>。已做 Unity 骨骼重定向、原片段截取与上肢遮罩。原始 BVH 和处理说明随包保留。</p></footer></html>',encoding='utf-8')
    sweep=json.loads((OUT/'ground_sweep.json').read_text());counts={name:len(x['checks']) for name,x in checks.items()};rows='\n'.join(f"| {r['source']} | {r['start']:.3f}–{r['end']:.3f} 秒 | {r['handSeam']*100:.2f} cm |" for r in cycles['clips'])
    report=f"""# PC 鞋底接地与现成装配动作（2026-10-19）

## 修正

- 使用实际蒙皮后的两只鞋底计算站立高度，不再把人物根节点当作脚底。
- 检查整块鞋底占地，处理站在蓝色底座边缘时的支撑位置；随工位旋转、缩放及布局切换重新定位。
- 停用此前手臂姿态混合、动作限幅和接触 IK。工作动作来自现成工业动作捕捉库，人物保留站姿，播放原记录的肩、臂、腕和手指动作。
- 保留真实人员绑定、人数口径、暂停和拖轴同步。工位坐标、设备、AGV、网页接口及 VR 保持原状。

## 动作来源及片段

原库：Motion Capture Benchmark of Industrial Tasks for Ergonomic Assessment and European Historic Crafts，MINES ParisTech，CC BY 4.0。包含真实电视装配现场的双手组装与电动工具拧紧。原始 BVH 文件、作者、许可和 SHA-256 随包提供。

原记录的 90 FPS 数据经 Unity Humanoid 重定向。为减少重复播放的首尾跳变，从原记录选取操作段；段内关键帧和播放节奏沿用来源，未合成新动作。片段首尾仍可能有轻微差异，未通过修改关节轨迹消除差异。

| 动作 | 来源内时间段 | 首尾手部距离（编辑器参考） |
|---|---|---:|
{rows}

本项目将其作为通用作业示意，不表示准确的发动机工艺手势或真实手工具接触精度。

## 验证

- 79 个工位的实际人员任务逐站验证，两只鞋底到地坪／蓝色底座顶面的误差均通过 ≤2 mm 门槛；另检查四段录像的连续采样。该误差是渲染网格到支撑面的计算值。
- 装配、接地与播放检查 {counts['assembly']} 项通过；功能回归 {counts['functional']} 项通过；布局旋转、缩放、预览及取消 {counts['layout']} 项通过；隐藏全部／单个设备接地检查 {counts['hidden']} 项通过。
- 暂停、拖轴、工位特写、工区视角、人员去重、AGV、第一视角、完工统计和 1366／1920／2560 三种界面尺寸已检查。
- 视频全部解码通过。构建 0 错误、31 条既有 SDK／凸碰撞体警告。
- PC_Main、FactoryContent、VR_Main、FactoryVRContent、全局画质及原人物 prefab 校验值保持不变。旧包保留，无需更新 APK。

本轮使用隔离服务 8042，未修改正式 8000 服务的生产时钟。未重复 15 分钟性能测试，也没有头显真机测试。

## 使用

关闭旧程序后运行本目录 EngineFactoryPC.exe；复制到其他电脑时复制整个目录。打开“动作与接地预览/动作与接地预览.html”查看录像。

完整来源及许可见“原始装配动作/来源与许可.md”。
"""
    (PACKAGE/'本次更新与测试说明.md').write_text(report,encoding='utf-8');(OUT/'交付报告.md').write_text(report,encoding='utf-8')
    for name in ['assembly_summary.json','ground_sweep.json','cycles.json','import.json','build_report.json','protected.json']:shutil.copy2(OUT/name,media/name)
    summary=dict(checks=counts,stations=len(sweep),max_sole_gap_m=max(sweep.values()),package=str(PACKAGE));(OUT/'delivery_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
