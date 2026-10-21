/**
 * 分析模块 - 瓶颈分析、设备分析、工位分析
 */

function analyzeBottlenecks(result) {
    const loadingEl = document.getElementById('bottleneckLoading');
    const contentEl = document.getElementById('bottleneckContent');
    
    loadingEl.style.display = 'block';
    loadingEl.textContent = '正在分析瓶颈...';
    contentEl.style.display = 'none';
    
    try {
        const analysis = performBottleneckAnalysis(result);
        displayBottleneckAnalysis(analysis);
        loadingEl.style.display = 'none';
        contentEl.style.display = 'block';
    } catch (error) {
        console.error('瓶颈分析失败:', error);
        loadingEl.textContent = '瓶颈分析失败: ' + error.message;
    }
}

function performBottleneckAnalysis(result) {
    const bottlenecks = [];
    const recommendations = [];
    
    // 构建任务到设备的映射 - 从NORMAL事件获取实际使用的设备
    const taskEquipmentMap = {};
    (result.gantt_events || []).forEach(event => {
        if (event.event_type === 'NORMAL' && event.equipment_used && event.equipment_used.length > 0) {
            if (!taskEquipmentMap[event.step_id]) {
                taskEquipmentMap[event.step_id] = new Set();
            }
            event.equipment_used.forEach(equip => taskEquipmentMap[event.step_id].add(equip));
        }
    });
    // 转换Set为Array
    Object.keys(taskEquipmentMap).forEach(stepId => {
        taskEquipmentMap[stepId] = Array.from(taskEquipmentMap[stepId]);
    });
    
    // 同时从state.nodes获取（作为补充）
    if (state.nodes && state.nodes.length > 0) {
        state.nodes.forEach(node => {
            if (node.required_tools && node.required_tools.trim()) {
                const tools = node.required_tools.split(/[;；,，]/).map(t => t.trim()).filter(t => t);
                if (!taskEquipmentMap[node.step_id]) {
                    taskEquipmentMap[node.step_id] = tools;
                } else {
                    // 合并
                    tools.forEach(t => {
                        if (!taskEquipmentMap[node.step_id].includes(t)) {
                            taskEquipmentMap[node.step_id].push(t);
                        }
                    });
                }
            }
        });
    }
    
    // 构建设备利用率映射 - 从设备统计获取
    const equipUtilization = {};
    const allEquipmentNames = new Set();
    result.equipment_stats.forEach(equip => {
        equipUtilization[equip.resource_id] = equip.utilization_rate || 0;
        allEquipmentNames.add(equip.resource_id);
    });
    
    // 获取关键设备列表（从配置中）
    const criticalEquipConfig = result.config?.critical_equipment || state.config?.criticalEquipment || {};
    let criticalEquipSet = new Set(Object.keys(criticalEquipConfig));
    
    // 如果没有配置关键设备，使用设备统计中的所有设备
    if (criticalEquipSet.size === 0) {
        criticalEquipSet = allEquipmentNames;
    }
    
    // 构建设备到任务的反向映射（从gantt_events分析）
    const equipmentToTasks = {};
    (result.gantt_events || []).forEach(event => {
        if (event.event_type === 'NORMAL' && event.equipment_used) {
            const taskName = event.task_name.replace(/\(.*\)/, '').trim();
            event.equipment_used.forEach(equip => {
                if (!equipmentToTasks[equip]) {
                    equipmentToTasks[equip] = new Set();
                }
                equipmentToTasks[equip].add(taskName);
            });
        }
    });
    
    console.log('=== 瓶颈分析调试信息 ===');
    console.log('设备统计:', result.equipment_stats);
    console.log('关键设备配置:', criticalEquipConfig);
    console.log('关键设备集合:', Array.from(criticalEquipSet));
    console.log('任务-设备映射:', taskEquipmentMap);
    console.log('设备-任务映射:', equipmentToTasks);
    console.log('设备利用率:', equipUtilization);
    
    // 1. 分析设备瓶颈
    result.equipment_stats.forEach(equip => {
        const utilRate = equip.utilization_rate || 0;
        let severity = null;
        let impact = '';
        let suggestion = '';
        
        if (utilRate >= 0.9) {
            severity = 'high';
            impact = `设备 ${equip.resource_id} 利用率高达 ${(utilRate*100).toFixed(1)}%，严重制约产能`;
            suggestion = `建议增加 ${equip.resource_id} 数量或优化使用该设备的工序`;
        } else if (utilRate >= 0.8) {
            severity = 'medium';
            impact = `设备 ${equip.resource_id} 利用率 ${(utilRate*100).toFixed(1)}%，接近满负荷`;
            suggestion = `关注 ${equip.resource_id} 使用情况，必要时考虑增加设备`;
        } else if (utilRate >= 0.7) {
            severity = 'low';
            impact = `设备 ${equip.resource_id} 利用率 ${(utilRate*100).toFixed(1)}%，负荷较高`;
            suggestion = `可考虑优化 ${equip.resource_id} 的使用调度`;
        }
        
        if (severity) {
            bottlenecks.push({
                resource_type: 'equipment',
                resource_id: equip.resource_id,
                bottleneck_type: 'high_utilization',
                severity: severity,
                utilization_rate: utilRate,
                impact_description: impact,
                suggestion: suggestion
            });
        }
    });
    
    // 3. 分析等待时间瓶颈 - 增强版，关联具体设备
    const waitEvents = (result.gantt_events || []).filter(e => e.event_type === 'WAITING');
    const stepWaitTimes = {};
    const equipmentWaitStats = {}; // 统计每个设备造成的等待
    
    // 找出利用率最高的设备（作为默认瓶颈候选）
    const topUtilEquipment = Object.entries(equipUtilization)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 3)
        .map(([name, util]) => ({ name, util }));
    
    waitEvents.forEach(event => {
        const stepId = event.step_id;
        const waitTime = event.end_time - event.start_time;
        const taskName = event.task_name.replace('(等待)', '').trim();
        
        // 获取该任务需要的设备
        let requiredEquipment = taskEquipmentMap[stepId] || [];
        
        // 如果没有直接映射，尝试从设备到任务的反向映射查找
        if (requiredEquipment.length === 0) {
            Object.entries(equipmentToTasks).forEach(([equip, tasks]) => {
                if (tasks.has(taskName)) {
                    requiredEquipment.push(equip);
                }
            });
        }
        
        if (!stepWaitTimes[stepId]) {
            stepWaitTimes[stepId] = { 
                times: [], 
                taskName: taskName,
                requiredEquipment: requiredEquipment
            };
        }
        stepWaitTimes[stepId].times.push(waitTime);
        
        // 统计每个关键设备导致的等待时间
        requiredEquipment.forEach(equip => {
            if (criticalEquipSet.has(equip) || allEquipmentNames.has(equip)) {
                if (!equipmentWaitStats[equip]) {
                    equipmentWaitStats[equip] = { 
                        totalWaitTime: 0, 
                        waitCount: 0,
                        affectedTasks: new Set()
                    };
                }
                equipmentWaitStats[equip].totalWaitTime += waitTime;
                equipmentWaitStats[equip].waitCount++;
                equipmentWaitStats[equip].affectedTasks.add(taskName);
            }
        });
    });
    
    // 分析哪个设备是主要瓶颈
    const equipmentBottleneckRanking = Object.entries(equipmentWaitStats)
        .map(([equip, stats]) => ({
            equipment: equip,
            totalWaitTime: stats.totalWaitTime,
            waitCount: stats.waitCount,
            affectedTasks: Array.from(stats.affectedTasks),
            utilization: equipUtilization[equip] || 0
        }))
        .sort((a, b) => b.totalWaitTime - a.totalWaitTime);
    
    // 添加设备导致的等待瓶颈
    equipmentBottleneckRanking.forEach(item => {
        if (item.totalWaitTime >= 60) { // 总等待时间超过60分钟
            const severity = item.totalWaitTime >= 180 ? 'high' : (item.totalWaitTime >= 120 ? 'medium' : 'low');
            bottlenecks.push({
                resource_type: 'equipment_wait',
                resource_id: item.equipment,
                bottleneck_type: 'equipment_caused_wait',
                severity: severity,
                wait_time: item.totalWaitTime,
                utilization_rate: item.utilization,
                affected_tasks: item.affectedTasks,
                impact_description: `设备 "${item.equipment}" 导致等待 ${item.waitCount} 次，总等待 ${item.totalWaitTime.toFixed(0)} 分钟，利用率 ${(item.utilization*100).toFixed(1)}%`,
                suggestion: `增加 "${item.equipment}" 数量可减少 ${item.affectedTasks.length} 个任务的等待时间`
            });
        }
    });
    
    // 添加任务等待瓶颈（包含设备信息）
    Object.entries(stepWaitTimes).forEach(([stepId, info]) => {
        const avgWait = info.times.reduce((a, b) => a + b, 0) / info.times.length;
        const totalWait = info.times.reduce((a, b) => a + b, 0);
        
        if (avgWait >= 30 || totalWait / result.sim_duration >= 0.05) {
            // 找出导致等待的关键设备
            let criticalEquipInvolved = info.requiredEquipment.filter(e => 
                criticalEquipSet.has(e) || allEquipmentNames.has(e)
            );
            
            // 如果没有找到关联设备，尝试分析可能的原因
            let equipInfo = '';
            let bottleneckEquip = null;
            let maxUtil = 0;
            
            if (criticalEquipInvolved.length > 0) {
                equipInfo = `，涉及关键设备: ${criticalEquipInvolved.join(', ')}`;
                
                // 找出最可能的瓶颈设备（利用率最高的）
                criticalEquipInvolved.forEach(equip => {
                    const util = equipUtilization[equip] || 0;
                    if (util > maxUtil) {
                        maxUtil = util;
                        bottleneckEquip = equip;
                    }
                });
            } else {
                // 没有直接关联，检查工人利用率和设备利用率
                const avgWorkerUtil = result.worker_stats.reduce((s, w) => s + (w.utilization_rate || 0), 0) / result.worker_stats.length;
                
                if (avgWorkerUtil >= 0.8) {
                    equipInfo = '，主要原因: 工人不足 (利用率' + (avgWorkerUtil * 100).toFixed(0) + '%)';
                } else if (topUtilEquipment.length > 0 && topUtilEquipment[0].util >= 0.7) {
                    // 推测可能是高利用率设备导致
                    const possibleEquip = topUtilEquipment[0];
                    equipInfo = `，可能的瓶颈设备: ${possibleEquip.name} (利用率${(possibleEquip.util * 100).toFixed(0)}%)`;
                    bottleneckEquip = possibleEquip.name;
                    maxUtil = possibleEquip.util;
                } else {
                    equipInfo = '，原因: 前置任务未完成或资源竞争';
                }
            }
            
            const bottleneckInfo = (bottleneckEquip && criticalEquipInvolved.length > 0)
                ? `，主要瓶颈: ${bottleneckEquip} (利用率${(maxUtil*100).toFixed(0)}%)`
                : '';
            
            bottlenecks.push({
                resource_type: 'task',
                resource_id: stepId,
                bottleneck_type: 'long_wait',
                severity: avgWait >= 60 ? 'high' : 'medium',
                wait_time: avgWait,
                related_equipment: criticalEquipInvolved,
                bottleneck_equipment: bottleneckEquip,
                impact_description: `任务 '${info.taskName}' 平均等待 ${avgWait.toFixed(1)} 分钟${equipInfo}${bottleneckInfo}`,
                suggestion: bottleneckEquip 
                    ? `建议增加 "${bottleneckEquip}" 数量以减少任务 '${info.taskName}' 的等待`
                    : `检查任务 '${info.taskName}' 所需资源是否充足`
            });
        }
    });
    
    // 4. 分析返工瓶颈
    const reworkEvents = (result.gantt_events || []).filter(e => e.event_type === 'REWORK');
    const stepReworkInfo = {};
    reworkEvents.forEach(event => {
        const stepId = event.step_id;
        if (!stepReworkInfo[stepId]) {
            stepReworkInfo[stepId] = { count: 0, totalTime: 0, taskName: event.task_name.replace(/\(返工.*\)/, '').trim() };
        }
        stepReworkInfo[stepId].count++;
        stepReworkInfo[stepId].totalTime += (event.end_time - event.start_time);
    });
    
    Object.entries(stepReworkInfo).forEach(([stepId, info]) => {
        if (info.count >= 3 || info.totalTime >= 60) {
            bottlenecks.push({
                resource_type: 'task',
                resource_id: stepId,
                bottleneck_type: 'frequent_rework',
                severity: info.count >= 5 ? 'high' : 'medium',
                wait_time: info.totalTime,
                impact_description: `任务 '${info.taskName}' 返工 ${info.count} 次，耗时 ${info.totalTime.toFixed(1)} 分钟`,
                suggestion: `检查任务 '${info.taskName}' 的质量控制流程`
            });
        }
    });
    
    // 按严重程度排序
    const severityOrder = { high: 0, medium: 1, low: 2 };
    bottlenecks.sort((a, b) => severityOrder[a.severity] - severityOrder[b.severity]);
    
    // 生成汇总
    const highCount = bottlenecks.filter(b => b.severity === 'high').length;
    const mediumCount = bottlenecks.filter(b => b.severity === 'medium').length;
    const lowCount = bottlenecks.filter(b => b.severity === 'low').length;
    
    // 计算效率评分
    let score = 100;
    score -= highCount * 10;
    score -= mediumCount * 5;
    if (result.quality_stats && result.quality_stats.first_pass_rate < 0.9) {
        score -= (0.9 - result.quality_stats.first_pass_rate) * 20;
    }
    score = Math.max(0, Math.min(100, score));
    
    // 生成建议
    const equipBottlenecks = bottlenecks.filter(b => b.resource_type === 'equipment' && b.severity === 'high');
    if (equipBottlenecks.length > 0) {
        recommendations.push(`【优先】增加关键设备容量：${equipBottlenecks.map(b => b.resource_id).join(', ')}。这些设备利用率过高，是当前主要产能瓶颈。`);
    }
    
    // 设备导致等待的瓶颈建议
    const equipWaitBottlenecks = bottlenecks.filter(b => b.bottleneck_type === 'equipment_caused_wait');
    if (equipWaitBottlenecks.length > 0) {
        const topEquip = equipWaitBottlenecks.slice(0, 3);
        recommendations.push(`【设备瓶颈】以下设备导致大量等待：${topEquip.map(b => `${b.resource_id}(等待${b.wait_time.toFixed(0)}分钟)`).join(', ')}。建议优先增加这些设备数量。`);
    }
    
    const reworkBottlenecks = bottlenecks.filter(b => b.bottleneck_type === 'frequent_rework');
    if (reworkBottlenecks.length > 0) {
        recommendations.push(`【质量】关注高返工率任务：${reworkBottlenecks.slice(0, 3).map(b => b.resource_id).join(', ')}。建议加强质量控制。`);
    }
    
    if (bottlenecks.length === 0)recommendations.push('本次评估未发现明显资源瓶颈，可通过同条件改善仿真比较实际产出。');

    return {
        bottlenecks: bottlenecks,
        summary: {
            total_bottlenecks: bottlenecks.length,
            by_severity: { high: highCount, medium: mediumCount, low: lowCount },
            efficiency_score: score
        },
        recommendations: recommendations
    };
}

