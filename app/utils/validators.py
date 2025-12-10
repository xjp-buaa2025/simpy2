"""
数据验证工具
提供各种数据验证功能

功能:
- 工艺流程验证（DAG有效性）
- 配置参数验证
- CSV数据行验证
"""

from typing import List, Tuple, Dict, Set, Any, Optional
import networkx as nx

from app.models.config_model import GlobalConfig
from app.models.process_model import ProcessNode, ProcessDefinition
from app.models.enums import OpType


def validate_process_definition(
    process: ProcessDefinition
) -> Tuple[bool, List[str], List[str]]:
    """
    验证工艺流程定义
    
    检查内容:
    - 节点ID唯一性
    - 前置依赖有效性
    - DAG无环
    - 存在起始节点
    - M类型节点返工概率
    
    Args:
        process: 工艺流程定义
        
    Returns:
        (是否有效, 错误列表, 警告列表)
    """
    errors = []
    warnings = []
    
    if not process.nodes:
        errors.append("流程中没有任何节点")
        return False, errors, warnings
    
    # 1. 检查节点ID唯一性
    seen_ids: Set[str] = set()
    for node in process.nodes:
        if node.step_id in seen_ids:
            errors.append(f"重复的节点ID: {node.step_id}")
        seen_ids.add(node.step_id)
    
    # 2. 检查前置依赖有效性
    node_ids = {n.step_id for n in process.nodes}
    for node in process.nodes:
        for pred_id in node.get_predecessor_list():
            if pred_id not in node_ids:
                errors.append(
                    f"节点'{node.step_id}'的前置依赖'{pred_id}'不存在"
                )
    
    # 3. 构建图并检查环
    graph = nx.DiGraph()
    for node in process.nodes:
        graph.add_node(node.step_id)
    for node in process.nodes:
        for pred_id in node.get_predecessor_list():
            if pred_id in node_ids:
                graph.add_edge(pred_id, node.step_id)
    
    if not nx.is_directed_acyclic_graph(graph):
        try:
            cycle = nx.find_cycle(graph)
            cycle_str = " -> ".join([f"{u}" for u, v in cycle])
            errors.append(f"流程图存在循环依赖: {cycle_str}")
        except nx.NetworkXNoCycle:
            errors.append("流程图存在循环依赖")
    
    # 4. 检查起始节点
    start_nodes = [n for n in graph.nodes() if graph.in_degree(n) == 0]
    if not start_nodes:
        errors.append("没有找到起始节点（所有节点都有前置依赖）")
    
    # 5. 检查M类型节点返工概率
    for node in process.nodes:
        if node.op_type == OpType.M:
            if node.rework_prob <= 0:
                warnings.append(
                    f"测量节点'{node.step_id}'的返工概率为0，"
                    f"考虑设置合理的返工概率"
                )
            elif node.rework_prob > 0.5:
                warnings.append(
                    f"测量节点'{node.step_id}'的返工概率过高({node.rework_prob})，"
                    f"建议不超过0.5"
                )
    
    # 6. 检查工时参数
    for node in process.nodes:
        if node.std_duration <= 0:
            errors.append(f"节点'{node.step_id}'的标准工时必须大于0")
        if node.time_variance < 0:
            errors.append(f"节点'{node.step_id}'的时间方差不能为负")
        if node.time_variance > node.std_duration:
            warnings.append(
                f"节点'{node.step_id}'的时间方差({node.time_variance})大于标准工时"
                f"({node.std_duration})，可能导致负数工时"
            )
    
    # 7. 检查负荷评分
    for node in process.nodes:
        if node.work_load_score < 1 or node.work_load_score > 10:
            warnings.append(
                f"节点'{node.step_id}'的负荷评分({node.work_load_score})"
                f"超出范围[1-10]"
            )
    
    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def validate_config(config: GlobalConfig) -> Tuple[bool, List[str]]:
    """
    验证全局配置
    
    Args:
        config: 全局配置
        
    Returns:
        (是否有效, 错误列表)
    """
    errors = []
    
    # 排班配置
    if config.work_hours_per_day < 1 or config.work_hours_per_day > 24:
        errors.append("每日工作小时数必须在1-24之间")
    
    if config.work_days_per_month < 1 or config.work_days_per_month > 31:
        errors.append("每月工作天数必须在1-31之间")
    
    if config.num_workers < 1:
        errors.append("工人数量必须大于0")
    
    # 设备配置
    if not config.critical_equipment:
        errors.append("必须配置至少一种关键设备")
    else:
        for name, capacity in config.critical_equipment.items():
            if capacity < 1:
                errors.append(f"设备'{name}'的容量必须大于0")
    
    # 休息参数
    if config.rest_time_threshold <= 0:
        errors.append("休息时间阈值必须大于0")
    
    if config.rest_duration_time < 0:
        errors.append("休息时长不能为负")
    
    if config.rest_load_threshold < 1 or config.rest_load_threshold > 10:
        errors.append("负荷休息阈值必须在1-10之间")
    
    # 生产目标
    if config.target_output < 1:
        errors.append("目标产量必须大于0")
    
    is_valid = len(errors) == 0
    return is_valid, errors


