"""
工艺节点模型
定义工艺流程中的节点和流程定义

模型:
- ProcessNode: 单个工艺节点
- ProcessDefinition: 完整工艺流程定义
"""

from typing import List, Dict, Set, Optional
from pydantic import BaseModel, Field

from app.models.enums import OpType


class ProcessNode(BaseModel):
    """
    工艺节点模型
    
    定义单个工艺步骤的所有属性
    
    Attributes:
        step_id: 唯一步骤ID
        task_name: 任务名称
        op_type: 操作类型（H/A/M/T/D）
        predecessors: 前置依赖（分号分隔）
        std_duration: 标准工时（分钟）
        time_variance: 时间波动方差
        work_load_score: REBA负荷评分（1-10）
        rework_prob: 返工概率（仅M类有效）
        required_workers: 所需工人数
        required_tools: 所需工具/设备列表
        station: 工位ID（必填）
        x, y: 前端编辑器坐标
    """
    
    step_id: str = Field(
        description="唯一步骤ID"
    )
    task_name: str = Field(
        description="任务名称"
    )
    op_type: OpType = Field(
        description="操作类型（H/A/M/T/D）"
    )
    predecessors: str = Field(
        default="",
        description="前置依赖（分号分隔）"
    )
    std_duration: float = Field(
        ge=0,
        description="标准工时（分钟）"
    )
    time_variance: float = Field(
        default=0.0,
        ge=0,
        description="时间波动方差（正态分布）"
    )
    work_load_score: int = Field(
        default=5,
        ge=1,
        le=10,
        description="REBA负荷评分（1-10）"
    )
    rework_prob: float = Field(
        default=0.0,
        ge=0,
        le=1,
        description="返工概率（仅M类有效，0-1）"
    )
    required_workers: int = Field(
        default=1,
        ge=1,
        description="所需工人数"
    )
    required_tools: List[str] = Field(
        default=[],
        description="所需工具/设备列表"
    )
    station: str = Field(
        default="ST01",
        description="工位ID（必填）"
    )
    
    # 前端坐标（用于流程图编辑器）
    x: float = Field(
        default=0,
        description="节点X坐标"
    )
    y: float = Field(
        default=0,
        description="节点Y坐标"
    )
    
    def get_predecessor_list(self) -> List[str]:
        """
        解析前置依赖为列表
        
        Returns:
            前置依赖ID列表
        """
        if not self.predecessors:
            return []
        return [p.strip() for p in self.predecessors.split(";") if p.strip()]
    
    def get_critical_equipment(self, critical_set: Set[str]) -> List[str]:
        """
        获取关键设备（需要排队的）
        
        Args:
            critical_set: 关键设备名称集合
            
        Returns:
            关键设备列表
        """
        return [t for t in self.required_tools if t in critical_set]
    
    def get_common_tools(self, critical_set: Set[str]) -> List[str]:
        """
        获取普通工具（无限供应）
        
        Args:
            critical_set: 关键设备名称集合
            
        Returns:
            普通工具列表
        """
        return [t for t in self.required_tools if t not in critical_set]
    
    def is_measurement(self) -> bool:
        """
        判断是否为测量类型任务
        
        Returns:
            是否为M类型
        """
        return self.op_type == OpType.M
    
    def can_trigger_rework(self) -> bool:
        """
        判断是否可能触发返工
        
        Returns:
            是否可能返工（M类型且返工概率>0）
        """
        return self.is_measurement() and self.rework_prob > 0
    
    def is_high_load(self, threshold: int = 7) -> bool:
        """
        判断是否为高负荷任务
        
        Args:
            threshold: 负荷阈值
            
        Returns:
            是否为高负荷
        """
        return self.work_load_score > threshold
    
    def to_csv_row(self) -> List[str]:
        """
        转换为CSV行数据
        
        Returns:
            CSV字段列表
        """
        return [
            self.step_id,
            self.task_name,
            self.op_type.value,
            self.predecessors,
            str(self.std_duration),
            str(self.time_variance),
            str(self.work_load_score),
            str(self.rework_prob),
            str(self.required_workers),
            ";".join(self.required_tools),
            self.station
        ]
    
    class Config:
        json_schema_extra = {
            "example": {
                "step_id": "S001",
                "task_name": "取压气机转子",
                "op_type": "H",
                "predecessors": "",
                "std_duration": 5.0,
                "time_variance": 1.0,
                "work_load_score": 4,
                "rework_prob": 0.0,
                "required_workers": 2,
                "required_tools": ["吊装设备"],
                "x": 100,
                "y": 100
            }
        }


