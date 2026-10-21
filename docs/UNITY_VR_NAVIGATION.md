# 工位朝向与 VR 导航交付

更新：2026-10-08。工程：`C:/AllUnityProjects/MainProject/MainProject`。

## 实现

- `SimPyStationOrientation.cs` 保存 79 个工位的朝向，参考固定通道位置；P012 朝北，D001 朝南，D042、B002 朝西。PC、VR 共享配置，不从回放运输路线推导方向。
- 2026-10-09 几何复查修正：清洗机、液氮柜、测试台及备用六自由度云台的竖直轴应为 X=0°；工具工作台应为 X=180°。此前统一保留 −90° 的判断不正确。`SimPyEquipmentOrientation.cs` 按模型指定竖直姿态，工位水平朝向独立保留；原 FBX 与 VR 分级网格均保留。详见 `UNITY_MODEL_AXES_FIXED.md`。
- 去除工位状态球；保留标签、进度和泛光。PC 漫游标记改为地面箭头。
- `SimPyVRNavigation.cs` 在现有单个 XR Origin 的 SDK Camera Offset 下创建虚拟导航层和高度层；摄像机与两个手柄追踪对象保留原追踪组件。关闭冲突的旧移动、转向及射线组件。
- 左杆前推瞄准、回中确认，后拨或侧拨取消；右杆主方向选择高度／30° 转向，左右杆按下分别恢复高度／返回入口。死区 0.25，瞄准和转向触发阈值 0.65。
- 30 米射线及地面落点检测；胶囊检查身体空间。79 个工位和 AGV 使用简单障碍碰撞体，独立于模型 LOD；与厂房现有 10 个碰撞体合计 90 个。
- 高度范围 ±0.9 米、最高速度 0.35 米／秒。Device 模式眼高 1.7 米；Floor 模式保留实际头高。仅 VR 生成副本归零原 XR 根节点偏移，PC 原场景不改。
- 等待有效头部追踪再初始化入口；失去头部追踪取消瞄准，输入回中后解锁。SDK 定位父层平移／转向后补偿虚拟层水平位置和方向，保留 SDK 高度变化。
- 原 SimPy 通讯、共享时钟、只读 VR、远处简化、标签频率和材质策略继续使用。

## 验证结果

记录目录：`results/unity_validation/navigation_20261008`。

| 范围 | 结果与证据 |
|---|---|
| VR 导航与工位 | 29 项通过，`vr_navigation_tests.json`；输入与 SDK 父层变化由编辑器模拟，使用真实运行时物理检查 |
| PC 回归 | 8 项通过，`pc_orientation.json`；79 工位位置与朝向和 VR 一致 |
| 画面 | 全景、工位详情、AGV 跟随、VR 默认视角、射线及 S002/S003/F012/F013 正面截图检查通过 |
| 独立 EXE | 实际运行检查全景、F012 详情、V 第一视角打开／收起；运行日志无本轮检查的四类异常 |
| 实时通讯 | 7 项通过，`native_sync/checks.json`：真实重新排产、加载、控制端续租、共享时钟推进与参数／事件／统计恢复 |
| 重新排产后的 VR | `vr_restored_web_result.json`、`vr_final_live.checks.json` 通过，跟随新仿真编号及恢复后的时钟 |
| PC 保护 | FactoryContent、PC_Main、QualitySettings、GraphicsSettings 的 SHA256 在修改前、测试后和打包后相同 |
| APK | 14 项通过，`apk/apk_validation.json`：CRC、包名、ARM64、XR 库、单一 QTI 启动入口、联网、签名、对齐及 VR 场景列表 |

测试临时修改工作时间、工作日、目标数量及工序名称并重新排产；原配置和生产事件恢复，仿真编号因重新运行正常更新。最后暂停在 2771.9057617 分钟，速度 200，当前新仿真编号 `f70dbb9e-b4c5-4ac2-bd3d-d70fbcd2228c`。

## 测试包

- PC：`builds/UnityPC_20261008/EngineFactoryPC.exe`，Windows 64 位，保留整个文件夹。
- VR：`builds/UnityVR_20261008/EngineFactoryVR.apk`，1.0.20261008 / code 2，59,797,924 字节；操作、连接和安装见同目录 `测试说明.md`。
- PC 构建：Succeeded，0 错误、27 提示；原复杂凸包降级、原 Scene Volume 失效脚本、包缓存和示例字段提示仍存在。没有更改原 PC 模型或原场景来消除这些提示。
- VR 构建：Succeeded，0 错误、2 提示；SDK Both 输入设置及未使用的示例字段。Both 设置沿用项目现有 SDK 配置，需真机观察输入与性能。

未连接头显，APK 未安装到真机。真实手柄轴、双目画面、定位模式、信标重定位、休眠恢复和 CPU/GPU 帧时间需设备验证；编辑器通过不表示上述项通过。

Unity 最终恢复 Windows 64 位构建平台及停止运行的 PC_Main；新 PC 测试程序保留运行。新增源码与备份路径记录在本次验证目录 `source_before`。
