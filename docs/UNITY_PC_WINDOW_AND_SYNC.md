# PC 独立程序通信与窗口模式

## 实际 EXE 通信测试（2026-10-05）

用户启动 `builds/UnityPC_20261005_Fixed/EngineFactoryPC.exe` 后，停止 Unity Editor 的 Play，单独测试该进程。

- 使用网页调用的同一个 `/api/simulation/run` 接口：工时 8→6 小时、月工作日 22→15、目标 3→5，F012 名称加测试后缀。
- EXE 的 Player.log 出现新运行 `465ed6a9-bf43-4cf5-831b-ead712bd27d7` 的自动载入记录。
- 后端时钟从新排产初始暂停状态变为播放状态，revision 92→93，控制者保持为该 EXE 的 `80b5c206896d4aa2908c0774485dc4ea`。测试脚本没有发送初始化播放命令。
- 等待超过控制租约的 12 秒后，控制连接仍有效，回放时间持续增长，证明 EXE 持续向后端续约。
- 恢复原输入后，EXE 再次收到新运行；工序事件、工位名称及月末产量与原结果完全一致。回放位置、速度和暂停状态也恢复。

证据：`results/unity_validation/standalone_20261005/checks.json`、`changed_player.json`、`lease_after_13_seconds.json`、`restored_player.json`。脚本：`tools/unity_pc_standalone_sync_validation.py`。

网页修改参数后需要重新**运行仿真**，发布新的排产结果，EXE 才会更新。PC 与网页通过同一个 SimPy 后端通信；后台服务仍需运行。当前默认服务为 `http://127.0.0.1:8000`，跨机器时使用已有 `--simpy-server=http://服务器IP:8000` 或连接配置文件。

本次独立程序通信使用真实日志和服务器时钟验证。自动审批拒绝控制 `enginefactorypc` 窗口，因此没有声称自动点击 EXE 按钮或读取其画面。

## 新版窗口功能

- 首次启动默认窗口，尺寸通常为 1366×768，小屏自动适配。
- **显示设置 → 窗口 / 全屏**，或 **F11 / Alt+Enter** 切换。
- 全屏使用无边框桌面全屏；返回窗口恢复先前窗口大小。
- 窗口允许拖动边框调整大小，也可使用系统最大化/还原按钮。
- 记住显示模式和窗口大小，下一次启动恢复。
- 独立的 `SimPyPCWindow` 仅由 Windows PC 入口创建；VR 入口及 Android XR 不创建这个组件。
- 控制台按窗口宽度缩放，较矮窗口的详情/菜单自适应缩小。操作不会改变仿真速度或时钟。

原生显示模式切换需要运行新包验证；Editor 中的显示模式按钮标注“PC 打包版可用”。Editor 布局测试与原生窗口测试分别记录。

新版输出：[EngineFactoryPC.exe](C:/xjp/simpy2/builds/UnityPC_20261005_Window/EngineFactoryPC.exe)。Windows x64 构建成功，0 错误，26 条原 CAD 碰撞网格/Scene Volume/Ximmerse 示例脚本等警告，资源 1,496,834,097 字节。构建报告：`results/unity_validation/standalone_20261005/window_build_report.json`。分发时复制整个 Window 目录。

## 布局及 VR 回归

Editor 在只读跟随真实 EXE 时钟的状态下检查 1366×768、1920×1080、2560×1440、1280×800、1920×800。每种尺寸分别检查全景、显示设置、工位详情、第一视角，共 **20 项通过**，面板越界和 PC 文字溢出均为 0。新增窗口/全屏两个按钮均已生成。记录：`results/unity_validation/standalone_20261005/layout/summary.json`。

VR_Main 在 Editor 中复查：79 个工位、单个观察相机、PC 屏幕 Canvas 数量为 0，无桌面预览相机；时间和暂停状态跟随真实 PC EXE，无控制权限。截图确认保留第一人称工厂及世界空间标签。记录：`window_vr_regression.json`、`window_vr_regression.png`。这不代表 VR 真机或 APK 验收。
