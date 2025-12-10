"""
CSV解析工具
提供工艺流程CSV文件的解析和导出功能

功能:
- 解析工艺流程CSV文件
- 导出工艺流程为CSV
- 导出甘特图数据为CSV
- CSV模板生成
"""

import csv
import io
from typing import List, Tuple, Optional
from dataclasses import dataclass

from app.models.enums import OpType
from app.models.process_model import ProcessNode, ProcessDefinition
from app.models.gantt_model import GanttEvent, GANTT_CSV_HEADERS


# 工艺流程CSV表头
CSV_HEADERS = [
    "step_id",
    "task_name",
    "op_type",
    "predecessors",
    "std_duration",
    "time_variance",
    "work_load_score",
    "rework_prob",
    "required_workers",
    "required_tools"
]

# CSV模板示例数据
CSV_TEMPLATE_DATA = [
    ["S001", "取压气机转子", "H", "", "5", "1", "4", "0", "2", "吊装设备"],
    ["S002", "安装前检查", "M", "S001", "10", "2", "3", "0.05", "1", "检测台"],
    ["S003", "装配前轴承", "A", "S002", "15", "3", "6", "0", "2", "装配台"],
    ["S004", "装配后轴承", "A", "S002", "15", "3", "6", "0", "2", "装配台"],
    ["S005", "安装密封件", "A", "S003;S004", "8", "1.5", "5", "0", "1", ""],
    ["S006", "动平衡测试", "M", "S005", "30", "5", "4", "0.1", "1", "动平衡机"],
    ["S007", "记录测试数据", "D", "S006", "5", "0.5", "2", "0", "1", ""],
    ["S008", "最终装配", "A", "S007", "20", "4", "7", "0", "2", "装配台"],
    ["S009", "试车准备", "T", "S008", "10", "2", "5", "0", "2", "试车台"],
    ["S010", "整机试车", "M", "S009", "60", "10", "6", "0.15", "2", "试车台"],
]


@dataclass
class ParseResult:
    """CSV解析结果"""
    success: bool
    process: Optional[ProcessDefinition] = None
    errors: List[str] = None
    warnings: List[str] = None
    parsed_count: int = 0
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []


def parse_process_csv(
    content: str,
    encoding: str = 'utf-8'
) -> ParseResult:
    """
    解析工艺流程CSV内容
    
    Args:
        content: CSV文件内容字符串
        encoding: 文件编码（用于记录）
        
    Returns:
        ParseResult解析结果
    """
    result = ParseResult(success=False)
    nodes = []
    
    try:
        reader = csv.DictReader(io.StringIO(content))
        
        for row_num, row in enumerate(reader, start=2):
            try:
                # 解析required_tools
                tools_str = row.get('required_tools', '').strip()
                tools = []
                if tools_str:
                    tools = [t.strip() for t in tools_str.split(';') if t.strip()]
                
                # 解析op_type
                op_type_str = row.get('op_type', 'A').strip().upper()
                try:
                    op_type = OpType(op_type_str)
                except ValueError:
                    result.warnings.append(
                        f"第{row_num}行: 未知操作类型 '{op_type_str}'，使用默认值 'A'"
                    )
                    op_type = OpType.A
                
                # 创建节点
                node = ProcessNode(
                    step_id=row.get('step_id', '').strip(),
                    task_name=row.get('task_name', '').strip(),
                    op_type=op_type,
                    predecessors=row.get('predecessors', '').strip(),
                    std_duration=float(row.get('std_duration', 0) or 0),
                    time_variance=float(row.get('time_variance', 0) or 0),
                    work_load_score=int(row.get('work_load_score', 5) or 5),
                    rework_prob=float(row.get('rework_prob', 0) or 0),
                    required_workers=int(row.get('required_workers', 1) or 1),
                    required_tools=tools
                )
                
                # 验证必填字段
                if not node.step_id:
                    result.errors.append(f"第{row_num}行: step_id不能为空")
                    continue
                if not node.task_name:
                    result.errors.append(f"第{row_num}行: task_name不能为空")
                    continue
                
                nodes.append(node)
                result.parsed_count += 1
                
            except Exception as e:
                result.errors.append(f"第{row_num}行解析错误: {str(e)}")
        
        # 检查是否有解析成功的节点
        if nodes:
            result.process = ProcessDefinition(nodes=nodes)
            result.success = len(result.errors) == 0
        else:
            result.errors.append("没有成功解析任何节点")
        
    except Exception as e:
        result.errors.append(f"CSV解析失败: {str(e)}")
    
    return result


