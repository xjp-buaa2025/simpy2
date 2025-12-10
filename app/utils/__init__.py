"""
工具函数包
提供各种辅助功能

模块说明:
- csv_parser.py: CSV解析工具
- time_converter.py: 时间转换工具
- statistics.py: KPI统计计算
- validators.py: 数据验证工具
"""

from app.utils.csv_parser import (
    parse_process_csv,
    parse_csv_file,
    export_process_csv,
    export_process_csv_bytes,
    export_gantt_csv,
    export_gantt_csv_bytes,
    generate_template_csv,
    generate_template_csv_bytes,
    validate_csv_headers,
    CSV_HEADERS,
    CSV_TEMPLATE_DATA,
    ParseResult,
)

from app.utils.time_converter import (
    minutes_to_day_hour,
    minutes_to_day_hour_dict,
    day_hour_to_minutes,
    parse_day_hour_string,
    format_duration,
    format_duration_short,
    get_time_range,
    calculate_calendar_info,
    split_time_into_days,
)

from app.utils.statistics import (
    calculate_kpi,
    calculate_utilization_rate,
    calculate_first_pass_rate,
    calculate_avg_cycle_time,
    calculate_worker_statistics,
    calculate_equipment_statistics,
    calculate_event_statistics,
    generate_kpi_report,
)

from app.utils.validators import (
    validate_process_definition,
    validate_config,
    validate_csv_row,
    validate_node_dependencies,
    validate_simulation_request,
    check_dag_connectivity,
)

__all__ = [
    # CSV解析
    "parse_process_csv",
    "parse_csv_file",
    "export_process_csv",
    "export_process_csv_bytes",
    "export_gantt_csv",
    "export_gantt_csv_bytes",
    "generate_template_csv",
    "generate_template_csv_bytes",
    "validate_csv_headers",
    "CSV_HEADERS",
    "CSV_TEMPLATE_DATA",
    "ParseResult",
    # 时间转换
    "minutes_to_day_hour",
    "minutes_to_day_hour_dict",
    "day_hour_to_minutes",
    "parse_day_hour_string",
    "format_duration",
    "format_duration_short",
    "get_time_range",
    "calculate_calendar_info",
    "split_time_into_days",
    # 统计
    "calculate_kpi",
    "calculate_utilization_rate",
    "calculate_first_pass_rate",
    "calculate_avg_cycle_time",
    "calculate_worker_statistics",
    "calculate_equipment_statistics",
    "calculate_event_statistics",
    "generate_kpi_report",
    # 验证
    "validate_process_definition",
    "validate_config",
    "validate_csv_row",
    "validate_node_dependencies",
    "validate_simulation_request",
    "check_dag_connectivity",
]
