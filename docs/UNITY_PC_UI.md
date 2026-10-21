# Unity PC 界面说明

更新日期：2026-10-05。PC 界面围绕工厂全景、生产状态和回放控制重新组织。

## 新布局

| 区域 | 内容 |
| --- | --- |
| 顶部 | 工作日时间、已完工/目标、在制发动机、等待发动机、连接状态 |
| 场景上方 | 发动机筛选、第一视角、AGV 跟随、恢复全景、显示设置、生产详情 |
| 右上 | 工位状态图例与数量；设备颜色始终表示全线状态 |
| 右侧抽屉 | 工位、发动机、AGV、帮助四个页签；长内容可用滚轮查看 |
| 底部 | 播放/暂停、回到起点、时间轴、速度、跳转和帮助 |

第一视角和详情默认收起。速度、跳转、显示设置及发动机筛选使用菜单；打开菜单会收起详情，打开详情会关闭菜单，避免浮层相互遮挡。工位标签继续采用自适应显示，并避让当前可见的界面面板。

示例：[1920×1080 默认全景](C:/xjp/simpy2/results/unity_validation/pc_ui_20261005/default_1920.png)、[工位详情](C:/xjp/simpy2/results/unity_validation/pc_ui_20261005/drawer_station.png)。

## 操作

- 全景：滚轮缩放，右键旋转；点击工位或标签查看工序详情。
- 回放：`Space` 播放/暂停，`Home` 回到起点；`PageUp` / `PageDown` 调节速度。底部时间轴可拖动，“跳转”可到下一工序完成或下一台发动机完工，并暂停。
- `F` 切换 AGV 跟随；“恢复全景”复位观察角度和漫游窗口位置。
- `V` 展开/收起“第一视角漫游”。点击小窗后，用 `WASD` 移动，右键或 `Q` / `E` 转向，`Shift` 加速，`R` 复位，`Esc` 退出漫游。窗口可拖动、缩放；工位详情中的观察按钮可定位到对应工位。
- 第一视角收起时，其独立预览摄像机停用；展开时恢复渲染。RenderTexture 保留供再次展开使用。

## 状态和统计怎么读

| 显示项 | 含义 |
| --- | --- |
| 第 N 工作日、班内时间 | 按 SimPy 每日工时和月工作日数换算，使用工作日序号 |
| 已完工 / 目标 | 当前回放时刻完成全部工序的发动机数 / 月度计划目标；实际排产可能超过目标 |
| 在制发动机 | 已出现仿真事件、尚未全部完工的发动机数 |
| 等待发动机 | 当前存在等待事件的去重发动机数；一个发动机可以同时在另一道工序加工 |
| 装配完成、终检完成 | 各自阶段的完成数，与全部工序完工分开显示在发动机详情中 |
| 工位图例数量 | 全线工位当前的加工、等待、人员休息和空闲数量 |

蓝色表示加工，黄色表示等待，紫色表示人员休息或返工，灰色表示空闲，绿色表示刚完成或筛选产品已完成。返工工位计入“加工”数量，具体情况查看工位标签及详情。

发动机筛选改变标签及相关展示；设备颜色仍表示全线状态。AGV 继续用于发动机 1 的工序流程演示，展示运输不决定工序开工。发动机模型的阶段外观是示意，完工计数来自仿真工序数据。

连接状态可点击查看数据来源、运行编号和共享时钟状态。回放控制仍遵守 PC 主控权限；只读跟随时可查看场景，不能更改共享回放。

## 代码入口与保留内容

- [SimPyReplayPCConsole.cs](C:/AllUnityProjects/MainProject/MainProject/Assets/Scripts/SimPyReplayPCConsole.cs)：PC 面板、菜单、抽屉、样式和统计展示。
- [SimPyReplayFirstPerson.cs](C:/AllUnityProjects/MainProject/MainProject/Assets/Scripts/SimPyReplayFirstPerson.cs)：漫游窗口、摄像机和输入；提供 `SetFirstPersonWindowVisible(bool)`、`ToggleFirstPersonWindow()`。
- [SimPyReplayRuntime.cs](C:/AllUnityProjects/MainProject/MainProject/Assets/Scripts/SimPyReplayRuntime.cs)：共享仿真状态、PC UI 初始化和更新。Experience 负责工位交互及详情，Presentation 负责发动机阶段，Sync / Clock 负责数据和时钟联动。

继续使用 `PC_Main` / `VR_Main` 入口及共享 `FactoryContent`。原场景、工位、模型和工序绑定保留；本次界面调整不删除模型，也不改变 SimPy 排产算法。PC 样式独立于 VR 世界空间标签，数据和共享时钟接口维持现有协议。

## 验收记录