// 保留API调用作为备选
async function fetchBottleneckAnalysis(simId) {
    const loadingEl = document.getElementById('bottleneckLoading');
    const contentEl = document.getElementById('bottleneckContent');
    
    loadingEl.style.display = 'block';
    loadingEl.textContent = '正在分析瓶颈...';
    contentEl.style.display = 'none';
    
    try {
        const response = await fetch(`/api/results/${simId}/bottleneck`);
        const data = await response.json();
        
        if (data.success) {
            displayBottleneckAnalysis(data.data);
            loadingEl.style.display = 'none';
            contentEl.style.display = 'block';
        } else {
            loadingEl.textContent = '瓶颈分析失败: ' + data.message;
        }
    } catch (error) {
        console.error('获取瓶颈分析失败:', error);
        loadingEl.textContent = '获取瓶颈分析失败';
    }
}

function displayBottleneckAnalysis(analysis) {
    const { bottlenecks, summary, recommendations } = analysis;
    
    // 更新汇总数据
    document.getElementById('bottleneckTotal').textContent = summary.total_bottlenecks || 0;
    document.getElementById('bottleneckHigh').textContent = summary.by_severity?.high || 0;
    document.getElementById('bottleneckMedium').textContent = summary.by_severity?.medium || 0;
    document.getElementById('efficiencyScore').textContent = (summary.efficiency_score || 0).toFixed(0) + '分';
    
    // 显示瓶颈列表
    const listEl = document.getElementById('bottleneckList');
    if (bottlenecks.length === 0) {
        listEl.innerHTML = '<div style="text-align: center; color: var(--accent-green); padding: 1rem;">✅ 未检测到明显瓶颈，生产状态良好</div>';
    } else {
        listEl.innerHTML = bottlenecks.map(b => {
            const severityColors = {
                'high': { bg: 'rgba(239,68,68,0.1)', border: 'var(--accent-red)', icon: '🔴' },
                'medium': { bg: 'rgba(245,158,11,0.1)', border: 'var(--accent-orange)', icon: '🟡' },
                'low': { bg: 'rgba(16,185,129,0.1)', border: 'var(--accent-green)', icon: '🟢' }
            };
            const color = severityColors[b.severity] || severityColors.low;
            
            const typeLabels = {
                'equipment': '设备',
                'equipment_wait': '设备瓶颈',
                'worker': '工人',
                'task': '任务'
            };
            const typeLabel = typeLabels[b.resource_type] || b.resource_type;
            
            const bottleneckTypeLabels = {
                'high_utilization': '高利用率',
                'long_wait': '长等待',
                'frequent_rework': '频繁返工',
                'equipment_caused_wait': '设备导致等待'
            };
            const btLabel = bottleneckTypeLabels[b.bottleneck_type] || b.bottleneck_type;
            
            // 为设备瓶颈添加额外信息
            let extraInfo = '';
            if (b.bottleneck_equipment) {
                extraInfo = `<div style="font-size: 0.75rem; color: var(--accent-orange); margin-top: 0.25rem;">🔧 瓶颈设备: ${b.bottleneck_equipment}</div>`;
            }
            if (b.affected_tasks && b.affected_tasks.length > 0) {
                extraInfo += `<div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.25rem;">📋 影响任务: ${b.affected_tasks.slice(0, 3).join(', ')}${b.affected_tasks.length > 3 ? '...' : ''}</div>`;
            }
            
            return `
                <div style="padding: 0.75rem; margin-bottom: 0.5rem; background: ${color.bg}; border-left: 3px solid ${color.border}; border-radius: 4px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;">
                        <span style="font-weight: 600;">${color.icon} [${typeLabel}] ${b.resource_id}</span>
                        <span style="font-size: 0.75rem; padding: 0.125rem 0.5rem; background: ${color.border}; color: white; border-radius: 10px;">${btLabel}</span>
                    </div>
                    <div style="font-size: 0.875rem; color: var(--text-secondary); margin-bottom: 0.25rem;">${b.impact_description}</div>
                    ${extraInfo}
                    <div style="font-size: 0.75rem; color: var(--accent-cyan);">💡 ${b.suggestion}</div>
                </div>
            `;
        }).join('');
    }
    
    // 显示改进建议
    const recsEl = document.getElementById('bottleneckRecommendations');
    if (recommendations.length === 0) {
        recsEl.innerHTML = '<div style="color: var(--accent-green);">当前生产状态良好，暂无改进建议。</div>';
    } else {
        recsEl.innerHTML = recommendations.map((rec, idx) => 
            `<div style="margin-bottom: 0.5rem; padding-left: 1rem; border-left: 2px solid var(--accent-cyan);">${idx + 1}. ${rec}</div>`
        ).join('');
    }
}

