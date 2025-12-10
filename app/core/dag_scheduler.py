"""
DAG拓扑调度器
使用NetworkX构建和管理工艺流程的依赖图

功能:
- 从工艺定义构建DAG（有向无环图）
- 拓扑排序确定执行顺序
- 就绪任务识别（支持并行）
- DAG有效性验证（无环、有起点）
"""

from typing import Dict, List, Set, Tuple, Optional
import networkx as nx

from app.models.process_model import ProcessNode, ProcessDefinition


class DAGScheduler:
    """
    DAG拓扑调度器
    
    使用NetworkX DiGraph管理工艺流程的依赖关系
    支持并行任务识别和拓扑排序
    """
    
    def __init__(self, process: ProcessDefinition):
        """
        初始化DAG调度器
        
        Args:
            process: 工艺流程定义
        """
        self.process = process
        self.graph = nx.DiGraph()
        self.node_map: Dict[str, ProcessNode] = {}
        
        # 构建DAG
        self._build_graph(process)
    
    def _build_graph(self, process: ProcessDefinition):
        """
        从工艺定义构建DAG
        
        Args:
            process: 工艺流程定义
        """
        # 添加节点
        for node in process.nodes:
            self.graph.add_node(node.step_id, data=node)
            self.node_map[node.step_id] = node
        
        # 添加边（依赖关系）
        for node in process.nodes:
            for pred_id in node.get_predecessor_list():
                if pred_id in self.node_map:
                    # 边从前置节点指向当前节点
                    self.graph.add_edge(pred_id, node.step_id)
    
    def validate(self) -> Tuple[bool, str]:
        """
        验证DAG有效性
        
        检查:
        - 是否为有向无环图
        - 是否有起始节点
        
        Returns:
            (是否有效, 验证消息)
        """
        # 检查是否为DAG（无环）
        if not nx.is_directed_acyclic_graph(self.graph):
            try:
                cycle = nx.find_cycle(self.graph)
                cycle_str = " -> ".join([f"{u}" for u, v in cycle])
                return False, f"流程图存在循环依赖: {cycle_str}"
            except nx.NetworkXNoCycle:
                pass
            return False, "流程图存在循环依赖"
        
        # 检查是否有起始节点
        start_nodes = self.get_start_nodes()
        if not start_nodes:
            return False, "没有找到起始节点（所有节点都有前置依赖）"
        
        return True, "验证通过"
    
    def get_start_nodes(self) -> List[str]:
        """获取起始节点（入度为0）"""
        return [n for n in self.graph.nodes() if self.graph.in_degree(n) == 0]
    
    def get_end_nodes(self) -> List[str]:
        """获取终止节点（出度为0）"""
        return [n for n in self.graph.nodes() if self.graph.out_degree(n) == 0]
    
    def get_ready_nodes(self, completed: Set[str]) -> List[str]:
        """
        获取就绪节点（所有前置已完成，可并行执行）
        
        Args:
            completed: 已完成节点ID集合
            
        Returns:
            就绪节点ID列表
        """
        ready = []
        for node_id in self.graph.nodes():
            if node_id in completed:
                continue
            predecessors = list(self.graph.predecessors(node_id))
            if all(p in completed for p in predecessors):
                ready.append(node_id)
        return ready
    
    def get_node(self, step_id: str) -> Optional[ProcessNode]:
        """获取指定节点"""
        return self.node_map.get(step_id)
    
    def get_all_nodes(self) -> List[str]:
        """获取所有节点ID"""
        return list(self.graph.nodes())
    
    def get_node_count(self) -> int:
        """获取节点数量"""
        return self.graph.number_of_nodes()
    
    def get_predecessors(self, step_id: str) -> List[str]:
        """获取节点的前置节点"""
        if step_id not in self.graph:
            return []
        return list(self.graph.predecessors(step_id))
    
    def get_successors(self, step_id: str) -> List[str]:
        """获取节点的后继节点"""
        if step_id not in self.graph:
            return []
        return list(self.graph.successors(step_id))
    
    def get_topological_order(self) -> List[str]:
        """获取拓扑排序顺序"""
        try:
            return list(nx.topological_sort(self.graph))
        except nx.NetworkXUnfeasible:
            return []
    
    def get_critical_path(self) -> Tuple[List[str], float]:
        """获取关键路径和时长"""
        if not self.graph.nodes():
            return [], 0
        
        earliest_start = {}
        for node_id in nx.topological_sort(self.graph):
            preds = list(self.graph.predecessors(node_id))
            if not preds:
                earliest_start[node_id] = 0
            else:
                earliest_start[node_id] = max(
                    earliest_start[p] + self.node_map[p].std_duration
                    for p in preds
                )
        
        end_nodes = self.get_end_nodes()
        if not end_nodes:
            return [], 0
        
        max_end_time = 0
        critical_end = None
        for end_id in end_nodes:
            end_time = earliest_start[end_id] + self.node_map[end_id].std_duration
            if end_time > max_end_time:
                max_end_time = end_time
                critical_end = end_id
        
        critical_path = []
        if critical_end:
            current = critical_end
            while current:
                critical_path.insert(0, current)
                preds = list(self.graph.predecessors(current))
                if not preds:
                    break
                current = max(
                    preds,
                    key=lambda p: earliest_start[p] + self.node_map[p].std_duration
                )
        
        return critical_path, max_end_time
    
    def get_parallel_groups(self) -> List[List[str]]:
        """获取可并行执行的任务组"""
        groups = []
        completed = set()
        
        while len(completed) < len(self.graph.nodes()):
            ready = self.get_ready_nodes(completed)
            if not ready:
                break
            groups.append(ready)
            completed.update(ready)
        
        return groups
