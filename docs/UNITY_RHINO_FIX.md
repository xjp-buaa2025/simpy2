# Rhino X Pro 输入与画面修复

2026-10-08。工程：`C:/AllUnityProjects/MainProject/MainProject`。

## 输入

导航新增 `SimPyVRInput`，优先读取现有 InputActionManager 的头部姿态状态，以及左右 ActionBasedController 实际引用的姿态 Actions。原 CenterEye TrackedPoseDriver 和左右手追踪组件保留。VR 独立摇杆／点击／B 键 Actions 使用 controller usage 绑定，摇杆读取未处理值，死区仅在导航中处理。

无绑定时枚举 Unity XR 设备，头部查询 CenterEye／HeadMounted；状态字段缺失时使用有效姿态数据。追踪标志优先于旧接口单独的 isTracked 判断。明确丢失头部追踪时停止移动；左手射线需要左手姿态，右杆操作不依赖右手位置。断连、追踪恢复、暂停和复位都需要回中。

导航诊断显示来源、原始左右摇杆值、点击、追踪标志和阻断原因，启动显示，异常持续显示，B 键可打开。日志限频；输入阻断原因变化时另外记录。

## 画面与 AGV

79 个工位中远景使用 11 类共享轮廓网格，最大 108 个三角形、3 个材质；保留 22／28 米近景回差。新增陈设网格 1,716 个三角形，另有少量地面分区线和文字。静态陈设按材质合并，独立碰撞体不随显示距离隐藏。当前导航障碍 92 个（79 工位、1 AGV、12 陈设），另保留厂房边界。

AGV 保持尺寸和原轴修正，增加高可辨识的车身与安全条。新增独立 VR 任务牌，生产概况和方向／距离信息位于视野左上角，诊断位于右下方。车体与任务牌保留真实遮挡。

静态检查又发现原回放终点在设备中心，会把暂停或到站车辆藏入设备。`VrTravelRoute` 仅在 VR 简化场景启用，复制路线并把起终点投影到设备外缘；连续任务沿用前一停靠点。按仿真编号清理缓存，网页重新排产后重新计算。原回放数据、时间和 PC 路线不改变。这是流程展示路线，不是物理 AGV 路径规划。

## 验证

证据：`results/unity_validation/rhino_fix_20261008`。

- `input_chain_final.json`：17 项通过，真实 Input System 状态事件注入及 action 绑定读取；涵盖 false isTracked／有效追踪标志、原始轴、点击、B 键、缺失状态字段、追踪丢失、重连与回中解锁。
- `navigation_final.json`：原导航 29 项通过；`visual_final.json`：9 项通过。
- `agv_samples_final.json`：20 个起点、运输、到站和月末时刻，各检查实体启用／落地和从无遮挡安全观察点看到信息牌，40 项通过。临时回放测试不写共享时钟，结束恢复当前时刻。
- 入口、中部、终检、AGV 近景和 PC 截图已检查；PC 8 项回归通过。
- `native_sync/checks.json`：网页重新排产实际通讯 7 项通过；恢复原参数、事件、统计、暂停位置及速度。仿真编号因重新运行正常更新。
- APK 签名、启动入口、ARM64、XR 库、联网与包对齐检查见 `apk` 子目录。PC 原场景与画质设置哈希见最终 `delivery_summary.json`。

可复现编辑器检查：`python -m tools.unity_rhino_validation`；可选 `--web-sync` 会对守护基线临时重新排产并恢复，需要已运行的 PC 控制端。请勿在头显真实输入运行时执行编辑器合成输入检查。

## 交付限制

APK：`builds/UnityVR_20261008_RhinoFix/EngineFactoryVR.apk`，versionCode 3；旧包保留。操作与诊断见同目录 `测试说明.md`。PC 不需要重新安装包。

当前没有连接头显，尚未实测 Rhino X Pro 的真实输入、双目性能、定位及休眠恢复。编辑器注入通过只证明修复后的输入链路可工作，不能替代真机确认。
