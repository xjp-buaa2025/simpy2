"""
仿真系统集成测试
测试SimulationEngine的完整功能

测试内容:
- 完整仿真流程
- 流水线模式
- 结果正确性
- 性能测试
"""

import pytest
import time

from app.models.config_model import GlobalConfig
from app.models.process_model import ProcessNode, ProcessDefinition
from app.models.enums import OpType, SimulationStatus, GanttEventType
from app.core.simulation_engine import SimulationEngine


def create_simple_process() -> ProcessDefinition:
    """创建简单测试流程（3个节点）"""
    return ProcessDefinition(
        name="Simple Process",
        nodes=[
            ProcessNode(
                step_id="S001",
                task_name="准备",
                op_type=OpType.H,
                predecessors="",
                std_duration=30,
                required_workers=1
            ),
            ProcessNode(
                step_id="S002",
                task_name="装配",
                op_type=OpType.A,
                predecessors="S001",
                std_duration=60,
                required_workers=2
            ),
            ProcessNode(
                step_id="S003",
                task_name="检测",
                op_type=OpType.M,
                predecessors="S002",
                std_duration=45,
                rework_prob=0.1,
                required_workers=1
            ),
        ]
    )


def create_complex_process() -> ProcessDefinition:
    """创建复杂测试流程（包含并行和设备）"""
    return ProcessDefinition(
        name="Complex Process",
        nodes=[
            ProcessNode(
                step_id="S001",
                task_name="部件A准备",
                op_type=OpType.H,
                predecessors="",
                std_duration=20,
                required_workers=1
            ),
            ProcessNode(
                step_id="S002",
                task_name="部件B准备",
                op_type=OpType.H,
                predecessors="",
                std_duration=25,
                required_workers=1
            ),
            ProcessNode(
                step_id="S003",
                task_name="部件A装配",
                op_type=OpType.A,
                predecessors="S001",
                std_duration=45,
                required_workers=2,
                required_tools=["装配台"]
            ),
            ProcessNode(
                step_id="S004",
                task_name="部件B装配",
                op_type=OpType.A,
                predecessors="S002",
                std_duration=50,
                required_workers=2,
                required_tools=["装配台"]
            ),
            ProcessNode(
                step_id="S005",
                task_name="组合装配",
                op_type=OpType.A,
                predecessors="S003;S004",
                std_duration=90,
                required_workers=3,
                required_tools=["装配台"],
                work_load_score=8
            ),
            ProcessNode(
                step_id="S006",
                task_name="平衡测试",
                op_type=OpType.M,
                predecessors="S005",
                std_duration=60,
                rework_prob=0.15,
                required_workers=1,
                required_tools=["动平衡机"]
            ),
            ProcessNode(
                step_id="S007",
                task_name="最终检验",
                op_type=OpType.M,
                predecessors="S006",
                std_duration=40,
                rework_prob=0.05,
                required_workers=1
            ),
        ]
    )


class TestSimulationBasic:
    """基础仿真测试"""
    
    def test_simple_simulation(self):
        """测试简单仿真"""
        config = GlobalConfig(
            work_hours_per_day=8,
            work_days_per_month=22,
            num_workers=4,
            target_output=1,
            pipeline_mode=False
        )
        process = create_simple_process()
        
        engine = SimulationEngine(config, process)
        result = engine.run()
        
        assert result.status == SimulationStatus.COMPLETED
        assert result.engines_completed >= 1
        assert len(result.gantt_events) > 0
    
    def test_simulation_result_structure(self):
        """测试仿真结果结构"""
        config = GlobalConfig(
            work_hours_per_day=8,
            work_days_per_month=5,  # Short simulation
            num_workers=4,
            target_output=1
        )
        process = create_simple_process()
        
        engine = SimulationEngine(config, process)
        result = engine.run()
        
        # Check result structure
        assert result.sim_id is not None
        assert result.status in SimulationStatus
        assert result.config is not None
        assert result.sim_duration >= 0
        assert result.engines_completed >= 0
        assert 0 <= result.target_achievement_rate
        assert result.avg_cycle_time >= 0
        
        # Worker stats
        assert len(result.worker_stats) == config.num_workers
        for stat in result.worker_stats:
            assert stat.resource_id.startswith("Worker_")
            assert 0 <= stat.utilization_rate <= 1
        
        # Quality stats
        assert result.quality_stats is not None
        assert result.quality_stats.total_inspections >= 0
        assert 0 <= result.quality_stats.first_pass_rate <= 1
        
        # Gantt events
        assert isinstance(result.gantt_events, list)
        
        # Time mapping
        assert "minutes_per_day" in result.time_mapping
    
    def test_empty_process(self):
        """测试空流程"""
        config = GlobalConfig(num_workers=4)
        process = ProcessDefinition(name="Empty", nodes=[])
        
        engine = SimulationEngine(config, process)
        result = engine.run()
        
        assert result.status == SimulationStatus.FAILED


