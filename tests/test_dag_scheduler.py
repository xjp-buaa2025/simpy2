"""
DAG调度器单元测试
测试DAGScheduler的核心功能

测试内容:
- DAG构建
- 循环依赖检测
- 并行任务识别
- 就绪节点计算
- 关键路径计算
- 拓扑排序
"""

import pytest

from app.models.process_model import ProcessNode, ProcessDefinition
from app.models.enums import OpType
from app.core.dag_scheduler import DAGScheduler


def create_node(
    step_id: str,
    predecessors: str = "",
    std_duration: float = 30,
    op_type: OpType = OpType.A
) -> ProcessNode:
    """辅助函数：创建测试节点"""
    return ProcessNode(
        step_id=step_id,
        task_name=f"Task {step_id}",
        op_type=op_type,
        predecessors=predecessors,
        std_duration=std_duration,
        required_workers=1
    )


class TestDAGSchedulerBasic:
    """DAG调度器基础测试"""
    
    def test_empty_process(self):
        """测试空流程"""
        process = ProcessDefinition(name="Empty", nodes=[])
        scheduler = DAGScheduler(process)
        
        assert scheduler.get_node_count() == 0
        assert scheduler.get_start_nodes() == []
        assert scheduler.get_end_nodes() == []
    
    def test_single_node(self):
        """测试单节点流程"""
        process = ProcessDefinition(
            name="Single",
            nodes=[create_node("S001")]
        )
        scheduler = DAGScheduler(process)
        
        assert scheduler.get_node_count() == 1
        assert scheduler.get_start_nodes() == ["S001"]
        assert scheduler.get_end_nodes() == ["S001"]
        
        valid, msg = scheduler.validate()
        assert valid
    
    def test_linear_chain(self):
        """测试线性链式流程"""
        process = ProcessDefinition(
            name="Linear",
            nodes=[
                create_node("S001"),
                create_node("S002", "S001"),
                create_node("S003", "S002"),
            ]
        )
        scheduler = DAGScheduler(process)
        
        assert scheduler.get_start_nodes() == ["S001"]
        assert scheduler.get_end_nodes() == ["S003"]
        
        valid, msg = scheduler.validate()
        assert valid
    
    def test_diamond_pattern(self):
        """测试菱形依赖模式"""
        #     S001
        #    /    \
        # S002    S003
        #    \    /
        #     S004
        process = ProcessDefinition(
            name="Diamond",
            nodes=[
                create_node("S001"),
                create_node("S002", "S001"),
                create_node("S003", "S001"),
                create_node("S004", "S002;S003"),
            ]
        )
        scheduler = DAGScheduler(process)
        
        assert scheduler.get_start_nodes() == ["S001"]
        assert scheduler.get_end_nodes() == ["S004"]
        
        valid, msg = scheduler.validate()
        assert valid


class TestCycleDetection:
    """循环依赖检测测试"""
    
    def test_simple_cycle(self):
        """测试简单循环"""
        # A -> B -> C -> A
        process = ProcessDefinition(
            name="Cycle",
            nodes=[
                create_node("A", "C"),
                create_node("B", "A"),
                create_node("C", "B"),
            ]
        )
        scheduler = DAGScheduler(process)
        
        valid, msg = scheduler.validate()
        assert not valid
        assert "循环" in msg
    
    def test_self_reference(self):
        """测试自引用"""
        process = ProcessDefinition(
            name="SelfRef",
            nodes=[
                create_node("A", "A"),
            ]
        )
        scheduler = DAGScheduler(process)
        
        valid, msg = scheduler.validate()
        assert not valid
    
    def test_indirect_cycle(self):
        """测试间接循环"""
        # A -> B -> C -> D -> B (cycle in B-C-D)
        process = ProcessDefinition(
            name="IndirectCycle",
            nodes=[
                create_node("A"),
                create_node("B", "A;D"),
                create_node("C", "B"),
                create_node("D", "C"),
            ]
        )
        scheduler = DAGScheduler(process)
        
        valid, msg = scheduler.validate()
        assert not valid


