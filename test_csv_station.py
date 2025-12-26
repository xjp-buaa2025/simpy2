#!/usr/bin/env python3
"""
测试CSV文件解析是否正确读取工位信息
"""

import os
import sys
from app.utils.csv_parser import parse_csv_file

# 获取CSV文件路径
csv_path = os.path.join(os.getcwd(), 'data', '2.csv')

# 读取文件内容
with open(csv_path, 'rb') as f:
    file_content = f.read()

# 解析CSV文件
result = parse_csv_file(file_content)

# 检查解析结果
if not result.success:
    print("CSV解析失败:")
    for error in result.errors:
        print(f"  - {error}")
    sys.exit(1)

# 打印工位信息
print("工位信息统计:")
print("=" * 50)

station_count = {}
for node in result.process.nodes:
    station = node.station
    station_count[station] = station_count.get(station, 0) + 1
    print(f"节点 {node.step_id} ({node.task_name}) 工位: {station}")

print("\n工位分布:")
print("=" * 50)
for station, count in station_count.items():
    print(f"{station}: {count}个节点")