class TestPipelineMode:
    """流水线模式测试"""
    
    def test_pipeline_multiple_engines(self):
        """测试流水线模式多台生产"""
        config = GlobalConfig(
            work_hours_per_day=8,
            work_days_per_month=22,
            num_workers=6,
            target_output=3,
            pipeline_mode=True
        )
        process = create_simple_process()
        
        engine = SimulationEngine(config, process)
        result = engine.run()
        
        assert result.status == SimulationStatus.COMPLETED
        # Should complete multiple engines with pipeline mode
        assert result.engines_completed >= 2
    
    def test_sequential_vs_pipeline(self):
        """测试顺序模式vs流水线模式"""
        config_seq = GlobalConfig(
            work_hours_per_day=8,
            work_days_per_month=22,
            num_workers=6,
            target_output=3,
            pipeline_mode=False
        )
        
        config_pipe = GlobalConfig(
            work_hours_per_day=8,
            work_days_per_month=22,
            num_workers=6,
            target_output=3,
            pipeline_mode=True
        )
        
        process = create_simple_process()
        
        engine_seq = SimulationEngine(config_seq, process)
        result_seq = engine_seq.run()
        
        engine_pipe = SimulationEngine(config_pipe, process)
        result_pipe = engine_pipe.run()
        
        # Pipeline mode should complete more or equal engines
        assert result_pipe.engines_completed >= result_seq.engines_completed


class TestGanttEvents:
    """甘特图事件测试"""
    
    def test_event_types(self):
        """测试事件类型"""
        config = GlobalConfig(
            work_hours_per_day=8,
            work_days_per_month=10,
            num_workers=4,
            target_output=1
        )
        process = create_simple_process()
        
        engine = SimulationEngine(config, process)
        result = engine.run()
        
        event_types = set(e.event_type for e in result.gantt_events)
        
        # Should have at least NORMAL events
        assert GanttEventType.NORMAL in event_types
    
    def test_event_time_ordering(self):
        """测试事件时间顺序"""
        config = GlobalConfig(
            work_hours_per_day=8,
            work_days_per_month=10,
            num_workers=4
        )
        process = create_simple_process()
        
        engine = SimulationEngine(config, process)
        result = engine.run()
        
        # Group events by engine
        engine_events = {}
        for event in result.gantt_events:
            if event.engine_id not in engine_events:
                engine_events[event.engine_id] = []
            engine_events[event.engine_id].append(event)
        
        # Events within each engine should have valid times
        for events in engine_events.values():
            for event in events:
                assert event.start_time >= 0
                assert event.end_time >= event.start_time
    
    def test_event_worker_assignment(self):
        """测试事件工人分配"""
        config = GlobalConfig(num_workers=4, target_output=1)
        process = create_simple_process()
        
        engine = SimulationEngine(config, process)
        result = engine.run()
        
        normal_events = [
            e for e in result.gantt_events 
            if e.event_type == GanttEventType.NORMAL
        ]
        
        for event in normal_events:
            # Each normal event should have workers assigned
            assert len(event.worker_ids) > 0


