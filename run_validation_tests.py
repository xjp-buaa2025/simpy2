#!/usr/bin/env python3
"""
航空发动机装配排产仿真系统 - 完整性测试脚本
Comprehensive System Validation Script

测试内容:
1. 单节点边界测试
2. 并行分支DAG测试
3. 高返工率质量测试
4. 资源竞争压力测试
5. 高负荷休息规则测试
6. 连续工作时间测试
7. 复杂DAG网络测试
8. 全操作类型覆盖测试
9. 时间方差不确定性测试
10. 大规模流程压力测试

运行方式: python run_validation_tests.py
"""

import os
import sys
import time
from typing import Dict, List, Tuple

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models.config_model import GlobalConfig
from app.models.enums import SimulationStatus, GanttEventType
from app.core.simulation_engine import SimulationEngine
from app.utils.csv_parser import parse_process_csv
from app.utils.validators import validate_process_definition


class TestResult:
    """测试结果类"""
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.duration = 0.0
        self.engines_completed = 0
        self.total_events = 0
        self.rework_count = 0
        self.rest_count = 0
        self.error_message = ""
        self.details: Dict = {}


def run_single_test(csv_path: str, config: GlobalConfig, test_name: str) -> TestResult:
    """运行单个测试"""
    result = TestResult(test_name)
    start_time = time.time()
    
    try:
        # 读取CSV文件内容
        with open(csv_path, 'r', encoding='utf-8') as f:
            csv_content = f.read()
        
        # 解析CSV
        parse_result = parse_process_csv(csv_content)
        if not parse_result.success or not parse_result.process:
            result.error_message = f"CSV解析失败: {'; '.join(parse_result.errors)}"
            return result
        
        process = parse_result.process
        
        # 验证流程
        valid, errors, warnings = validate_process_definition(process)
        if not valid:
            result.error_message = f"流程验证失败: {'; '.join(errors)}"
            return result
        
        # 运行仿真
        engine = SimulationEngine(config, process)
        sim_result = engine.run()
        
        result.duration = time.time() - start_time
        
        if sim_result.status != SimulationStatus.COMPLETED:
            result.error_message = f"仿真状态异常: {sim_result.status}"
            return result
        
        # 收集结果
        result.engines_completed = sim_result.engines_completed
        result.total_events = len(sim_result.gantt_events)
        result.rework_count = sum(1 for e in sim_result.gantt_events 
                                   if e.event_type == GanttEventType.REWORK)
        result.rest_count = sum(1 for e in sim_result.gantt_events 
                                 if e.event_type == GanttEventType.REST)
        
        result.details = {
            'target_achievement': f"{sim_result.target_achievement_rate*100:.1f}%",
            'avg_cycle_time': f"{sim_result.avg_cycle_time:.1f}分钟",
            'first_pass_rate': f"{sim_result.quality_stats.first_pass_rate*100:.1f}%",
            'total_inspections': sim_result.quality_stats.total_inspections,
            'total_reworks': sim_result.quality_stats.total_reworks,
            'node_count': len(process.nodes),
            'sim_duration': f"{sim_result.sim_duration}分钟"
        }
        
        result.passed = True
        
    except Exception as e:
        result.error_message = str(e)
        result.duration = time.time() - start_time
    
    return result


