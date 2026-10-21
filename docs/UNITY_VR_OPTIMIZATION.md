# VR 工厂场景优化

最新：VR 原模型与远景改善已更新至 **versionCode 4**，见 [实现与验证记录](UNITY_VR_VISUAL4.md)。安装包位于 `builds/UnityVR_20261008_Visual4`。以下版本 3 及更早内容为历史记录。

更新：2026-10-08。Unity 工程：`C:/AllUnityProjects/MainProject/MainProject`。

Rhino X Pro 手柄输入与分类设备低模更新见 [修复记录](UNITY_RHINO_FIX.md)。最新包为 `builds/UnityVR_20261008_RhinoFix/EngineFactoryVR.apk`（versionCode 3），含输入诊断、AGV 方位提示及独立任务牌；真实手柄仍待设备确认。

最新工位朝向修正与 VR 导航已交付：见 [导航实现与验证](UNITY_VR_NAVIGATION.md)。最新 APK 位于 `builds/UnityVR_20261008`，手柄操作见同目录 `测试说明.md`。加入独立导航障碍后 VR 运行时共 90 个碰撞体；下表的 10 个是加入导航前的历史指标。

后续 APK 已构建：`builds/UnityVR_20261007/EngineFactoryVR.apk`，安装与真机测试见同目录 `测试说明.md`。本页以下记录为场景优化阶段；APK 阶段复查与包校验记录位于 `results/unity_validation/apk_20261007`。

## 已完成

- PC 继续加载 `FactoryContent.unity`；VR 改为加载独立的 `FactoryVRContent.unity`。原设备、建筑、AGV 和 PC 发动机资产保留。
- VR 近处保留设备外观，按材质合并静态零件；超过 28 米切换到蓝色基座与设备轮廓，回到 22 米内恢复细节。切换有回差，避免在边界反复闪动。
- 工厂墙体、柱子、地板和顶棚使用独立简化几何；删除 VR 副本中的闲置设备脚本、刚体和碰撞体。保留 XR 组件与厂房边界碰撞体。
- AGV 使用独立车体、载物台、警示标识和四个车轮，共 7 个渲染组件。修正进口模型坐标造成的埋地问题，沿用回放位置和转向逻辑。
- VR 使用独立简化着色器与共享材质；复制设备贴图并限制至 1024，开启 mipmap。原 PC 材质与贴图没有修改。
- 附近最多 12 个工位标签，选择加入距离回差；标签数据 10 Hz 更新，生产状态牌 4 Hz 更新，朝向随观察相机每帧更新。
- 工位近处显示状态泛光；远处保留设备轮廓；远处发动机模型隐藏但逻辑完工数量持续同步。
- VR 不创建桌面全景或第一视角预览 RenderTexture。VR 画质设置退出时恢复，PC 不使用上述简化分支。

## 优化前后

同一排产、同一观察位置，1920×1080 编辑器单目画面；第 10560 分钟，第 22 工作日，完工 5 台。

| 指标 | 优化前 VR | 优化后 VR | 降幅 |
|---|---:|---:|---:|
| 启用的渲染组件 | 3,686 | 419 | 88.6% |
| 启用几何的三角形 | 3,877,808 | 630,997 | 83.7% |
| 场景引用材质数 | 733 | 225 | 69.3% |
| 场景碰撞体数 | 1,251 | 10 | 99.2% |
| 启用 MonoBehaviour 数 | 1,933 | 85 | 95.6% |
| 场景引用网格内存 | 2,534,641,450 字节 | 96,973,192 字节 | 96.2% |

“启用三角形”包含视野外仍启用的几何，不能作为实际每帧绘制数。网格内存是 Unity Profiler 对场景引用网格的统计，不等于 APK 大小或头显总内存。编辑器单目截图、批次和帧时间不能代替双目头显性能验收。

## 已验证

验证记录：`results/unity_validation/vr_optimization_20261007/validation_summary.json`，14 项检查通过。

- 近处、远处及 24 米回差区域切换通过，近远模型不同时显示。
- 79 个工位编号与位置和 PC 一致。
- VR 只读跟随正在运行的 PC 共享时钟；仿真编号、工作日、分钟及完工 5 台一致。
- VR 仅一个观察相机，无桌面 Canvas、无预览 RenderTexture；材质无缺失或不支持的着色器。
- AGV 7 个渲染组件启用，网格最低点高于地面。
- 切回 PC：完整发动机 3,020 个渲染组件保留，工厂、界面与完工统计显示正常；shadowDistance=150、lodBias=2、maximumLODLevel=0 恢复。
- `FactoryContent.unity`、`PC_Main.unity`、`QualitySettings.asset`、`GraphicsSettings.asset` SHA256 与调整前一致。
- PC 构建场景列表仍为 `PC_Main` 和 `FactoryContent`；编辑器最终停在 PC_Main，已退出 Play。

本轮使用已暂停的月末时钟进行只读验证，没有修改网页排产参数或运行中 PC 的播放位置。AGV 连续运动算法沿用原实现；本轮检查其轻量模型、坐标及方向转换，未重新做全月动态回放验收。未构建 APK，未测燧光头显帧率、双目效果和定位。

## 后续维护与打包

1. 工厂模型与工位映射继续在原 `FactoryContent` 维护。
2. 停止 Play，执行 `Tools → SimPy → VR → Generate optimized factory`，重新生成 VR 副本。它会替换 VR 生成资产，请在原场景维护设备布局，避免直接手改生成文件。
3. PC：`Tools → SimPy → Clients → Use PC build scenes`，Windows 平台。
4. VR：`Tools → SimPy → Clients → Use VR build scenes`，Android 平台。菜单自动选择 `VR_Main` 与 `FactoryVRContent`，VR 入口的服务地址使用 PC 局域网 IP。
5. 真机验收时再检查 CPU/GPU 帧时间、内存峰值、双目着色器、标签可读性、定位原点和网络重连，按设备预算进一步调整细节距离与渲染比例。

可重复的编辑器验证脚本：`tools/unity_vr_optimization_validation.py --phase after` 与 `python -m tools.unity_vr_functional_validation`。需 Unity 编辑器打开此工程、SimPy 服务可访问，且现有 PC 控制端持有共享时钟；验证使用只读跟随方式。
