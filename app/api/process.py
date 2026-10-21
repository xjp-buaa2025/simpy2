"""
工艺流程接口
提供工艺流程的创建、解析、验证和管理功能

API端点:
- GET /api/process/template: 下载CSV模板
- POST /api/process/parse-csv: 解析上传的CSV
- POST /api/process/parse-file: 解析上传的CSV或XLSX
- POST /api/process/validate: 验证工艺流程DAG
- POST /api/process/save: 保存工艺流程
- GET /api/process/example: 获取示例工艺流程
"""

import os
import io
import csv
from urllib.parse import quote
from typing import List, Dict, Any, Optional, Set
from app.models.enums import OpType, OP_TYPE_META
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from app.utils.process_file_parser import ProcessFileError, parse_process_file

router = APIRouter()


# ============ 数据模型 ============

class ProcessNode(BaseModel):
    """工艺节点模型"""
    step_id: str = Field(description="唯一步骤ID")
    task_name: str = Field(description="任务名称")
    op_type: OpType = Field(description="基础行为类型（H/A/M/T/D/S-Move/S-Rest/Coop）")
    predecessors: str = Field(default="", description="前置依赖（分号分隔）")
    std_duration: float = Field(ge=0, description="标准工时（分钟）")
    time_variance: float = Field(default=0.0, ge=0, description="时间波动方差")
    work_load_score: int = Field(default=5, ge=1, le=10, description="REBA负荷评分")
    rework_prob: float = Field(default=0.0, ge=0, le=1, description="返工概率（仅M类有效）")
    required_workers: int = Field(default=1, ge=1, description="所需工人数")
    required_tools: List[str] = Field(default=[], description="所需工具/设备列表")
    station: str = Field(default="ST01", description="工位ID")
    area_id: str = ""
    workstation_id: str = ""
    
    # 前端坐标（用于流程图编辑器）
    x: float = Field(default=0, description="节点X坐标")
    y: float = Field(default=0, description="节点Y坐标")
    
    def get_predecessor_list(self) -> List[str]:
        """解析前置依赖为列表"""
        if not self.predecessors:
            return []
        return [p.strip() for p in self.predecessors.split(";") if p.strip()]
    
    def get_critical_equipment(self, critical_set: Set[str]) -> List[str]:
        """获取关键设备（需要排队的）"""
        return [t for t in self.required_tools if t in critical_set]
    
    def get_common_tools(self, critical_set: Set[str]) -> List[str]:
        """获取普通工具（无限供应）"""
        return [t for t in self.required_tools if t not in critical_set]


class ProcessDefinition(BaseModel):
    """工艺流程定义"""
    name: str = Field(default="未命名流程", description="流程名称")
    description: str = Field(default="", description="流程描述")
    nodes: List[ProcessNode] = Field(default=[], description="工艺节点列表")
    station_catalog: List[Dict[str, str]] = Field(default_factory=list, description="工位编号、工区与显示名称")
    
    def get_node_map(self) -> Dict[str, ProcessNode]:
        """获取节点映射字典"""
        return {node.step_id: node for node in self.nodes}


class APIResponse(BaseModel):
    """统一API响应格式"""
    success: bool
    message: str
    data: Optional[Any] = None


class ValidationResult(BaseModel):
    """验证结果"""
    valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    node_count: int = 0
    edge_count: int = 0
    parallel_groups: int = 0


# ============ CSV模板 ============

CSV_TEMPLATE_HEADERS = [
    "step_id",
    "task_name", 
    "op_type",
    "predecessors",
    "std_duration",
    "time_variance",
    "work_load_score",
    "rework_prob",
    "required_workers",
    "required_tools",
    "station",
    "area_id",
    "workstation_id"
]

CSV_TEMPLATE_EXAMPLE = [
    ["S001", "取压气机转子", "H", "", "5", "1", "4", "0", "2", "吊装设备", "ST01"],
    ["S002", "安装前检查", "M", "S001", "10", "2", "3", "0.05", "1", "检测台", "ST02"],
    ["S003", "装配前轴承", "A", "S002", "15", "3", "6", "0", "2", "装配台", "ST03"],
    ["S004", "装配后轴承", "A", "S002", "15", "3", "6", "0", "2", "装配台", "ST03"],
    ["S005", "安装密封件", "A", "S003;S004", "8", "1.5", "5", "0", "1", "", "ST04"],
    ["S006", "动平衡测试", "M", "S005", "30", "5", "4", "0.1", "1", "动平衡机", "ST05"],
    ["S007", "记录测试数据", "D", "S006", "5", "0.5", "2", "0", "1", "", "ST06"],
    ["S008", "最终装配", "A", "S007", "20", "4", "7", "0", "2", "装配台", "ST07"],
    ["S009", "试车准备", "T", "S008", "10", "2", "5", "0", "2", "试车台", "ST08"],
    ["S010", "整机试车", "M", "S009", "60", "10", "6", "0.15", "2", "试车台", "ST08"],
]


