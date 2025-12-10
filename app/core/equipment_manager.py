"""
设备管理器
管理关键设备和普通工具资源

功能:
- 区分关键设备（有限，用PriorityResource）和普通工具（无限）
- 设备请求与释放
- 设备利用率统计

设计要点:
- 关键设备使用simpy.PriorityResource进行资源竞争管理
- 普通工具不做资源限制，假设无限供应
- 关键设备列表由前端配置决定
"""

from typing import Dict, List, Tuple, Set, Optional, Any
import simpy

from app.models.config_model import GlobalConfig


class EquipmentManager:
    """
    设备管理器
    
    区分管理关键设备和普通工具
    - 关键设备：有限数量，需要排队
    - 普通工具：无限供应，无需管理
    """
    
    def __init__(self, env: simpy.Environment, config: GlobalConfig):
        """
        初始化设备管理器
        
        Args:
            env: SimPy环境
            config: 全局配置
        """
        self.env = env
        self.config = config
        
        # 关键设备资源（PriorityResource）
        self.critical_equipment: Dict[str, simpy.PriorityResource] = {}
        
        # 使用记录（设备名 -> [(开始时间, 结束时间), ...]）
        self.usage_log: Dict[str, List[Tuple[float, float]]] = {}
        
        # 当前使用状态
        self.current_usage: Dict[str, int] = {}
        
        # 初始化关键设备
        for equip_name, capacity in config.critical_equipment.items():
            self.critical_equipment[equip_name] = simpy.PriorityResource(
                env, capacity=capacity
            )
            self.usage_log[equip_name] = []
            self.current_usage[equip_name] = 0
    
    def is_critical(self, tool_name: str) -> bool:
        """
        判断是否为关键设备
        
        Args:
            tool_name: 工具/设备名称
            
        Returns:
            是否为关键设备
        """
        return tool_name in self.critical_equipment
    
    def get_critical_equipment_names(self) -> List[str]:
        """
        获取所有关键设备名称
        
        Returns:
            关键设备名称列表
        """
        return list(self.critical_equipment.keys())
    
    def get_critical_set(self) -> Set[str]:
        """
        获取关键设备名称集合
        
        Returns:
            关键设备名称集合
        """
        return set(self.critical_equipment.keys())
    
    def request_equipment(
        self, 
        tools: List[str], 
        priority: int = 1
    ) -> Tuple[List[Any], List[str]]:
        """
        请求关键设备
        
        普通工具会自动跳过，只对关键设备创建请求
        
        Args:
            tools: 工具列表
            priority: 请求优先级（数值越小优先级越高）
            
        Returns:
            (请求对象列表, 关键设备名称列表)
        """
        requests = []
        critical_tools = []
        
        for tool in tools:
            if self.is_critical(tool):
                req = self.critical_equipment[tool].request(priority=priority)
                requests.append(req)
                critical_tools.append(tool)
        
        return requests, critical_tools
    
    def release_equipment(
        self, 
        tools: List[str], 
        requests: List[Any]
    ):
        """
        释放设备
        
        Args:
            tools: 工具列表
            requests: 对应的请求对象列表
        """
        critical_tools = [t for t in tools if self.is_critical(t)]
        for tool, req in zip(critical_tools, requests):
            self.critical_equipment[tool].release(req)
    
    def log_usage_start(self, tool_name: str):
        """
        记录设备使用开始
        
        Args:
            tool_name: 设备名称
        """
        if tool_name in self.usage_log:
            # 记录开始时间，结束时间待填充
            self.usage_log[tool_name].append((self.env.now, -1))
            self.current_usage[tool_name] = self.current_usage.get(tool_name, 0) + 1
    
    def log_usage_end(self, tool_name: str):
        """
        记录设备使用结束
        
        Args:
            tool_name: 设备名称
        """
        if tool_name in self.usage_log and self.usage_log[tool_name]:
            # 找到最后一个未完成的记录
            for i in range(len(self.usage_log[tool_name]) - 1, -1, -1):
                start, end = self.usage_log[tool_name][i]
                if end == -1:
                    self.usage_log[tool_name][i] = (start, self.env.now)
                    break
            self.current_usage[tool_name] = max(
                0, self.current_usage.get(tool_name, 1) - 1
            )
    
    def get_equipment_utilization(self, total_time: float) -> Dict[str, float]:
        """
        计算设备利用率
        
        Args:
            total_time: 总仿真时间
            
        Returns:
            设备名 -> 利用率 映射
        """
        utilization = {}
        
        for equip_name, logs in self.usage_log.items():
            capacity = self.config.critical_equipment.get(equip_name, 1)
            total_capacity_time = total_time * capacity
            
            # 计算总使用时间
            usage_time = 0
            for start, end in logs:
                if end > 0:
                    usage_time += (end - start)
                else:
                    # 未结束的使用
                    usage_time += (self.env.now - start)
            
            utilization[equip_name] = (
                usage_time / total_capacity_time if total_capacity_time > 0 else 0
            )
        
        return utilization
    
    def get_equipment_stats(self, total_time: float) -> List[Dict]:
        """
        获取设备统计数据
        
        Args:
            total_time: 总仿真时间
            
        Returns:
            设备统计列表
        """
        stats = []
        utilization = self.get_equipment_utilization(total_time)
        
        for equip_name in self.critical_equipment.keys():
            capacity = self.config.critical_equipment.get(equip_name, 1)
            total_capacity_time = total_time * capacity
            
            # 计算使用时间
            usage_time = 0
            task_count = 0
            for start, end in self.usage_log.get(equip_name, []):
                if end > 0:
                    usage_time += (end - start)
                    task_count += 1
            
            stats.append({
                "equipment_name": equip_name,
                "capacity": capacity,
                "total_time": total_capacity_time,
                "work_time": usage_time,
                "idle_time": total_capacity_time - usage_time,
                "utilization_rate": utilization.get(equip_name, 0),
                "tasks_served": task_count
            })
        
        return stats
    
    def get_available_capacity(self, tool_name: str) -> int:
        """
        获取设备当前可用容量
        
        Args:
            tool_name: 设备名称
            
        Returns:
            可用容量数
        """
        if tool_name not in self.critical_equipment:
            return float('inf')  # 普通工具无限
        
        resource = self.critical_equipment[tool_name]
        return resource.capacity - len(resource.users)
    
    def is_equipment_available(self, tool_name: str) -> bool:
        """
        判断设备是否有空闲容量
        
        Args:
            tool_name: 设备名称
            
        Returns:
            是否可用
        """
        return self.get_available_capacity(tool_name) > 0
    
    def get_queue_length(self, tool_name: str) -> int:
        """
        获取设备等待队列长度
        
        Args:
            tool_name: 设备名称
            
        Returns:
            等待队列长度
        """
        if tool_name not in self.critical_equipment:
            return 0
        
        resource = self.critical_equipment[tool_name]
        return len(resource.queue)
    
    def reset(self):
        """
        重置设备管理器（用于新仿真）
        """
        self.usage_log = {name: [] for name in self.critical_equipment.keys()}
        self.current_usage = {name: 0 for name in self.critical_equipment.keys()}
