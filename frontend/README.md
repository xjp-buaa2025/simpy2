# 前端代码模块化重构说明

## 概述

原始 `index.html` 文件有 **3684行**，现已拆分为模块化结构，便于维护和扩展。

## 文件结构

```
frontend/
├── index.html          # 521行 - HTML结构
├── css/
│   └── styles.css      # 703行 - 所有样式
├── js/
│   ├── config.js       # 62行  - 配置和常量（工位、颜色等）
│   ├── state.js        # 31行  - 全局状态管理
│   ├── data.js         # 82行  - 示例数据
│   ├── utils.js        # 36行  - 工具函数
│   ├── canvas.js       # 377行 - 画布编辑器
│   ├── editor.js       # 136行 - 节点编辑器
│   ├── layout.js       # 219行 - 布局功能
│   ├── csv.js          # 98行  - CSV导入导出
│   ├── simulation.js   # 213行 - 仿真功能
│   ├── analysis.js     # 786行 - 瓶颈/设备/工位分析
│   ├── charts.js       # 402行 - 图表和甘特图
│   ├── ui.js           # 101行 - UI交互
│   └── main.js         # 21行  - 入口初始化
└── process_model.py    # 后端模型
└── simulation.py       # 后端API
```

## 模块职责

| 模块 | 职责 |
|------|------|
| `config.js` | 工位配置、操作类型颜色/图标、默认配置 |
| `state.js` | 全局状态对象、画布状态变量、图表实例 |
| `data.js` | 压气机装配流程示例数据（含工位信息） |
| `utils.js` | showToast、hexToRgba等工具函数 |
| `canvas.js` | 画布初始化、渲染、节点/连线绘制、事件处理 |
| `editor.js` | 节点模态框、保存/删除节点、边重建 |
| `layout.js` | 自动布局、按工位布局、工位筛选、加载数据 |
| `csv.js` | CSV导入导出、构建流程定义 |
| `simulation.js` | 运行仿真、更新结果、图表更新 |
| `analysis.js` | 瓶颈分析、设备详情、工位统计分析 |
| `charts.js` | 疲劳曲线图表、甘特图渲染和控制 |
| `ui.js` | Tab切换、工具箱、配置面板、统计更新 |
| `main.js` | DOMContentLoaded初始化 |

## 加载顺序

脚本加载顺序很重要，在`index.html`中按以下顺序引入：

```html
<script src="js/config.js"></script>   <!-- 配置常量 -->
<script src="js/state.js"></script>    <!-- 状态（依赖config） -->
<script src="js/data.js"></script>     <!-- 数据 -->
<script src="js/utils.js"></script>    <!-- 工具函数 -->
<script src="js/canvas.js"></script>   <!-- 画布（依赖state、utils） -->
<script src="js/editor.js"></script>   <!-- 编辑器（依赖state、canvas） -->
<script src="js/layout.js"></script>   <!-- 布局（依赖state、canvas、editor） -->
<script src="js/csv.js"></script>      <!-- CSV -->
<script src="js/simulation.js"></script> <!-- 仿真 -->
<script src="js/analysis.js"></script> <!-- 分析 -->
<script src="js/charts.js"></script>   <!-- 图表 -->
<script src="js/ui.js"></script>       <!-- UI -->
<script src="js/main.js"></script>     <!-- 入口（最后加载） -->
```

## 部署说明

1. 将 `frontend/` 目录下所有文件替换到服务器对应位置
2. 确保目录结构正确：`css/` 和 `js/` 子目录
3. 后端文件 `process_model.py` 和 `simulation.py` 替换到 `app/models/` 和 `app/api/`

## 代码行数对比

| 文件类型 | 原始 | 模块化后 |
|---------|------|---------|
| HTML | 3684行（含CSS+JS） | 521行 |
| CSS | - | 703行 |
| JS | - | 2491行（13个模块） |
| **总计** | 3684行 | 3715行 |

模块化后虽然总行数略增（因添加了注释和模块头），但每个文件职责单一，便于：
- 团队协作开发
- 定位和修复bug
- 添加新功能
- 代码审查