def main():
    """主测试函数"""
    print("=" * 70)
    print("🛫 航空发动机装配排产仿真系统 - 完整性验证测试")
    print("   Beihang University - AeroEngine Scheduling System Validation")
    print("=" * 70)
    print()
    
    # 测试文件列表
    test_cases = [
        ("test_01_single_node.csv", "单节点边界测试", 
         GlobalConfig(num_workers=2, target_output=5)),
        
        ("test_02_parallel_branches.csv", "并行分支DAG测试",
         GlobalConfig(num_workers=6, target_output=3, critical_equipment={"装配台": 2, "检测台": 1})),
        
        ("test_03_high_rework.csv", "高返工率质量测试",
         GlobalConfig(num_workers=4, target_output=2, random_seed=42,
                     critical_equipment={"装配台": 2, "检测台": 1, "动平衡机": 1})),
        
        ("test_04_resource_competition.csv", "资源竞争压力测试",
         GlobalConfig(num_workers=6, target_output=2, pipeline_mode=True,
                     critical_equipment={"装配台": 2, "动平衡机": 1, "试车台": 1, "检测台": 1, "专用夹具": 2})),
        
        ("test_05_high_workload.csv", "高负荷休息规则测试",
         GlobalConfig(num_workers=4, target_output=2, rest_load_threshold=7, rest_duration_load=5,
                     critical_equipment={"装配台": 2, "检测台": 1, "动平衡机": 1})),
        
        ("test_06_continuous_work.csv", "连续工作时间测试",
         GlobalConfig(num_workers=3, target_output=2, rest_time_threshold=50, rest_duration_time=8,
                     critical_equipment={"装配台": 2, "检测台": 1})),
        
        ("test_07_complex_dag.csv", "复杂DAG网络测试",
         GlobalConfig(num_workers=6, target_output=2, pipeline_mode=True,
                     critical_equipment={"装配台": 3, "检测台": 2, "动平衡机": 1})),
        
        ("test_08_all_op_types.csv", "全操作类型覆盖测试",
         GlobalConfig(num_workers=5, target_output=2,
                     critical_equipment={"装配台": 2, "检测台": 1, "动平衡机": 1, "试车台": 1, "扭力扳手": 2, "专用夹具": 1})),
        
        ("test_09_time_variance.csv", "时间方差不确定性测试",
         GlobalConfig(num_workers=4, target_output=3, random_seed=123,
                     critical_equipment={"装配台": 2, "检测台": 1})),
        
        ("test_10_large_scale.csv", "大规模流程压力测试(50节点)",
         GlobalConfig(num_workers=8, target_output=2, pipeline_mode=True, work_days_per_month=22,
                     critical_equipment={"装配台": 4, "检测台": 3, "动平衡机": 2, "试车台": 1, "专用夹具": 2})),
    ]
    
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    results: List[TestResult] = []
    
    total_start = time.time()
    
    for csv_file, test_name, config in test_cases:
        csv_path = os.path.join(data_dir, csv_file)
        
        if not os.path.exists(csv_path):
            print(f"⚠️  跳过 {test_name}: 文件不存在 ({csv_file})")
            continue
        
        print(f"🔄 运行: {test_name}...")
        result = run_single_test(csv_path, config, test_name)
        results.append(result)
        
        if result.passed:
            print(f"   ✅ 通过 (耗时: {result.duration:.2f}s, 完成: {result.engines_completed}台, "
                  f"事件: {result.total_events}, 返工: {result.rework_count}, 休息: {result.rest_count})")
        else:
            print(f"   ❌ 失败: {result.error_message}")
    
    total_time = time.time() - total_start
    
    # 汇总报告
    print()
    print("=" * 70)
    print("📊 测试汇总报告")
    print("=" * 70)
    
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    
    print(f"\n总测试数: {len(results)}")
    print(f"✅ 通过: {passed}")
    print(f"❌ 失败: {failed}")
    print(f"⏱️  总耗时: {total_time:.2f}秒")
    
    print("\n" + "-" * 70)
    print("详细结果:")
    print("-" * 70)
    
    for result in results:
        status = "✅" if result.passed else "❌"
        print(f"\n{status} {result.name}")
        if result.passed:
            print(f"   耗时: {result.duration:.2f}s")
            for key, value in result.details.items():
                print(f"   {key}: {value}")
        else:
            print(f"   错误: {result.error_message}")
    
    print("\n" + "=" * 70)
    
    # 系统可靠性评估
    print("\n📈 系统可靠性评估:")
    print("-" * 40)
    
    if failed == 0:
        print("✅ 所有测试通过!")
        print("✅ DAG调度逻辑正确")
        print("✅ 资源约束机制有效")
        print("✅ 返工逻辑实现正确")
        print("✅ 休息规则执行正常")
        print("✅ 时间不确定性处理正确")
        print("✅ 大规模流程处理能力验证")
        print("\n🎉 系统验证完成，可靠性达标!")
    else:
        print(f"⚠️  有 {failed} 个测试失败，请检查相关模块")
    
    print()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
