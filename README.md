# 航空发动机装配排产仿真系统

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.100+-green.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/SimPy-4.0+-orange.svg" alt="SimPy">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
</p>

<p align="center">
  <b>北京航空航天大学</b><br>
  AeroEngine Assembly Scheduling Simulation System
</p>

---

## 📋 项目简介

本系统是一个面向航空发动机装配车间的**离散事件仿真平台**，用于模拟和优化复杂装配流程的排产调度。系统基于 SimPy 仿真引擎，支持多约束资源调度、质量返工逻辑、工人疲劳管理等核心功能，帮助生产管理人员进行产能规划和瓶颈分析。

### 🎯 应用场景

- 航空发动机总装车间产能评估
- 装配工艺流程优化
- 人员配置与设备投资决策
- 生产计划可行性验证
- 质量控制策略评估

---

## ✨ 功能特性

### 核心仿真能力

| 功能 | 描述 |
|------|------|
| **DAG 工艺流程** | 支持有向无环图定义的复杂装配流程，自动解析依赖关系与关键路径 |
| **双重资源约束** | 工人池 + 关键设备的并行资源竞争与排队，支持设备数量限制 |
| **质量返工逻辑** | M类型（测量）节点支持概率性返工，自动释放资源重新排队 |
| **疲劳休息规则** | 支持规则A（基于连续工作时间）和规则B（基于累积负荷评分）的休息触发机制 |
| **流水线模式** | 支持多台发动机并行生产的流水线排产，根据资源可用性自动投产 |
| **人因工程** | 追踪工人疲劳度、高负荷作业次数，模拟人因对生产效率的影响 |

### 可视化与分析

| 功能 | 描述 |
|------|------|
| **可视化流程编辑器** | 拖拽式节点编辑，支持连线、自动布局 |
| **多维甘特图** | 生产进度甘特图（按发动机）+ 工人排产甘特图（按资源） |
| **资源利用率分析** | 工人/设备利用率统计，区分工作、空闲、休息时间 |
| **智能瓶颈分析** | 自动识别设备瓶颈、工人瓶颈、等待时间瓶颈及高返工任务 |
| **KPI 仪表盘** | 月产量、计划达成率、周期时间、一次通过率、返工率 |
| **数据导出** | 支持仿真报告（JSON）、甘特图数据（CSV）导出 |

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      前端 (Browser)                          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐│
│  │ 流程编辑器   │ │ 参数配置    │ │ 结果展示 (图表/甘特图)   ││
│  │ (Canvas)    │ │ (Forms)     │ │ (Chart.js)              ││
│  └─────────────┘ └─────────────┘ └─────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                              │ HTTP/REST
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    后端 API (FastAPI)                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ /process │ │ /config  │ │/simulation│ │ /results │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   仿真引擎核心 (SimPy)                        │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐     │
│  │ DAGScheduler  │ │ TaskExecutor  │ │ EventCollector│     │
│  │ (拓扑排序)     │ │ (任务执行)     │ │ (事件记录)    │     │
│  └───────────────┘ └───────────────┘ └───────────────┘     │
│  ┌───────────────┐ ┌───────────────┐                       │
│  │ WorkerPool    │ │EquipmentMgr  │                        │
│  │ (工人管理)     │ │ (设备管理)    │                        │
│  └───────────────┘ └───────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

### 目录结构

```
aero_engine_sim/
├── app/
│   ├── api/                    # REST API 端点
│   │   ├── config.py           # 配置管理 API
│   │   ├── process.py          # 工艺流程 API
│   │   ├── results.py          # 结果导出 API
│   │   └── simulation.py       # 仿真控制 API
│   ├── core/                   # 仿真引擎核心
│   │   ├── dag_scheduler.py    # DAG 依赖调度器
│   │   ├── equipment_manager.py# 设备资源管理
│   │   ├── event_collector.py  # 事件收集器
│   │   ├── simulation_engine.py# 仿真主引擎
│   │   ├── task_executor.py    # 任务执行器
│   │   └── worker_pool.py      # 工人池管理
│   ├── models/                 # Pydantic 数据模型
│   │   ├── config_model.py     # 配置模型
│   │   ├── enums.py            # 枚举定义
│   │   ├── gantt_model.py      # 甘特图模型
│   │   ├── process_model.py    # 工艺流程模型
│   │   ├── result_model.py     # 仿真结果模型
│   │   └── worker_model.py     # 工人状态模型
│   ├── utils/                  # 工具函数
│   │   ├── csv_parser.py       # CSV 解析器
│   │   ├── statistics.py       # 统计计算
│   │   ├── time_converter.py   # 时间转换
│   │   └── validators.py       # 数据验证
│   └── main.py                 # FastAPI 应用入口
├── frontend/
│   ├── css/                    # 样式文件
│   ├── js/                     # 前端逻辑脚本
│   └── index.html              # 单页面前端应用入口
├── config/
│   └── default_config.yaml     # 默认配置文件
├── data/
│   ├── 1.csv                   # 测试流程数据 1
│   ├── 2.csv                   # 测试流程数据 2
│   ├── 3.csv                   # 测试流程数据 3
│   └── aero_engine_full_assembly2.csv # 完整发动机装配流程
├── tests/                      # 单元测试
│   ├── test_dag_scheduler.py   # DAG 调度测试
│   ├── test_worker_pool.py     # 工人池测试
│   ├── test_simulation.py      # 仿真引擎测试
│   ├── test_rework_logic.py    # 返工逻辑测试
│   └── test_rest_logic.py      # 休息逻辑测试
├── run_validation_tests.py     # 集成验证脚本
├── requirements.txt            # Python 依赖
└── README.md                   # 本文档
```

