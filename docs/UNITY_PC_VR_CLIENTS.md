# PC 与 VR 观看端

更新：2026-10-07。Unity 工程：C:/AllUnityProjects/MainProject/MainProject。

## 场景与维护

- Assets/Scenes/PC_Main.unity：PC 主控入口。
- Assets/Scenes/VR_Main.unity：燧光头显只读观看入口。
- Assets/Scenes/FactoryContent.unity：PC 加载的完整工厂，也是 VR 简化副本的维护来源。
- Assets/Scenes/FactoryVRContent.unity：VR 独立轻量工厂；近处设备外观、远处轮廓、轻量 AGV，仍使用同一组 79 道工序与共享时钟。
- Assets/Scenes/HelloUnity.unity：保留本轮开始前的原场景，供回退。后续工厂修改请在 FactoryContent 中进行。

打开入口场景后按 Play，入口会加载对应工厂；编辑状态下入口只有配置对象，因此 Game 窗口显示没有摄像机是正常的。

PC 保留全景、完整发动机、原有界面和 WASD 预览。VR 使用 XR Origin 的追踪摄像机、附近工位的世界空间标签及生产状态牌；不会创建 PC 全景摄像机或预览 RenderTexture。VR 只观看，不提供仿真控制或手柄漫游。

编辑器没有头显时，VR 入口用单目观察相机检查画面；该相机不会进入 APK。这不能代替头显双目与定位验收。

## 连接与同步

启动原 SimPy 服务。PC 与头显应访问同一个服务：PC 默认 http://127.0.0.1:8000；VR 入口目前配置为 http://10.33.244.29:8000（本机当前局域网地址）。IP 改变后在入口的 SimPyClientBootstrap.serverUrl 中修改。VR 中 127.0.0.1 指向头显自己。

设备端也可在 Application.persistentDataPath 下放置 simpy_connection.json：

```json
{"serverUrl":"http://PC的局域网IP:8000"}
```

PC 程序可使用 --simpy-server=http://PC地址:8000 覆盖连接配置。两端必须保持同一服务来源。Android 清单已允许 INTERNET 和当前局域网 HTTP 连接；没有修改 PC 的网络设置。

共享时钟接口：GET /api/simulation/unity/playback.json。PC 通过 claim 与 PUT playback 控制；VR 只读取。同步内容包含 sim_id、当前分钟、播放状态和速度。时钟用服务端单调时间推进，客户端用往返延迟估计校准，不要求两台设备系统时间一致。不同 PC 的控制权有租期保护；连接中断时观看端暂停在最近时刻，重新连接后校准。新排产结果会切换 sim_id 并回到月初；PC 再按启动播放设置继续。

这一层控制回放，不修改 SimPy 排产算法、事件起止时间或完工里程碑。

## VR 专用简化

2026-10-07 已进一步生成独立 VR 工厂。当前优化结果、维护与打包方法详见 [UNITY_VR_OPTIMIZATION.md](UNITY_VR_OPTIMIZATION.md)。下面的原共享场景构建裁剪机制保留作为旧场景的兼容路径。

- VR 发动机资产位于 Assets/Generated/SimPyVR，保留主要零件并合并为四段，支持分阶段展示；PC 继续使用完整 CAD 模型。
- VR 不生成外围仓储、吊车等装饰，不渲染桌面界面；最多显示附近十二个工位标签，远处设备按距离及回差隐藏。
- VR 关闭动态阴影，使用独立的抗锯齿、LOD 与渲染比例设置；退出时恢复原设置。工位状态、AGV 路线和完工数量保持完整。
- Android 构建且入口为 VR_Main 时，构建处理器只在临时构建场景中移除被替代的原设备、旧发动机和装饰网格引用，保留工位锚点、建筑、通道、AGV 和 XR。PC 构建不经过此简化；保存的共享场景及原资产不被删改。

Tools/SimPy/Clients 菜单可以打开两个入口，并切换 PC 或 VR 的构建场景列表。它只调整场景列表，打包目标平台仍需在 Build Settings 中选择。本轮不输出 EXE 或 APK。

## 验收边界

本轮验证记录在 results/unity_validation/clients，汇总为 validation_summary.json：

- 共享时钟及 HTTP 边界测试：5 项通过。
- PC 入口实际写入控制时钟；VR 编辑器入口使用 HTTP 主控测试夹具验证暂停、调速及完工同步。尚未运行 PC 独立程序与头显 APK 同时在线的端到端验收。
- 暂停在第 2950 分钟；第 4622 分钟完工 1 台；第 10560 分钟完工 5 台，VR 均跟随正确。
- VR 只有一个编辑器观察相机，没有桌面 Canvas 或预览 RenderTexture；最多显示附近 12 个工位标签。
- 单台发动机从 604 个渲染组件、2,045,087 个三角形，减少为 VR 独立资产的 4 个渲染组件、59,886 个三角形。
- VR 临时构建共享场景的源网格从 20,916,006 个三角形减到 2,670,962 个；这不包含运行时生成网格，不是每帧实际绘制数量或帧率。
- 切回 PC 后恢复 5 台完整发动机共 3020 个渲染组件、原全景和预览相机、shadowDistance=150、lodBias=2；与此前 PC 记录一致。
- HelloUnity 原场景 SHA256 与本轮开始前备份一致。编辑器最终停留在 PC_Main 运行画面，第 2950 分钟暂停、速度 20。

头显的实际双目显示、燧光定位原点/地面、显示模式、网络与帧率仍需设备验收。2026-10-07 已移除失效且未使用的 D:/MRMR/... 多人 SDK 依赖，并输出 `builds/UnityVR_20261007/EngineFactoryVR.apk`；安装测试说明随包提供。本轮未连接头显，不宣称真机已通过。
