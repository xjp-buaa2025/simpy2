# 工艺文件导入与工位进度

网页的“导入工艺文件”支持 CSV 和 XLSX。PT6A27 工艺表的 `WSation`（兼容 `station`、`WStation`、`工位编号`）对应网页工区和 Unity 工位。例如 `WS-R01` 同时写入节点的 `station`、`area_id`、`workstation_id`，中文名称从 PT6A29 工位目录取得。

导入不切换容量约束开关。同编号的容量、效率、并行套数及设备配置保留；新工位默认容量 1，仅在原本已启用容量模型时参与约束。已有的工位约束模式、设备库存和仿真设置保持原值。数据或容量校验失败时，网页保留导入前的流程和设置。JSON 方案和 CSV 导出均保留工区及实体工位绑定。

## 上传接口

`POST /api/process/parse-file` 使用 `multipart/form-data`，文件字段为 `file`。

成功响应 `data` 包含 `name`、`description`、`nodes`、`station_catalog`。目录条目包含 `station_id`、`area_id`、`label`。错误响应包含可展示的 `data.errors` 以及定位到工作表、行、字段的 `data.issues`；不返回可加载的部分流程。原 `/api/process/parse-csv` 仍可使用。

## 进度含义

每个 `(station_id, engine_id)` 独立计算：

```text
progress = 已放行工序的标准工时之和 / 工位全部工序的标准工时之和
```

`progress` 为 0～1。只在工序真实执行结束、完成必要休息并放行时累计；执行中、等待和失败返工均不贡献完成量。表内的 `S-Move`、`S-Rest`、`Coop` 与其他工序使用相同规则。

`completed` 以该工位的全部工序实际放行为准，不能用 `progress == 1` 替代。零工时工序不增加工时权重，因此可能出现 `progress=1, completed=false`；网页同时展示已放行工序数。全站总标准工时为零时，全部放行前进度为 0，之后为 1。

时间统一使用从仿真开始计算的分钟，与墙上时间和仿真计算耗时无关。同一时间点所有 `completed_at <= time_minutes` 的完成事件一次性计入。期末尚未执行的完成回调不算放行。

## 结果结构

运行响应、结果查询和 JSON 报告都包含 `station_progress`：

```text
station_progress
  schema_version: 1
  sim_id
  time_unit: "minute"
  time_minutes: 仿真期末分钟
  stations[]
    station_id, area_id, label
    total_steps, total_standard_minutes
    engines[]
      engine_id, released_at
      started_at: 首次进入该工位的时间，可为 null
      completed_at: 工位全部工序放行的时间，可为 null
      completed_steps, completed_standard_minutes
      progress, completed
      state: "not_started" | "in_progress" | "completed"
      completion_events[]
        step_id, completed_at, std_duration
```

同一工位可有多台发动机，不选择默认发动机，也不将它们的进度混成一个比例。完整时间线保留所有已投产发动机，各工位中尚未进入的发动机进度为 0。

## 按时间查询

```http
GET /api/results/{sim_id}/station-progress?time_minutes=120&station_id=WS-R01&engine_id=1
```

三个查询参数均可省略。时间省略时取期末；省略筛选条件时返回全部工位或发动机。返回统一 `success/message/data` 包装，`data` 与完整结构相同，但不包含 `completion_events`，数值按指定分钟重新采样。尚未投产的发动机不出现在该时间的快照中；未知编号返回空筛选结果。

- 结果不存在：HTTP 404。
- 旧结果没有放行记录：HTTP 409，需重新仿真。
- 时间为非有限数、负数或超过仿真期末：HTTP 422。

暂停时重复查询同一时间，向前或向后拖动时查询对应分钟，即可得到确定的进度。结果页的工位进度表也调用此接口。

## Unity 后续接入

发布仿真时，独立入口提供最近发布的完整工位时间线：

```http
GET /api/simulation/unity/station-progress.json
```

响应为直接的 `station_progress` JSON，无 API 包装，带 `Cache-Control: no-store`。未生成时返回 HTTP 404。该文件包含 `sim_id`、完成事件及期末快照，Unity 可自行采样时间线，或在服务保留该结果时按 `sim_id` 调用按时间查询接口。现有结果存储仍为进程内存；完整已发布 JSON 文件独立保留，不引入数据库。

`publish_to_clients=false` 仍返回工位进度，但不替换已发布文件。符合旧工序映射的流程继续发布原版回放；其他流程返回 `unity_sync.mode="station_progress_only"`，并附 `station_progress_url`。这一模式不会覆盖旧 `replay.json`、旧同步标记或 Unity StreamingAssets 回放，也不会改变旧共享播放时钟。

本次没有修改或构建 Unity 客户端。PT6A29 场景后续按同名 `station_id` 绑定进度，状态使用 `completed` 判定，进度条使用 `progress`。