class ProcessDefinition(BaseModel):
    """
    工艺流程定义
    
    包含完整工艺流程的所有节点
    
    Attributes:
        name: 流程名称
        description: 流程描述
        nodes: 工艺节点列表
    """
    
    name: str = Field(
        default="未命名流程",
        description="流程名称"
    )
    description: str = Field(
        default="",
        description="流程描述"
    )
    nodes: List[ProcessNode] = Field(
        default=[],
        description="工艺节点列表"
    )
    
    def get_node_map(self) -> Dict[str, ProcessNode]:
        """
        获取节点映射字典
        
        Returns:
            步骤ID到节点的映射
        """
        return {node.step_id: node for node in self.nodes}
    
    def get_node(self, step_id: str) -> Optional[ProcessNode]:
        """
        根据ID获取节点
        
        Args:
            step_id: 步骤ID
            
        Returns:
            节点对象或None
        """
        node_map = self.get_node_map()
        return node_map.get(step_id)
    
    def get_start_nodes(self) -> List[ProcessNode]:
        """
        获取起始节点（无前置依赖）
        
        Returns:
            起始节点列表
        """
        return [n for n in self.nodes if not n.get_predecessor_list()]
    
    def get_end_nodes(self) -> List[ProcessNode]:
        """
        获取结束节点（不被其他节点依赖）
        
        Returns:
            结束节点列表
        """
        # 收集所有被依赖的节点
        depended = set()
        for node in self.nodes:
            depended.update(node.get_predecessor_list())
        
        # 返回不在被依赖集合中的节点
        return [n for n in self.nodes if n.step_id not in depended]
    
    def get_node_ids(self) -> List[str]:
        """
        获取所有节点ID
        
        Returns:
            节点ID列表
        """
        return [n.step_id for n in self.nodes]
    
    def get_total_std_duration(self) -> float:
        """
        计算总标准工时
        
        Returns:
            总工时（分钟）
        """
        return sum(n.std_duration for n in self.nodes)
    
    def get_measurement_nodes(self) -> List[ProcessNode]:
        """
        获取所有测量类型节点
        
        Returns:
            M类型节点列表
        """
        return [n for n in self.nodes if n.is_measurement()]
    
    def get_high_load_nodes(self, threshold: int = 7) -> List[ProcessNode]:
        """
        获取高负荷节点
        
        Args:
            threshold: 负荷阈值
            
        Returns:
            高负荷节点列表
        """
        return [n for n in self.nodes if n.is_high_load(threshold)]
    
    def get_all_tools(self) -> Set[str]:
        """
        获取所有使用到的工具/设备
        
        Returns:
            工具名称集合
        """
        tools = set()
        for node in self.nodes:
            tools.update(node.required_tools)
        return tools
    
    def validate_predecessors(self) -> tuple:
        """
        验证前置依赖有效性
        
        Returns:
            (是否有效, 错误列表)
        """
        errors = []
        node_ids = set(self.get_node_ids())
        
        for node in self.nodes:
            for pred_id in node.get_predecessor_list():
                if pred_id not in node_ids:
                    errors.append(
                        f"节点 '{node.step_id}' 的前置依赖 '{pred_id}' 不存在"
                    )
        
        return len(errors) == 0, errors
    
    def add_node(self, node: ProcessNode) -> bool:
        """
        添加节点
        
        Args:
            node: 要添加的节点
            
        Returns:
            是否添加成功（ID不重复）
        """
        if node.step_id in self.get_node_ids():
            return False
        self.nodes.append(node)
        return True
    
    def remove_node(self, step_id: str) -> bool:
        """
        移除节点
        
        Args:
            step_id: 要移除的节点ID
            
        Returns:
            是否移除成功
        """
        for i, node in enumerate(self.nodes):
            if node.step_id == step_id:
                self.nodes.pop(i)
                return True
        return False
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "航空发动机装配示例流程",
                "description": "包含压气机转子装配、动平衡测试和整机试车",
                "nodes": [
                    {
                        "step_id": "S001",
                        "task_name": "取压气机转子",
                        "op_type": "H",
                        "predecessors": "",
                        "std_duration": 5.0,
                        "time_variance": 1.0,
                        "work_load_score": 4,
                        "rework_prob": 0.0,
                        "required_workers": 2,
                        "required_tools": ["吊装设备"]
                    }
                ]
            }
        }