# ============ API端点 ============

@router.get("/template")
async def download_template():
    """
    下载CSV模板
    
    返回工艺流程CSV模板文件，包含表头和示例数据
    """
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 写入表头
    writer.writerow(CSV_TEMPLATE_HEADERS)
    
    # 写入示例数据
    for row in CSV_TEMPLATE_EXAMPLE:
        writer.writerow(row + ["", ""])
    
    output.seek(0)
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),  # 使用BOM便于Excel识别中文
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=process_template.csv"
        }
    )


@router.post("/parse-csv", response_model=APIResponse)
async def parse_csv(file: UploadFile = File(...)):
    """Compatibility entry point; successful data remains a process object."""
    if not (file.filename or "").casefold().endswith(".csv"):
        return APIResponse(success=False, message="请上传CSV格式文件")
    return await parse_file(file)


@router.post("/parse-file", response_model=APIResponse)
async def parse_file(file: UploadFile = File(...)):
    """Parse and validate the entire process before returning any loadable data."""
    try:
        process = parse_process_file(file.filename or "", await file.read())
        return APIResponse(success=True, message=f"成功解析 {len(process.nodes)} 个工艺节点、{len(process.station_catalog)} 个工位", data=process.model_dump())
    except ProcessFileError as error:
        return APIResponse(success=False, message=f"文件导入失败，存在 {len(error.issues)} 个错误",
                           data={"errors": error.errors, "issues": error.issues, "parsed_count": 0})


@router.post("/validate", response_model=APIResponse)
async def validate_process(process: ProcessDefinition):
    """
    验证工艺流程DAG
    
    检查工艺流程的有效性，包括：
    - 节点ID唯一性
    - 依赖关系有效性
    - 无循环依赖
    - 有起始和结束节点
    """
    errors = []
    warnings = []
    
    # 构建节点映射
    node_map = process.get_node_map()
    node_ids = set(node_map.keys())
    
    # 检查节点ID唯一性
    if len(node_ids) != len(process.nodes):
        errors.append("存在重复的节点ID")
    
    # 检查依赖关系
    edge_count = 0
    for node in process.nodes:
        predecessors = node.get_predecessor_list()
        for pred_id in predecessors:
            if pred_id not in node_ids:
                errors.append(f"节点 '{node.step_id}' 的前置依赖 '{pred_id}' 不存在")
            else:
                edge_count += 1
    
    # 检查是否有起始节点（无前置依赖的节点）
    start_nodes = [n for n in process.nodes if not n.get_predecessor_list()]
    if not start_nodes:
        errors.append("没有找到起始节点（所有节点都有前置依赖）")
    
    # 检查循环依赖（简单的DFS检测）
    def has_cycle() -> bool:
        visited = set()
        rec_stack = set()
        
        def dfs(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)
            
            # 获取后继节点
            for n in process.nodes:
                if node_id in n.get_predecessor_list():
                    if n.step_id not in visited:
                        if dfs(n.step_id):
                            return True
                    elif n.step_id in rec_stack:
                        return True
            
            rec_stack.remove(node_id)
            return False
        
        for node in process.nodes:
            if node.step_id not in visited:
                if dfs(node.step_id):
                    return True
        return False
    
    if has_cycle():
        errors.append("流程图存在循环依赖")
    
    # 检查M类型节点的返工概率
    for node in process.nodes:
        if node.op_type == OpType.M and node.rework_prob > 0:
            if node.rework_prob > 0.5:
                warnings.append(f"节点 '{node.step_id}' 返工概率 {node.rework_prob} 较高")
        elif node.op_type != OpType.M and node.rework_prob > 0:
            warnings.append(f"节点 '{node.step_id}' 非测量类型但设置了返工概率")
    
    # 检查工作负荷
    high_load_nodes = [n for n in process.nodes if n.work_load_score >= 8]
    if len(high_load_nodes) > len(process.nodes) * 0.3:
        warnings.append(f"有 {len(high_load_nodes)} 个高负荷节点（≥8分），可能影响工人效率")
    
    # 计算并行组数（简化计算）
    parallel_groups = len(start_nodes)
    
    result = ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        node_count=len(process.nodes),
        edge_count=edge_count,
        parallel_groups=parallel_groups
    )
    
    return APIResponse(
        success=result.valid,
        message="验证通过" if result.valid else f"验证失败，存在 {len(errors)} 个错误",
        data=result.model_dump()
    )


