# 工位标签稳定与 Plant Simulation 模型库接入

更新日期：2026-10-02。Unity 项目：`C:/AllUnityProjects/MainProject/MainProject`，场景 `Assets/Scenes/HelloUnity.unity`。

## 标签

- 全景标签按工序 ID 确定排列，不再随加工、等待、完成状态重新排序。
- 摄像机移动过程中沿用上次标签偏移，平滑跟随工位；停下约 0.4 秒后才进行一次避让布局。
- 拖动、缩放第一视角窗口时延后重排，释放后统一处理。
- 第一视角中的工位标签在 22–36 米范围渐隐，替代原来 28 米处直接开关。
- 第一视角起点移至通道 `(-75, 1.7, -25)`，避免被设备遮挡。XR Origin 保留。

## 设备选择

完整对应关系：`results/unity_validation/process_model_mapping.csv`，共 79 行。

| 工序含义 | 显示模型 | 工位数 |
|---|---|---:|
| 检测、校准、试验 | Inspection 检测台 | 23 |
| 预紧、轴承安装 | PressingMachine 压装设备 | 10 |
| 装配、定位、模块对接 | Repair 装配工具台 | 32 |
| 系统预装、接收、准备、冷冻装配 | WorkTable 工作台 | 10 |
| 检验包装、包装发运 | Packing 包装设备 | 2 |
| 超声波清洗、高压清洗 | 保留现有清洗设备 | 2 |

P041、D011、A001、A002、A003、A005 附加 Robot Kuka 机械臂用于展示。原工位、工厂和 AGV 均保留。点击右上角“关闭工业装饰”可恢复原蓝色工位，点击“开启工业装饰”重新显示设备。

检测台是氦质谱、动平衡、气密等工序的通用外观代理，压装设备也是液压预紧的外观代理。库中未找到专用液氮柜，P011 使用准备工作台，没有将普通模型标称为真实液氮设备。模型和机械臂不改变 SimPy 资源约束，也不包含设备工艺动画。

## 来源与导入

使用本机 Plant Simulation 15 安装目录 `C:/Program Files/Siemens/Tecnomatix Plant Simulation 15/3D/`：

- `s3d-graphics/Inspection.s3d`
- `s3d-graphics/PressingMachine.s3d`
- `s3d-graphics/Packing.s3d`
- `s3d-graphics/Repair.s3d`
- `jt-graphics/Robot Kuka.jt`
- `jt-graphics/Table2x1x1.jt`

按 plant-sim-unity-static-import 技能采用原生 JT 路线。S3D 提取其 JT_Data，再在独立的 Plant Simulation 新模型内导出 JT 9.5；当前打开的 psfile.spp 不修改。解码后转换坐标 `(x,y,z) → (x,z,y)` 并反转三角形绕序，生成独立 Unity Mesh/Prefab。

Unity 新资产放在 `Assets/PlantSimulationProcessLibrary/`；来源、导出夹具及审计放在 `PlantSimulationImport/process_library/`。源文件与导出文件的 SHA256 记录在 source_manifest.json。

6 类资产共 27 个 Mesh、29,940 个展开顶点、9,980 个三角形，解码与 Unity 几何数量及包围盒核对无差异。恢复 23 组材质参数；修复 JT 顶点属性颜色索引，避免展开后部分颜色缺失；着色前截断微小负数，避免 Gamma 转换产生黑面。包装设备保留原控制屏贴图，该平面通过几何验证后重建 UV，未宣称保留原 UV。未导入 Plant Simulation 行为逻辑或物理动画。

## 验证材料

`results/unity_validation/process_library/` 保存源清单、几何对比、颜色审计、6 类模型预览及运行快照。Unity Play 中显示 79 个工位、79 个进度条，工业装饰开关可恢复原蓝色工位。仿真更新仍通过现有 replay.json 接口。

实测固定摄像机期间仿真从 1835.997 分钟推进至 2498.644 分钟，标签布局次数保持 5 次，AGV 位置发生变化。缩放后可恢复全景；工业装饰开关两方向验证通过。跳转至下一台完工后，场景显示装配完成 5 台、终检完成 3 台、已完工 1 台，5 个发动机模型正常展示。当前停在首台完工时刻，点击界面“播放”继续。
