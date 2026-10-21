# PC 构建异常检查与修复

日期：2026-10-05。用户反馈打包版异常后，重新检查 Windows 目标下的 Unity PC 工厂。

## 已确认原因

用户运行旧包后的 `Player.log` 记录了 `ArgumentNullException: shader`，调用位置为 `SimPyReplayRuntime.BuildOverview()`。该处创建 AGV 总览定位灯材质时调用 `Shader.Find("Unlit/Color")`；此运行时创建的材质没有场景资产引用，原构建设置也没有明确保留该着色器。

异常使展示初始化中断，`Load()` 将 replay 清空，后续场景更新与界面输入处理随之停止。编辑器能找到该着色器，因此之前的编辑器界面验收没有覆盖此构建差异。

原始日志：[player_before_fix.log](C:/xjp/simpy2/results/unity_validation/pc_ui_20261005/repair/player_before_fix.log)。

## 修复

- 在 Graphics Settings 的 Always Included Shaders 中加入 `Unlit/Color`，内置着色器 fileID 10755；其他原配置保留。
- 增加 Editor 构建前校验：确认 `Unlit/Color`、`Standard`、`SimPy/StatusGlow` 可用，并确保运行时路线/定位灯需要的着色器明确保留。校验适用于后续标准 Unity 构建。
- 原工厂、原模型、79 个工位绑定、XR 配置和 SimPy 排产逻辑保持原样。

校验记录：[shader_retention_added.json](C:/xjp/simpy2/results/unity_validation/pc_ui_20261005/repair/shader_retention_added.json)。

## Unity 工厂复查

- 79 个绑定、79 个唯一工序编号、942 条工序事件。
- 有效渲染器无缺失材质，无不受支持的着色器；中文字体引用有效。
- 默认仅全景摄像机渲染，漫游预览相机关闭；原模型自带摄像机和 XR 摄像机均未抢占 PC 全景。
- 三种分辨率、菜单、详情、进度、月末数量、速度、复位、完成跳转、发动机筛选、AGV 跟随、漫游开关和标签稳定性共 24 项再次通过，最终截图无标签重叠/面板遮挡/PC 文字溢出。
- 仍有原场景 `工厂/Lighting/Scene Volume` 缺失脚本及旧 CAD 凸包警告；本轮有效材质与相机检查未发现其阻断工厂展示。原对象保留。

证据：[factory_audit.json](C:/xjp/simpy2/results/unity_validation/pc_ui_20261005/repair/factory_audit.json)、[validation_summary.json](C:/xjp/simpy2/results/unity_validation/pc_ui_20261005/validation_summary.json)。

修正版 Windows x64 构建成功，0 个构建错误，25 条旧模型/场景警告，资源 1,496,830,353 字节。输出：[EngineFactoryPC.exe](C:/xjp/simpy2/builds/UnityPC_20261005_Fixed/EngineFactoryPC.exe)；请使用整个 Fixed 文件夹，不能只替换 EXE。旧包保留作对照，README 已标明存在初始化异常。

构建记录：[pc_build_fixed_report.json](C:/xjp/simpy2/results/unity_validation/pc_ui_20261005/repair/pc_build_fixed_report.json)。用户随后启动 Fixed EXE，Player.log 确认成功完成初始化，且真实新排产载入与时钟回传测试通过。详见 [PC 通信与窗口记录](C:/xjp/simpy2/docs/UNITY_PC_WINDOW_AND_SYNC.md)。应用控制仍被自动审批拦截，尚未自动测试独立程序的原生窗口按钮。