@router.post("/save", response_model=APIResponse)
async def save_process(process: ProcessDefinition):
    """
    保存工艺流程
    
    将工艺流程保存到文件系统
    """
    try:
        # 生成文件名
        filename = f"{process.name.replace(' ', '_')}.json"
        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data"
        )
        os.makedirs(data_dir, exist_ok=True)
        
        filepath = os.path.join(data_dir, filename)
        
        # 保存JSON
        import json
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(process.model_dump(), f, ensure_ascii=False, indent=2)
        
        return APIResponse(
            success=True,
            message=f"流程已保存到 {filename}",
            data={"filepath": filepath}
        )
    except Exception as e:
        return APIResponse(
            success=False,
            message=f"保存失败: {str(e)}"
        )


@router.get("/example", response_model=APIResponse)
async def get_example_process():
    """
    获取示例工艺流程
    
    返回一个完整的示例工艺流程定义
    """
    example_nodes = []
    for i, row in enumerate(CSV_TEMPLATE_EXAMPLE):
        tools = [t.strip() for t in row[9].split(';') if t.strip()] if row[9] else []
        node = ProcessNode(
            step_id=row[0],
            task_name=row[1],
            op_type=OpType(row[2]),
            predecessors=row[3],
            std_duration=float(row[4]),
            time_variance=float(row[5]),
            work_load_score=int(row[6]),
            rework_prob=float(row[7]),
            required_workers=int(row[8]),
            required_tools=tools,
            x=100 + (i % 3) * 200,
            y=100 + (i // 3) * 120
        )
        example_nodes.append(node)
    
    process = ProcessDefinition(
        name="航空发动机装配示例流程",
        description="包含压气机转子装配、动平衡测试和整机试车的标准流程",
        nodes=example_nodes
    )
    
    return APIResponse(
        success=True,
        message="获取示例流程成功",
        data=process.model_dump()
    )


# 复杂示例数据 - 航空发动机完整装配流程（约35个节点，月产3台）
COMPLEX_EXAMPLE_NODES = [
    # 阶段1: 准备与来料检验
    ("S001", "风扇叶片检验", "M", "", 25, 3, 4, 0.03, 1, "检测台"),
    ("S002", "压气机叶片检验", "M", "", 30, 4, 4, 0.04, 1, "检测台"),
    ("S003", "工装准备", "H", "", 20, 2, 4, 0, 2, "装配台"),
    # 阶段2: 低压压气机装配
    ("S101", "低压转子吊装", "H", "S001;S003", 25, 4, 8, 0, 3, "吊车"),
    ("S102", "低压叶片安装", "A", "S101", 90, 10, 7, 0, 2, "装配台"),
    ("S103", "低压压气机测量", "M", "S102", 30, 4, 5, 0.08, 2, "检测台"),
    ("S104", "低压动平衡", "M", "S103", 60, 8, 6, 0.10, 2, "动平衡机"),
    # 阶段3: 高压压气机装配
    ("S201", "高压转子吊装", "H", "S002;S104", 25, 4, 8, 0, 3, "吊车"),
    ("S202", "高压叶片安装", "A", "S201", 150, 15, 7, 0, 2, "装配台"),
    ("S203", "高压压气机测量", "M", "S202", 35, 5, 5, 0.08, 2, "检测台"),
    ("S204", "高压动平衡", "M", "S203", 70, 10, 6, 0.12, 2, "动平衡机"),
    # 阶段4: 燃烧室装配
    ("S301", "燃烧室装配", "A", "S204", 120, 12, 7, 0, 2, "装配台"),
    ("S302", "燃烧室密封检查", "M", "S301", 40, 5, 5, 0.06, 2, "检测台"),
    # 阶段5: 涡轮装配
    ("S401", "涡轮装配", "A", "S302", 180, 18, 8, 0, 2, "装配台"),
    ("S402", "涡轮间隙测量", "M", "S401", 35, 5, 5, 0.08, 2, "检测台"),
    ("S403", "涡轮动平衡", "M", "S402", 75, 10, 6, 0.10, 2, "动平衡机"),
    # 阶段6: 轴系装配
    ("S501", "轴系装配", "A", "S403", 100, 10, 7, 0, 2, "装配台"),
    ("S502", "轴系测量", "M", "S501", 45, 6, 5, 0.06, 2, "检测台"),
    # 阶段7: 附件机匣装配
    ("S601", "附件机匣装配", "A", "S502", 120, 12, 6, 0, 2, "装配台"),
    ("S602", "附件系统检查", "M", "S601", 30, 4, 5, 0.05, 2, "检测台"),
    # 阶段8: 总装
    ("S701", "总装吊装", "H", "S602", 35, 5, 9, 0, 4, "吊车"),
    ("S702", "管路连接", "A", "S701", 150, 15, 6, 0, 2, ""),
    ("S703", "电气安装", "A", "S702", 80, 8, 5, 0, 2, ""),
    # 阶段9: 总装检测
    ("S801", "气密性测试", "M", "S703", 60, 8, 5, 0.05, 2, "检测台"),
    ("S802", "电气测试", "M", "S801", 45, 6, 5, 0.04, 2, "检测台"),
    # 阶段10: 试车
    ("S901", "试车准备", "H", "S802", 40, 5, 6, 0, 2, "试车台"),
    ("S902", "安装试车台", "H", "S901", 50, 6, 8, 0, 4, "试车台;吊车"),
    ("S903", "慢车试车", "M", "S902", 90, 12, 6, 0.08, 3, "试车台"),
    ("S904", "高速试车", "M", "S903", 120, 15, 7, 0.10, 3, "试车台"),
    ("S905", "数据分析", "D", "S904", 60, 8, 4, 0, 2, ""),
    ("S906", "试车后检查", "M", "S905", 45, 6, 5, 0.05, 2, "检测台"),
    # 阶段11: 最终处理
    ("S1001", "下台清洁", "H", "S906", 50, 5, 6, 0, 2, "吊车"),
    ("S1002", "文件整理", "D", "S1001", 40, 5, 3, 0, 1, ""),
    ("S1003", "质量审核", "D", "S1002", 30, 4, 3, 0, 2, ""),
    ("S1004", "包装入库", "H", "S1003", 35, 4, 6, 0, 2, ""),
]


@router.get("/example-complex", response_model=APIResponse)
async def get_complex_example_process():
    """
    获取复杂示例工艺流程
    
    返回航空发动机完整装配流程（约35个节点）
    设计为在人因与资源双重约束下月产约3台发动机
    
    总标准工时约2000分钟（约33小时），考虑：
    - 6名工人，部分任务需要2-4人
    - 关键设备约束（动平衡机2台、试车台1台等）
    - 休息规则（连续工作50分钟休息、高负荷任务后休息）
    - 返工概率（M类型任务5%-12%返工率）
    """
    nodes = []
    for i, row in enumerate(COMPLEX_EXAMPLE_NODES):
        tools = [t.strip() for t in row[9].split(';') if t.strip()] if row[9] else []
        node = ProcessNode(
            step_id=row[0],
            task_name=row[1],
            op_type=OpType(row[2]),
            predecessors=row[3],
            std_duration=float(row[4]),
            time_variance=float(row[5]),
            work_load_score=int(row[6]),
            rework_prob=float(row[7]),
            required_workers=int(row[8]),
            required_tools=tools,
            x=100 + (i % 4) * 180,
            y=80 + (i // 4) * 90
        )
        nodes.append(node)
    
    process = ProcessDefinition(
        name="航空发动机完整装配流程",
        description="完整的航空发动机装配流程，包含11个阶段35个工序，设计月产量约3台",
        nodes=nodes
    )
    
    return APIResponse(
        success=True,
        message="获取复杂示例流程成功（35个节点，预计月产3台）",
        data=process.model_dump()
    )


@router.get("/op-types", response_model=APIResponse)
async def get_op_types():
    """
    获取操作类型元数据
    
    返回所有操作类型的中英文名称、颜色和图标
    """
    data = []
    for op_type in OpType:
        meta = OP_TYPE_META[op_type]
        data.append({
            "value": op_type.value,
            "zh": meta["zh"],
            "en": meta["en"],
            "color": meta["color"],
            "icon": meta["icon"]
        })
    
    return APIResponse(
        success=True,
        message="获取操作类型成功",
        data=data
    )


@router.post("/export-csv", response_model=None)
async def export_process_csv(process: ProcessDefinition):
    """
    导出工艺流程为CSV
    """
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 写入表头
    writer.writerow(CSV_TEMPLATE_HEADERS)
    
    # 写入数据
    for node in process.nodes:
        writer.writerow([
            node.step_id,
            node.task_name,
            node.op_type.value,
            node.predecessors,
            node.std_duration,
            node.time_variance,
            node.work_load_score,
            node.rework_prob,
            node.required_workers,
            ";".join(node.required_tools),
            node.station,
            node.area_id,
            node.workstation_id
        ])
    
    output.seek(0)
    filename = f"{process.name.replace(' ', '_')}.csv"
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=process.csv; filename*=UTF-8''" + quote(filename)
        }
    )