class TestReadyNodes:
    """就绪节点测试"""
    
    def test_initial_ready_nodes(self):
        """测试初始就绪节点"""
        process = ProcessDefinition(
            name="Test",
            nodes=[
                create_node("S001"),
                create_node("S002"),  # Also a start node
                create_node("S003", "S001"),
            ]
        )
        scheduler = DAGScheduler(process)
        
        ready = scheduler.get_ready_nodes(set())
        assert set(ready) == {"S001", "S002"}
    
    def test_ready_after_completion(self):
        """测试完成后的就绪节点"""
        process = ProcessDefinition(
            name="Test",
            nodes=[
                create_node("S001"),
                create_node("S002", "S001"),
                create_node("S003", "S001"),
                create_node("S004", "S002;S003"),
            ]
        )
        scheduler = DAGScheduler(process)
        
        # Initial
        ready = scheduler.get_ready_nodes(set())
        assert ready == ["S001"]
        
        # After S001
        ready = scheduler.get_ready_nodes({"S001"})
        assert set(ready) == {"S002", "S003"}  # Parallel!
        
        # After S001, S002
        ready = scheduler.get_ready_nodes({"S001", "S002"})
        assert "S003" in ready
        assert "S004" not in ready  # S003 not done yet
        
        # After S001, S002, S003
        ready = scheduler.get_ready_nodes({"S001", "S002", "S003"})
        assert ready == ["S004"]
    
    def test_parallel_detection(self):
        """测试并行任务识别"""
        #     S001
        #    / | \
        # S002 S003 S004
        #    \ | /
        #     S005
        process = ProcessDefinition(
            name="Parallel",
            nodes=[
                create_node("S001"),
                create_node("S002", "S001"),
                create_node("S003", "S001"),
                create_node("S004", "S001"),
                create_node("S005", "S002;S003;S004"),
            ]
        )
        scheduler = DAGScheduler(process)
        
        # After S001, three tasks are ready in parallel
        ready = scheduler.get_ready_nodes({"S001"})
        assert len(ready) == 3
        assert set(ready) == {"S002", "S003", "S004"}


class TestTopologicalOrder:
    """拓扑排序测试"""
    
    def test_linear_order(self):
        """测试线性拓扑顺序"""
        process = ProcessDefinition(
            name="Linear",
            nodes=[
                create_node("S001"),
                create_node("S002", "S001"),
                create_node("S003", "S002"),
            ]
        )
        scheduler = DAGScheduler(process)
        
        order = scheduler.get_topological_order()
        assert order == ["S001", "S002", "S003"]
    
    def test_complex_order(self):
        """测试复杂拓扑顺序"""
        process = ProcessDefinition(
            name="Complex",
            nodes=[
                create_node("S001"),
                create_node("S002", "S001"),
                create_node("S003", "S001"),
                create_node("S004", "S002;S003"),
            ]
        )
        scheduler = DAGScheduler(process)
        
        order = scheduler.get_topological_order()
        
        # S001 must be first
        assert order[0] == "S001"
        # S004 must be last
        assert order[-1] == "S004"
        # S002 and S003 must be before S004
        assert order.index("S002") < order.index("S004")
        assert order.index("S003") < order.index("S004")


class TestCriticalPath:
    """关键路径测试"""
    
    def test_linear_critical_path(self):
        """测试线性关键路径"""
        process = ProcessDefinition(
            name="Linear",
            nodes=[
                create_node("S001", std_duration=10),
                create_node("S002", "S001", std_duration=20),
                create_node("S003", "S002", std_duration=15),
            ]
        )
        scheduler = DAGScheduler(process)
        
        path, duration = scheduler.get_critical_path()
        
        assert path == ["S001", "S002", "S003"]
        assert duration == 45  # 10 + 20 + 15
    
    def test_parallel_critical_path(self):
        """测试并行任务的关键路径"""
        #     S001 (10)
        #    /    \
        # S002(5) S003(20)
        #    \    /
        #     S004 (10)
        process = ProcessDefinition(
            name="Parallel",
            nodes=[
                create_node("S001", std_duration=10),
                create_node("S002", "S001", std_duration=5),
                create_node("S003", "S001", std_duration=20),
                create_node("S004", "S002;S003", std_duration=10),
            ]
        )
        scheduler = DAGScheduler(process)
        
        path, duration = scheduler.get_critical_path()
        
        # Critical path goes through S003 (longer)
        assert "S001" in path
        assert "S003" in path
        assert "S004" in path
        assert duration == 40  # 10 + 20 + 10