// ============ 设备详情功能 ============
function updateEquipmentDetails(result) {
    const loadingEl = document.getElementById('equipmentDetailLoading');
    const contentEl = document.getElementById('equipmentDetailContent');
    const criticalListEl = document.getElementById('criticalEquipmentList');
    const unlimitedListEl = document.getElementById('unlimitedEquipmentList');
    
    // 从配置中获取关键设备列表
    const criticalEquipConfig = result.config?.critical_equipment || state.config?.criticalEquipment || {};
    const criticalEquipNames = new Set(Object.keys(criticalEquipConfig));
    
    // 分类设备
    const criticalEquipment = [];
    const unlimitedEquipment = [];
    const usedEquipmentNames = new Set();
    
    // 从设备统计中获取
    result.equipment_stats.forEach(stat => {
        usedEquipmentNames.add(stat.resource_id);
        const isCritical = criticalEquipNames.has(stat.resource_id) || stat.is_unlimited === false;
        
        if (isCritical && !stat.is_unlimited) {
            criticalEquipment.push({
                name: stat.resource_id,
                capacity: criticalEquipConfig[stat.resource_id] || 1,
                utilization: stat.utilization_rate,
                workTime: stat.work_time,
                tasksServed: stat.tasks_completed,
                isBottleneck: stat.utilization_rate > 0.8
            });
        } else {
            unlimitedEquipment.push({
                name: stat.resource_id,
                workTime: stat.work_time,
                tasksServed: stat.tasks_completed,
                maxConcurrent: stat.max_concurrent_usage || '-'
            });
        }
    });
    
    // 渲染关键设备
    if (criticalEquipment.length === 0) {
        criticalListEl.innerHTML = '<div style="color: var(--text-secondary); padding: 0.5rem;">无关键设备配置</div>';
    } else {
        criticalListEl.innerHTML = criticalEquipment.map(e => {
            const utilPercent = (e.utilization * 100).toFixed(1);
            const barColor = e.isBottleneck ? 'var(--accent-red)' : 'var(--accent-orange)';
            return `
                <div style="padding: 0.5rem; margin-bottom: 0.5rem; background: var(--bg-secondary); border-radius: 4px; ${e.isBottleneck ? 'border: 1px solid var(--accent-red);' : ''}">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: 500;">${e.name}</span>
                        <span style="font-size: 0.75rem; color: var(--text-secondary);">数量: ${e.capacity}</span>
                    </div>
                    <div style="margin-top: 0.25rem; height: 6px; background: var(--bg-card); border-radius: 3px; overflow: hidden;">
                        <div style="height: 100%; width: ${Math.min(utilPercent, 100)}%; background: ${barColor}; border-radius: 3px;"></div>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.25rem;">
                        <span>利用率: ${utilPercent}%</span>
                        <span>服务任务: ${e.tasksServed}次</span>
                    </div>
                    ${e.isBottleneck ? '<div style="font-size: 0.75rem; color: var(--accent-red); margin-top: 0.25rem;">⚠️ 瓶颈设备</div>' : ''}
                </div>
            `;
        }).join('');
    }
    
    // 渲染无限制设备
    if (unlimitedEquipment.length === 0) {
        unlimitedListEl.innerHTML = '<div style="color: var(--text-secondary); padding: 0.5rem;">无无限制设备使用</div>';
    } else {
        unlimitedListEl.innerHTML = unlimitedEquipment.map(e => `
            <div style="padding: 0.5rem; margin-bottom: 0.5rem; background: var(--bg-secondary); border-radius: 4px;">
                <div style="font-weight: 500;">${e.name}</div>
                <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.25rem;">
                    <span>使用时间: ${(e.workTime / 60).toFixed(1)}小时</span>
                    <span>服务任务: ${e.tasksServed}次</span>
                </div>
            </div>
        `).join('');
    }
    
    loadingEl.style.display = 'none';
    contentEl.style.display = 'block';
}