---

## 🚀 快速开始

### 环境要求

- Python 3.9+
- 现代浏览器（Chrome/Firefox/Edge）

### 安装步骤

```bash
# 1. 克隆或解压项目
unzip aero_engine_sim.zip
cd aero_engine_sim

# 2. 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动服务
conda activate sim_engine
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 5. 访问系统
# 浏览器打开: http://localhost:8000
```

### Docker 部署（可选）

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t aero-sim .
docker run -p 8000:8000 aero-sim
```

---

## 📖 使用指南

### 1. 定义工艺流程

#### 方式一：可视化编辑器

1. 从左侧工具箱拖拽节点到画布
2. 双击节点编辑属性（工时、负荷、返工概率等）
3. 右键拖拽创建节点间连线（定义依赖关系）
4. 点击「自动布局」整理节点位置

#### 方式二：CSV 导入

准备符合以下格式的 CSV 文件（参考 `data/` 目录下的示例文件）：

| 列名 | 说明 | 示例 |
|------|------|------|
| step_id | 步骤唯一标识 | S001 |
| task_name | 任务名称 | 低压压气机装配 |
| op_type | 操作类型 (H/A/M/T/D) | A |
| predecessors | 前置依赖 (分号分隔) | S001;S002 |
| std_duration | 标准工时 (分钟) | 45 |
| time_variance | 时间方差 | 5 |
| work_load_score | 负荷评分 (1-10) | 6 |
| rework_prob | 返工概率 (仅M类型) | 0.08 |
| required_workers | 所需工人数 | 2 |
| required_tools | 所需设备 (分号分隔) | 动平衡机 |
| station | 工位编号 (可选) | ST01 |

#### 操作类型说明

| 代码 | 类型 | 说明 |
|------|------|------|
| H | Handling | 取放操作，物料搬运 |
| A | Assembly | 装配操作，零件组装 |
| M | Measurement | 测量检验，可能触发返工 |
| T | Tooling | 工具操作，使用专用工具 |
| D | Data Recording | 数据记录，文档填写 |

### 2. 配置仿真参数

在「参数配置」页面设置：

**排班配置**
- 每日工作小时数（默认 8）
- 每月工作天数（默认 22）
- 工人数量（默认 6）
- 目标月产量（决定流水线生产的停止条件）

**设备配置**
- 添加关键设备及数量（如：动平衡机 ×2）

**休息规则**
- 规则A：连续工作 N 分钟后休息（时间触发，默认 50分钟工作/10分钟休息）
- 规则B：高负荷任务后休息（负荷触发，REBA≥阈值）

### 3. 运行仿真

点击「运行仿真」按钮，系统将：

1. 验证工艺流程的 DAG 有效性（无环、连通性）
2. 初始化资源池（工人、设备）
3. 启动 SimPy 仿真环境
4. 按 DAG 拓扑顺序和资源可用性调度任务
5. 模拟资源竞争、随机返工、疲劳休息事件
6. 收集全量统计数据和甘特图事件

### 4. 分析结果

**仿真结果页面**
- **KPI 卡片**：月产量、达成率、平均周期时间、一次通过率、总仿真时长
- **瓶颈分析**：自动列出限制产能的Top设备、高负荷工人及长等待任务
- **资源利用率**：交互式图表展示各工人和设备的利用率详情

**甘特图页面**
- **生产甘特图**：按发动机维度查看各工序执行时间线，通过颜色区分正常/休息/返工/等待
- **资源甘特图**：按工人/设备维度查看任务分配情况，直观发现资源冲突
- **高级功能**：支持时间范围筛选、按事件类型过滤、导出 CSV 数据

---

## 🔌 API 参考

### 仿真控制

```
POST /api/simulation/run
```

请求体：
```json
{
  "config": {
    "work_hours_per_day": 8,
    "work_days_per_month": 22,
    "num_workers": 6,
    "target_output": 3,
    "critical_equipment": {"动平衡机": 2},
    "rest_time_threshold": 50,
    "rest_duration_time": 5,
    "rest_load_threshold": 7,
    "rest_duration_load": 3,
    "pipeline_mode": true
  },
  "process": {
    "name": "发动机装配流程",
    "nodes": [...]
  }
}
```

响应：
```json
{
  "success": true,
  "message": "仿真完成，生产3台发动机",
  "data": {
    "engines_completed": 3,
    "target_achievement_rate": 1.0,
    "avg_cycle_time": 1850.5,
    "sim_duration": 10560,
    "quality_stats": {...},
    "worker_stats": [...],
    "equipment_stats": [...],
    "gantt_events": [...]
  }
}
```

### 工艺流程

```
POST /api/process/parse-csv     # 解析 CSV 文件
POST /api/process/export-csv    # 导出为 CSV
GET  /api/process/example       # 获取示例流程
GET  /api/process/template      # 下载 CSV 模板
```

### 配置管理

```
GET  /api/config/default        # 获取默认配置
POST /api/config/validate       # 验证配置有效性
```

### 结果查询与导出

```
GET  /api/results/list/all      # 获取历史仿真记录列表
GET  /api/results/{sim_id}      # 获取指定仿真详情
DELETE /api/results/{sim_id}    # 删除仿真记录
GET  /api/results/{sim_id}/kpi  # 获取KPI数据
GET  /api/results/{sim_id}/bottleneck # 获取瓶颈分析报告
GET  /api/results/{sim_id}/worker-stats # 获取工人详细统计
GET  /api/results/{sim_id}/equipment-stats # 获取设备详细统计
POST /api/results/export/gantt  # 导出甘特图 CSV
POST /api/results/export/report # 导出完整 JSON 报告
```

---

## 🧪 测试

### 运行单元测试

```bash
cd aero_engine_sim
pytest tests/ -v
```

测试覆盖：
- `test_dag_scheduler.py` - DAG 拓扑排序和依赖解析
- `test_worker_pool.py` - 工人资源分配
- `test_simulation.py` - 端到端仿真流程集成测试
- `test_rework_logic.py` - 返工触发和资源释放逻辑
- `test_rest_logic.py` - 疲劳休息规则验证

### 运行集成验证

```bash
python run_validation_tests.py
```

验证场景（包含多个测试用例）：

| 测试 | 场景 | 验证点 |
|------|------|--------|
| test_01 | 单节点 | 最小可运行流程 |
| test_02 | 并行分支 | DAG 并发调度 |
| test_03 | 高返工率 | 返工逻辑和资源释放 |
| test_04 | 资源竞争 | 多工人多设备排队 |
| test_05 | 高负荷 | 负荷触发休息（规则B）|
| test_06 | 连续工作 | 时间触发休息（规则A）|
| test_07 | 复杂DAG | 多源多汇网络 |
| test_08 | 全类型 | H/A/M/T/D 操作覆盖 |
| test_09 | 时间方差 | 不确定性采样 |
| test_10 | 大规模 | 50节点性能测试 |

---

## 🛠️ 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| 后端框架 | FastAPI | REST API、自动文档 |
| 仿真引擎 | SimPy | 离散事件仿真 |
| 数据模型 | Pydantic | 数据验证、序列化 |
| 图算法 | NetworkX | DAG 拓扑排序、关键路径计算 |
| 配置管理 | PyYAML | YAML 配置解析 |
| 前端 | HTML5 + Vanilla JS | 单页面应用 |
| 图表 | Chart.js | 数据可视化 |
| 画布 | Canvas API | 流程图编辑器 |

---

## 📊 性能指标

| 指标 | 数值 | 测试条件 |
|------|------|---------|
| 单次仿真耗时 | < 1秒 | 50节点、4台发动机 |
| API 响应时间 | < 100ms | 不含仿真计算 |
| 内存占用 | < 200MB | 典型工作负载 |
| 并发支持 | 10+ | FastAPI 异步处理 |

---

## 🔮 未来规划

- [ ] 多目标优化算法集成（遗传算法、模拟退火）
- [ ] 实时数据对接（MES/ERP 集成）
- [ ] 3D 车间布局可视化
- [ ] 多产品混线排产
- [ ] 报表自动生成（PDF/Excel）

---

## 📄 许可证

本项目采用 MIT 许可证。

---

## 👥 联系方式

- 单位：北京航空航天大学
- 邮箱：contact@buaa.edu.cn

---

<p align="center">
  <i>Made with ❤️ for Aerospace Manufacturing</i>
</p>