证据来自真实 Unity Editor 运行状态和截图，目录为 [pc_ui_20261005](C:/xjp/simpy2/results/unity_validation/pc_ui_20261005)。

- 已完成：**24 / 24 项功能场景通过，0 项失败，所有场景警告为 0**。覆盖 1366×768、1920×1080、2560×1440，四个菜单、四个详情页、第一视角开关、月末计数、复位、速度、跳转、发动机筛选、AGV 跟随、恢复全景，以及镜头移动、1366 宽度抽屉和全部名称显示。
- 三种默认全景均保留 79 个工位标签；记录中未发现 PC 面板越界、PC 文本溢出、标签重叠或标签被面板遮挡。真实点击“全部名称”后保留 79 个完整工序名称；1366×768 的详情抽屉也通过检查。
- 镜头朝向从 15° 移动至 23°，连续采样 90 帧：标签显隐变化、标签偏移变化、布局重排均为 0；镜头停稳 1.2 秒后重排 1 次。最终 79 个标签可见，重叠、界面遮挡和文字溢出均为 0。这是所测移动场景的结果，不代表所有视角条件均已覆盖。
- 原生 `W` 键操作使第一视角移动约 0.329 个世界单位，共享回放时刻保持在 2950 分钟；时间轴真实拖动从 2950 分钟到约 5626.72 分钟，速度为 60 分钟/秒，完工数为 4，预览窗口及其摄像机均关闭。证据：[漫游前](C:/xjp/simpy2/results/unity_validation/pc_ui_20261005/native_before_walk.json)、[漫游后](C:/xjp/simpy2/results/unity_validation/pc_ui_20261005/native_after_walk.json)、[时间轴拖动](C:/xjp/simpy2/results/unity_validation/pc_ui_20261005/native_timeline_drag.json)。
- 第一视角开关记录确认摄像机启停跟随窗口。
- 基准排产月末显示实际完工 **5 台 / 目标 3 台**，与该次排产结果一致。
- 网页更新与恢复同步：通过真实 `/api/simulation/run` 将每日工时 8→6、月工作日 22→15、目标 3→5，并修改 F012 名称。Unity 更新正确；79 个工位完成数、8 个加工工位状态与进度和当前/月末完工数与新时间戳一致。测试后恢复原输入，工位与事件数组、产量和工作日均已核对。证据：[web_sync_checks.json](C:/xjp/simpy2/results/unity_validation/pc_ui_20261005/web_sync_checks.json)。
- VR Editor 对照：79 个工位、12 个附近标签、1 个观察相机；桌面 Canvas 为 0，预览 RenderTexture 未创建；第 2950 分钟和速度 20 跟随一致。PC 主控退出后保留最近时刻，VR 无控制权限。证据：[pc_ui_vr_20261005.json](C:/xjp/simpy2/results/unity_validation/pc_ui_20261005/pc_ui_vr_20261005.json)。这不代表 VR 真机或 APK 已验收。
- 本次未做优化前后的性能对照基准，不宣称帧率提升。

详细记录：[validation_summary.json](C:/xjp/simpy2/results/unity_validation/pc_ui_20261005/validation_summary.json)。

## Windows PC 包

修正版输出：[EngineFactoryPC.exe](C:/xjp/simpy2/builds/UnityPC_20261005_Fixed/EngineFactoryPC.exe)。移动时复制整个 Fixed 目录，不能只复制 EXE；SimPy 服务需单独运行。操作见 [README_PC.md](C:/xjp/simpy2/builds/UnityPC_20261005_Fixed/README_PC.md)。旧包存在着色器漏包，已标记保留作问题对照。

修正版 Windows 64 位正式构建成功，入口为 PC_Main + FactoryContent，资源 1,496,830,353 字节，构建错误 0；25 条模型/场景等警告保存在 [pc_build_fixed_report.json](C:/xjp/simpy2/results/unity_validation/pc_ui_20261005/repair/pc_build_fixed_report.json)。当前编辑器目标平台为 Windows；以后打 VR APK 时仍需切回 Android 并选择 VR 构建场景。

用户运行旧包后的日志确认 Unlit/Color 缺失，引发 AGV 定位灯材质创建异常并中断展示初始化。项目已明确保留该着色器，加入构建前校验，并完成 Windows 目标下 24 项编辑器复查。详见 [构建异常修复](C:/xjp/simpy2/docs/UNITY_PC_BUILD_FIX.md)。随后用户启动修正版，独立 EXE 日志与后台时钟确认初始化和新排产通信正常。新增窗口/全屏选择及窗口缩放，见 [PC 通信与窗口记录](C:/xjp/simpy2/docs/UNITY_PC_WINDOW_AND_SYNC.md)。