// ============ 工位统计分析功能 ============
function analyzeStationStatistics(result) {
    const loadingEl = document.getElementById('stationAnalysisLoading');
    const contentEl = document.getElementById('stationAnalysisContent');
    
    loadingEl.style.display = 'block';
    loadingEl.textContent = '正在分析工位数据...';
    contentEl.style.display = 'none';
    
    try {
        // 构建节点到工位的映射
        const nodeStationMap = {};
        state.nodes.forEach(n => {
            nodeStationMap[n.stepId] = n.station;
        });
        
        // 按工位统计
        const stationStats = {};
        state.stations.forEach(st => {
            stationStats[st.id] = {
                id: st.id,
                name: st.name,
                color: st.color,
                nodeCount: 0,
                totalDuration: 0,
                totalWaitTime: 0,
                executionCount: 0,
                reworkCount: 0
            };
        });
        
        // 统计节点数量
        state.nodes.forEach(node => {
            const stId = node.station;
            if (stationStats[stId]) {
                stationStats[stId].nodeCount++;
            }
        });
        
        // 从gantt_events统计执行时间
        (result.gantt_events || []).forEach(event => {
            const stId = nodeStationMap[event.step_id];
            if (!stId || !stationStats[stId]) return;
            
            const duration = event.end_time - event.start_time;
            
            if (event.event_type === 'NORMAL') {
                stationStats[stId].totalDuration += duration;
                stationStats[stId].executionCount++;
            } else if (event.event_type === 'WAITING') {
                stationStats[stId].totalWaitTime += duration;
            } else if (event.event_type === 'REWORK') {
                stationStats[stId].reworkCount++;
                stationStats[stId].totalDuration += duration;
            }
        });
        
        // 转换为数组并排序
        const stationList = Object.values(stationStats)
            .filter(s => s.nodeCount > 0)
            .sort((a, b) => b.totalDuration - a.totalDuration);
        
        // 渲染工位汇总
        const summaryEl = document.getElementById('stationSummaryList');
        summaryEl.innerHTML = stationList.map(s => `
            <div style="padding: 0.75rem; background: ${hexToRgba(s.color, 0.1)}; border-left: 3px solid ${s.color}; border-radius: 4px;">
                <div style="font-weight: 600; color: ${s.color}; margin-bottom: 0.25rem;">${s.name}</div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.25rem; font-size: 0.75rem; color: var(--text-secondary);">
                    <span>节点数: ${s.nodeCount}</span>
                    <span>执行次数: ${s.executionCount}</span>
                    <span>总耗时: ${(s.totalDuration / 60).toFixed(1)}h</span>
                    <span>等待时间: ${(s.totalWaitTime / 60).toFixed(1)}h</span>
                </div>
            </div>
        `).join('');
        
        // 工位瓶颈排名（按等待时间+返工次数）
        const bottleneckRanking = stationList
            .map(s => ({
                ...s,
                bottleneckScore: s.totalWaitTime + s.reworkCount * 30 // 返工权重30分钟
            }))
            .filter(s => s.bottleneckScore > 0)
            .sort((a, b) => b.bottleneckScore - a.bottleneckScore)
            .slice(0, 5);
        
        const bottleneckEl = document.getElementById('stationBottleneckList');
        if (bottleneckRanking.length === 0) {
            bottleneckEl.innerHTML = '<div style="color: var(--accent-green); padding: 0.5rem;">✅ 各工位运行良好，无明显瓶颈</div>';
        } else {
            bottleneckEl.innerHTML = bottleneckRanking.map((s, idx) => `
                <div style="display: flex; align-items: center; padding: 0.5rem; margin-bottom: 0.5rem; background: ${idx === 0 ? 'rgba(239,68,68,0.1)' : 'var(--bg-secondary)'}; border-radius: 4px;">
                    <span style="width: 24px; font-weight: 600; color: ${idx === 0 ? 'var(--accent-red)' : 'var(--text-secondary)'};">#${idx + 1}</span>
                    <span style="flex: 1; font-weight: 500;">${s.name}</span>
                    <span style="font-size: 0.75rem; color: var(--text-secondary);">
                        等待${(s.totalWaitTime / 60).toFixed(1)}h | 返工${s.reworkCount}次
                    </span>
                </div>
            `).join('');
        }
        
        // 工位流转分析
        analyzeStationFlow(result, nodeStationMap, stationStats);
        
        loadingEl.style.display = 'none';
        contentEl.style.display = 'block';
    } catch (error) {
        console.error('工位分析失败:', error);
        loadingEl.textContent = '工位分析失败: ' + error.message;
    }
}