def parse_csv_file(file_content: bytes) -> ParseResult:
    """
    解析CSV文件字节内容
    
    Args:
        file_content: 文件字节内容
        
    Returns:
        ParseResult解析结果
    """
    # 尝试不同编码
    encodings = ['utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'latin-1']
    
    for encoding in encodings:
        try:
            text = file_content.decode(encoding)
            return parse_process_csv(text, encoding)
        except UnicodeDecodeError:
            continue
    
    return ParseResult(
        success=False,
        errors=["无法识别文件编码，请使用UTF-8编码"]
    )


def export_process_csv(process: ProcessDefinition) -> str:
    """
    导出工艺流程为CSV字符串
    
    Args:
        process: 工艺流程定义
        
    Returns:
        CSV内容字符串
    """
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 写入表头
    writer.writerow(CSV_HEADERS)
    
    # 写入数据
    for node in process.nodes:
        writer.writerow(node.to_csv_row())
    
    return output.getvalue()


def export_process_csv_bytes(process: ProcessDefinition) -> bytes:
    """
    导出工艺流程为CSV字节（带BOM）
    
    Args:
        process: 工艺流程定义
        
    Returns:
        CSV内容字节（UTF-8 with BOM）
    """
    content = export_process_csv(process)
    return content.encode('utf-8-sig')


def export_gantt_csv(
    events: List[GanttEvent],
    work_hours_per_day: int = 8
) -> str:
    """
    导出甘特图数据为CSV字符串
    
    Args:
        events: 甘特图事件列表
        work_hours_per_day: 每日工作小时数
        
    Returns:
        CSV内容字符串
    """
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 写入表头
    writer.writerow(GANTT_CSV_HEADERS)
    
    # 写入数据
    for event in events:
        writer.writerow(event.to_csv_row(work_hours_per_day))
    
    return output.getvalue()


def export_gantt_csv_bytes(
    events: List[GanttEvent],
    work_hours_per_day: int = 8
) -> bytes:
    """
    导出甘特图数据为CSV字节（带BOM）
    
    Args:
        events: 甘特图事件列表
        work_hours_per_day: 每日工作小时数
        
    Returns:
        CSV内容字节（UTF-8 with BOM）
    """
    content = export_gantt_csv(events, work_hours_per_day)
    return content.encode('utf-8-sig')


def generate_template_csv() -> str:
    """
    生成CSV模板
    
    Returns:
        模板CSV内容字符串
    """
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 写入表头
    writer.writerow(CSV_HEADERS)
    
    # 写入示例数据
    for row in CSV_TEMPLATE_DATA:
        writer.writerow(row)
    
    return output.getvalue()


def generate_template_csv_bytes() -> bytes:
    """
    生成CSV模板字节（带BOM）
    
    Returns:
        模板CSV内容字节
    """
    content = generate_template_csv()
    return content.encode('utf-8-sig')


def validate_csv_headers(headers: List[str]) -> Tuple[bool, List[str]]:
    """
    验证CSV表头
    
    Args:
        headers: CSV表头列表
        
    Returns:
        (是否有效, 缺失字段列表)
    """
    required = {'step_id', 'task_name', 'op_type', 'std_duration'}
    headers_set = set(h.strip().lower() for h in headers)
    
    missing = required - headers_set
    return len(missing) == 0, list(missing)