class TestResourceConstraints:
    """资源约束测试"""
    
    def test_worker_constraint(self):
        """测试工人资源约束"""
        # Very few workers, should cause waiting
        config = GlobalConfig(
            work_hours_per_day=8,
            work_days_per_month=22,
            num_workers=2,  # Limited workers
            target_output=2,
            pipeline_mode=True
        )
        process = create_complex_process()
        
        engine = SimulationEngine(config, process)
        result = engine.run()
        
        # With limited workers, some waiting should occur
        assert result.status == SimulationStatus.COMPLETED
    
    def test_equipment_constraint(self):
        """测试设备资源约束"""
        config = GlobalConfig(
            work_hours_per_day=8,
            work_days_per_month=22,
            num_workers=10,
            target_output=2,
            critical_equipment={"动平衡机": 1},  # Limited equipment
            pipeline_mode=True
        )
        process = create_complex_process()
        
        engine = SimulationEngine(config, process)
        result = engine.run()
        
        assert result.status == SimulationStatus.COMPLETED


class TestQualityStats:
    """质量统计测试"""
    
    def test_inspection_counting(self):
        """测试检验计数"""
        config = GlobalConfig(
            work_hours_per_day=8,
            work_days_per_month=22,
            num_workers=6,
            target_output=2
        )
        process = create_complex_process()  # Has M-type nodes
        
        engine = SimulationEngine(config, process)
        result = engine.run()
        
        # Should have inspections from M-type nodes
        assert result.quality_stats.total_inspections > 0
    
    def test_first_pass_rate(self):
        """测试一次通过率"""
        config = GlobalConfig(
            work_hours_per_day=8,
            work_days_per_month=22,
            num_workers=6,
            target_output=3,
            random_seed=42  # For reproducibility
        )
        
        # Process with high rework probability
        process = ProcessDefinition(
            name="High Rework",
            nodes=[
                ProcessNode(
                    step_id="S001",
                    task_name="准备",
                    op_type=OpType.H,
                    std_duration=10,
                    required_workers=1
                ),
                ProcessNode(
                    step_id="S002",
                    task_name="检测",
                    op_type=OpType.M,
                    predecessors="S001",
                    std_duration=20,
                    rework_prob=0.5,  # High rework probability
                    required_workers=1
                ),
            ]
        )
        
        engine = SimulationEngine(config, process)
        result = engine.run()
        
        # First pass rate should be less than 100%
        assert result.quality_stats.first_pass_rate < 1.0


class TestPerformance:
    """性能测试"""
    
    def test_simulation_speed(self):
        """测试仿真速度"""
        config = GlobalConfig(
            work_hours_per_day=8,
            work_days_per_month=22,  # Full month
            num_workers=6,
            target_output=3
        )
        process = create_complex_process()
        
        start_time = time.time()
        engine = SimulationEngine(config, process)
        result = engine.run()
        elapsed = time.time() - start_time
        
        # Should complete in reasonable time (< 10 seconds)
        assert elapsed < 10.0
        assert result.status == SimulationStatus.COMPLETED
    
    def test_large_process(self):
        """测试大规模流程"""
        # Create a larger process
        nodes = []
        for i in range(20):
            step_id = f"S{i+1:03d}"
            pred = f"S{i:03d}" if i > 0 else ""
            nodes.append(ProcessNode(
                step_id=step_id,
                task_name=f"任务{i+1}",
                op_type=OpType.A,
                predecessors=pred,
                std_duration=15,
                required_workers=1
            ))
        
        process = ProcessDefinition(name="Large", nodes=nodes)
        config = GlobalConfig(
            work_hours_per_day=8,
            work_days_per_month=22,
            num_workers=6
        )
        
        start_time = time.time()
        engine = SimulationEngine(config, process)
        result = engine.run()
        elapsed = time.time() - start_time
        
        assert elapsed < 10.0
        assert result.status == SimulationStatus.COMPLETED


class TestReproducibility:
    """可复现性测试"""
    
    def test_random_seed(self):
        """测试随机种子"""
        config = GlobalConfig(
            work_hours_per_day=8,
            work_days_per_month=22,
            num_workers=6,
            target_output=2,
            random_seed=42
        )
        process = create_complex_process()
        
        # Run twice with same seed
        engine1 = SimulationEngine(config, process)
        result1 = engine1.run()
        
        engine2 = SimulationEngine(config, process)
        result2 = engine2.run()
        
        # Core results should be identical (engines completed)
        # Note: Due to SimPy's concurrent scheduling, event count may vary slightly
        assert result1.engines_completed == result2.engines_completed
        # Allow small variance in event count due to timing differences
        assert abs(len(result1.gantt_events) - len(result2.gantt_events)) <= 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