// 工位流转分析
function analyzeStationFlow(result, nodeStationMap, stationStats) {
    // 构建节点依赖关系
    const flowMatrix = {}; // flowMatrix[fromStation][toStation] = count
    const flowPaths = [];
    
    state.nodes.forEach(node => {
        const toStation = node.station;
        if (!toStation) return;
        
        const predecessors = node.predecessors ? node.predecessors.split(';').map(p => p.trim()).filter(p => p) : [];
        predecessors.forEach(predId => {
            const fromStation = nodeStationMap[predId];
            if (fromStation && fromStation !== toStation) {
                // 跨工位流转
                if (!flowMatrix[fromStation]) flowMatrix[fromStation] = {};
                if (!flowMatrix[fromStation][toStation]) flowMatrix[fromStation][toStation] = 0;
                flowMatrix[fromStation][toStation]++;
                
                flowPaths.push({
                    from: fromStation,
                    to: toStation,
                    fromName: stationStats[fromStation]?.name || fromStation,
                    toName: stationStats[toStation]?.name || toStation
                });
            }
        });
    });
    
    // 统计TOP流转路径
    const pathCounts = {};
    flowPaths.forEach(p => {
        const key = `${p.from}->${p.to}`;
        if (!pathCounts[key]) {
            pathCounts[key] = { ...p, count: 0 };
        }
        pathCounts[key].count++;
    });
    
    const topPaths = Object.values(pathCounts)
        .sort((a, b) => b.count - a.count)
        .slice(0, 8);
    
    // 渲染TOP路径
    const pathsEl = document.getElementById('stationFlowTopPaths');
    if (topPaths.length === 0) {
        pathsEl.innerHTML = '<div style="color: var(--text-secondary); padding: 0.5rem;">无跨工位流转</div>';
    } else {
        pathsEl.innerHTML = topPaths.map(p => `
            <div style="display: flex; align-items: center; padding: 0.5rem; margin-bottom: 0.25rem; background: var(--bg-secondary); border-radius: 4px; font-size: 0.875rem;">
                <span style="flex: 1;">${p.fromName}</span>
                <span style="color: var(--accent-cyan); margin: 0 0.5rem;">→</span>
                <span style="flex: 1;">${p.toName}</span>
                <span style="background: var(--accent-purple); color: white; padding: 0.125rem 0.5rem; border-radius: 10px; font-size: 0.75rem;">${p.count}</span>
            </div>
        `).join('');
    }
    
    // 渲染流转矩阵
    const matrixEl = document.getElementById('stationFlowMatrix');
    const activeStations = Object.keys(flowMatrix).concat(
        ...Object.values(flowMatrix).map(m => Object.keys(m))
    ).filter((v, i, a) => a.indexOf(v) === i);
    
    if (activeStations.length === 0) {
        matrixEl.innerHTML = '<div style="color: var(--text-secondary); padding: 0.5rem;">无跨工位流转数据</div>';
    } else {
        let tableHtml = '<table style="width: 100%; border-collapse: collapse; font-size: 0.75rem;">';
        tableHtml += '<tr><th style="padding: 0.25rem; border: 1px solid var(--border-color);"></th>';
        activeStations.forEach(st => {
            const name = stationStats[st]?.name?.substring(0, 4) || st;
            tableHtml += `<th style="padding: 0.25rem; border: 1px solid var(--border-color); writing-mode: vertical-lr;">${name}</th>`;
        });
        tableHtml += '</tr>';
        
        activeStations.forEach(fromSt => {
            const fromName = stationStats[fromSt]?.name?.substring(0, 4) || fromSt;
            tableHtml += `<tr><td style="padding: 0.25rem; border: 1px solid var(--border-color); font-weight: 500;">${fromName}</td>`;
            activeStations.forEach(toSt => {
                const count = flowMatrix[fromSt]?.[toSt] || 0;
                const bgColor = count > 0 ? `rgba(139, 92, 246, ${Math.min(count / 5, 1) * 0.5})` : 'transparent';
                tableHtml += `<td style="padding: 0.25rem; border: 1px solid var(--border-color); text-align: center; background: ${bgColor};">${count || '-'}</td>`;
            });
            tableHtml += '</tr>';
        });
        tableHtml += '</table>';
        matrixEl.innerHTML = tableHtml;
    }
}
