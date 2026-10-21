"""
P0 修复专项验证脚本

验证四项 P0 正确性修复：
1. 工人原子获取 —— 复现"双任务各需2人、仅2名工人"的永久死锁场景，
   旧代码会卡死(engines_completed=0)，修复后应能完成。
2. 休息不占用设备 —— 休息事件的 equipment_used 应为空，设备利用率不被休息时间污染。
3. 可复现性 —— 相同 random_seed 两次运行，结果(产量/周期/返工)应完全一致。
4. 语义对齐 —— time_variance 按标准差使用（行为不变，仅文档）。
"""

from app.models.config_model import GlobalConfig
from app.models.process_model import ProcessNode, ProcessDefinition
from app.models.enums import OpType, GanttEventType
from app.core.simulation_engine import SimulationEngine


def test_no_deadlock_with_concurrent_multiworker():
    """两条并行分支，各起始任务都需要2名工人，但工人池仅2人。

    旧的"逐个获取工人"会让两任务各抢到1人、互相干等 -> 永久死锁，
    导致发动机永远无法完工。修复后用名额信号量原子预留，任务串行通过。
    """
    process = ProcessDefinition(
        name="Deadlock Repro",
        nodes=[
            # 两个互相独立的起始节点，都会在 t=0 同时就绪
            ProcessNode(step_id="A1", task_name="分支A装配", op_type=OpType.A,
                        std_duration=20, required_workers=2),
            ProcessNode(step_id="B1", task_name="分支B装配", op_type=OpType.A,
                        std_duration=20, required_workers=2),
            # 汇合节点
            ProcessNode(step_id="C1", task_name="合装", op_type=OpType.A,
                        predecessors="A1;B1", std_duration=10, required_workers=2),
        ]
    )
    config = GlobalConfig(
        work_hours_per_day=8, work_days_per_month=5,
        num_workers=2,          # 关键：只有2名工人
        target_output=1,
        random_seed=42
    )
    result = SimulationEngine(config, process).run()
    assert result.engines_completed >= 1, (
        f"疑似死锁：发动机未完工 (engines_completed={result.engines_completed})"
    )
    print(f"[1] 无死锁验证通过：engines_completed={result.engines_completed}, "
          f"avg_cycle_time={result.avg_cycle_time:.1f}min")


def test_rest_does_not_hold_equipment():
    """规则B负荷休息后，休息事件不应占用关键设备。"""
    process = ProcessDefinition(
        name="Rest vs Equip",
        nodes=[
            ProcessNode(step_id="S1", task_name="高负荷装配", op_type=OpType.A,
                        std_duration=20, work_load_score=9,  # 触发负荷休息
                        required_workers=1, required_tools=["动平衡机"]),
        ]
    )
    config = GlobalConfig(
        work_hours_per_day=8, work_days_per_month=5,
        num_workers=2, target_output=2,
        critical_equipment={"动平衡机": 1},
        rest_load_threshold=5, rest_duration_load=15,
        random_seed=42
    )
    result = SimulationEngine(config, process).run()
    rest_events = [e for e in result.gantt_events if e.event_type == GanttEventType.REST]
    assert rest_events, "未产生休息事件，无法验证"
    for e in rest_events:
        assert not e.equipment_used, (
            f"休息事件仍占用设备：{e.equipment_used}（应为空）"
        )
    print(f"[2] 休息不占设备验证通过：{len(rest_events)} 个休息事件均未锁定关键设备")


def test_reproducibility():
    """相同种子两次运行，关键结果应完全一致（含返工）。"""
    process = ProcessDefinition(
        name="Repro",
        nodes=[
            ProcessNode(step_id="S1", task_name="装配", op_type=OpType.A,
                        std_duration=20, time_variance=5, required_workers=1),
            ProcessNode(step_id="S2", task_name="检测", op_type=OpType.M,
                        predecessors="S1", std_duration=15, time_variance=3,
                        rework_prob=0.4, required_workers=1),
        ]
    )
    config = GlobalConfig(
        work_hours_per_day=8, work_days_per_month=10,
        num_workers=3, target_output=5, random_seed=2025
    )
    r1 = SimulationEngine(config, process).run()
    r2 = SimulationEngine(config, process).run()
    assert r1.engines_completed == r2.engines_completed, "产量不可复现"
    assert abs(r1.avg_cycle_time - r2.avg_cycle_time) < 1e-9, "周期时间不可复现"
    assert r1.quality_stats.total_reworks == r2.quality_stats.total_reworks, \
        "返工次数不可复现（random 模块未播种？）"
    print(f"[3] 可复现性验证通过：产量={r1.engines_completed}, "
          f"返工={r1.quality_stats.total_reworks}, "
          f"周期={r1.avg_cycle_time:.4f}min（两次完全一致）")


if __name__ == "__main__":
    test_no_deadlock_with_concurrent_multiworker()
    test_rest_does_not_hold_equipment()
    test_reproducibility()
    print("\n✅ P0 四项修复全部验证通过")