def validate_csv_row(
    row: Dict[str, str],
    row_num: int,
    node_ids: Set[str]
) -> Tuple[bool, List[str], List[str]]:
    """
    验证CSV数据行
    
    Args:
        row: CSV行数据字典
        row_num: 行号
        node_ids: 已存在的节点ID集合
        
    Returns:
        (是否有效, 错误列表, 警告列表)
    """
    errors = []
    warnings = []
    
    # 必填字段
    step_id = row.get('step_id', '').strip()
    if not step_id:
        errors.append(f"第{row_num}行: step_id不能为空")
    elif step_id in node_ids:
        errors.append(f"第{row_num}行: step_id '{step_id}' 重复")
    
    task_name = row.get('task_name', '').strip()
    if not task_name:
        errors.append(f"第{row_num}行: task_name不能为空")
    
    # 操作类型
    op_type = row.get('op_type', '').strip().upper()
    if op_type and op_type not in ['H', 'A', 'M', 'T', 'D']:
        warnings.append(f"第{row_num}行: 未知操作类型 '{op_type}'")
    
    # 数值字段
    try:
        std_duration = float(row.get('std_duration', 0) or 0)
        if std_duration <= 0:
            errors.append(f"第{row_num}行: std_duration必须大于0")
    except ValueError:
        errors.append(f"第{row_num}行: std_duration格式错误")
    
    try:
        time_variance = float(row.get('time_variance', 0) or 0)
        if time_variance < 0:
            errors.append(f"第{row_num}行: time_variance不能为负")
    except ValueError:
        errors.append(f"第{row_num}行: time_variance格式错误")
    
    try:
        work_load = int(row.get('work_load_score', 5) or 5)
        if work_load < 1 or work_load > 10:
            warnings.append(f"第{row_num}行: work_load_score超出范围[1-10]")
    except ValueError:
        warnings.append(f"第{row_num}行: work_load_score格式错误，使用默认值5")
    
    try:
        rework_prob = float(row.get('rework_prob', 0) or 0)
        if rework_prob < 0 or rework_prob > 1:
            errors.append(f"第{row_num}行: rework_prob必须在0-1之间")
    except ValueError:
        errors.append(f"第{row_num}行: rework_prob格式错误")
    
    try:
        required_workers = int(row.get('required_workers', 1) or 1)
        if required_workers < 1:
            errors.append(f"第{row_num}行: required_workers必须大于0")
    except ValueError:
        errors.append(f"第{row_num}行: required_workers格式错误")
    
    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def validate_node_dependencies(
    process: ProcessDefinition,
    critical_equipment: Set[str]
) -> List[str]:
    """
    验证节点资源依赖
    
    检查节点所需的设备是否在关键设备列表中
    
    Args:
        process: 工艺流程定义
        critical_equipment: 关键设备名称集合
        
    Returns:
        警告消息列表
    """
    warnings = []
    
    for node in process.nodes:
        for tool in node.required_tools:
            if tool not in critical_equipment:
                warnings.append(
                    f"节点'{node.step_id}'使用的工具'{tool}'"
                    f"不在关键设备列表中，将视为普通工具（无限供应）"
                )
    
    return warnings


def validate_simulation_request(
    config: GlobalConfig,
    process: ProcessDefinition
) -> Tuple[bool, List[str], List[str]]:
    """
    验证仿真请求
    
    Args:
        config: 全局配置
        process: 工艺流程定义
        
    Returns:
        (是否有效, 错误列表, 警告列表)
    """
    all_errors = []
    all_warnings = []
    
    # 验证配置
    config_valid, config_errors = validate_config(config)
    all_errors.extend(config_errors)
    
    # 验证流程
    process_valid, process_errors, process_warnings = validate_process_definition(process)
    all_errors.extend(process_errors)
    all_warnings.extend(process_warnings)
    
    # 验证资源依赖
    dep_warnings = validate_node_dependencies(
        process, 
        set(config.critical_equipment.keys())
    )
    all_warnings.extend(dep_warnings)
    
    # 检查工人数量是否足够
    max_workers_needed = max(
        (n.required_workers for n in process.nodes),
        default=1
    )
    if max_workers_needed > config.num_workers:
        all_errors.append(
            f"工人数量({config.num_workers})不足以执行"
            f"需要{max_workers_needed}人的任务"
        )
    
    is_valid = len(all_errors) == 0
    return is_valid, all_errors, all_warnings


def check_dag_connectivity(process: ProcessDefinition) -> Dict[str, Any]:
    """
    检查DAG连通性
    
    Args:
        process: 工艺流程定义
        
    Returns:
        连通性分析结果
    """
    graph = nx.DiGraph()
    
    for node in process.nodes:
        graph.add_node(node.step_id)
    for node in process.nodes:
        for pred_id in node.get_predecessor_list():
            if pred_id in {n.step_id for n in process.nodes}:
                graph.add_edge(pred_id, node.step_id)
    
    # 弱连通分量
    weak_components = list(nx.weakly_connected_components(graph))
    
    # 查找孤立节点
    isolated = [n for n in graph.nodes() if graph.degree(n) == 0]
    
    return {
        "is_connected": len(weak_components) == 1,
        "component_count": len(weak_components),
        "components": [list(c) for c in weak_components],
        "isolated_nodes": isolated
    }