class TestParallelGroups:
    """并行组测试"""
    
    def test_parallel_groups(self):
        """测试并行任务分组"""
        process = ProcessDefinition(
            name="Test",
            nodes=[
                create_node("S001"),
                create_node("S002"),
                create_node("S003", "S001"),
                create_node("S004", "S001"),
                create_node("S005", "S002"),
                create_node("S006", "S003;S004;S005"),
            ]
        )
        scheduler = DAGScheduler(process)
        
        groups = scheduler.get_parallel_groups()
        
        # First group: start nodes
        assert set(groups[0]) == {"S001", "S002"}
        # Second group: after S001 and S002
        assert set(groups[1]) == {"S003", "S004", "S005"}
        # Third group: final
        assert groups[2] == ["S006"]


class TestNodeAccess:
    """节点访问测试"""
    
    def test_get_node(self):
        """测试获取节点"""
        process = ProcessDefinition(
            name="Test",
            nodes=[
                create_node("S001"),
                create_node("S002", "S001"),
            ]
        )
        scheduler = DAGScheduler(process)
        
        node = scheduler.get_node("S001")
        assert node is not None
        assert node.step_id == "S001"
        
        node = scheduler.get_node("INVALID")
        assert node is None
    
    def test_get_predecessors(self):
        """测试获取前置节点"""
        process = ProcessDefinition(
            name="Test",
            nodes=[
                create_node("S001"),
                create_node("S002"),
                create_node("S003", "S001;S002"),
            ]
        )
        scheduler = DAGScheduler(process)
        
        assert scheduler.get_predecessors("S001") == []
        assert set(scheduler.get_predecessors("S003")) == {"S001", "S002"}
    
    def test_get_successors(self):
        """测试获取后继节点"""
        process = ProcessDefinition(
            name="Test",
            nodes=[
                create_node("S001"),
                create_node("S002", "S001"),
                create_node("S003", "S001"),
            ]
        )
        scheduler = DAGScheduler(process)
        
        assert set(scheduler.get_successors("S001")) == {"S002", "S003"}
        assert scheduler.get_successors("S002") == []


class TestValidation:
    """验证功能测试"""
    
    def test_valid_dag(self):
        """测试有效DAG"""
        process = ProcessDefinition(
            name="Valid",
            nodes=[
                create_node("S001"),
                create_node("S002", "S001"),
            ]
        )
        scheduler = DAGScheduler(process)
        
        valid, msg = scheduler.validate()
        assert valid
        assert "通过" in msg
    
    def test_no_start_node(self):
        """测试无起始节点"""
        # All nodes have predecessors, forming a cycle
        process = ProcessDefinition(
            name="NoStart",
            nodes=[
                create_node("A", "B"),
                create_node("B", "A"),
            ]
        )
        scheduler = DAGScheduler(process)
        
        valid, msg = scheduler.validate()
        assert not valid
    
    def test_invalid_predecessor(self):
        """测试无效前置依赖（在验证器中检查，不在DAGScheduler中）"""
        process = ProcessDefinition(
            name="Test",
            nodes=[
                create_node("S001"),
                create_node("S002", "INVALID"),  # Invalid predecessor
            ]
        )
        scheduler = DAGScheduler(process)
        
        # DAGScheduler ignores invalid predecessors
        # This should be caught by validators.py
        assert scheduler.get_predecessors("S002") == []


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
