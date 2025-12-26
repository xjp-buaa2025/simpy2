/**
 * 示例数据模块 - 压气机装配流程
 */

const COMPLEX_PROCESS_NODES = [
    // ========== 阶段0: 准备与检测 - 预处理工区 ==========
    { step_id: 'P001', task_name: '扫码收货', op_type: 'D', predecessors: '', std_duration: 10, time_variance: 2, work_load_score: 3, rework_prob: 0, required_workers: 1, required_tools: '扫码枪', station: 'ST01' },
    { step_id: 'P002', task_name: '目视检测转子', op_type: 'M', predecessors: 'P001', std_duration: 25, time_variance: 5, work_load_score: 4, rework_prob: 0.03, required_workers: 1, required_tools: '检测台', station: 'ST02' },
    { step_id: 'P003', task_name: '目视检测叶片', op_type: 'M', predecessors: 'P001', std_duration: 30, time_variance: 5, work_load_score: 4, rework_prob: 0.04, required_workers: 1, required_tools: '检测台', station: 'ST02' },
    { step_id: 'P004', task_name: '目视检测主要零件', op_type: 'M', predecessors: 'P001', std_duration: 35, time_variance: 6, work_load_score: 5, rework_prob: 0.03, required_workers: 2, required_tools: '检测台', station: 'ST02' },
    
    // ========== 阶段1: 转子叶片安装 - 压气机模块装配区 ==========
    { step_id: 'S101', task_name: '固定1级转子盘', op_type: 'T', predecessors: 'P002', std_duration: 20, time_variance: 3, work_load_score: 6, rework_prob: 0, required_workers: 2, required_tools: '叶片安装夹具', station: 'ST03' },
    { step_id: 'S102', task_name: '安装1级叶片', op_type: 'A', predecessors: 'S101;P003', std_duration: 45, time_variance: 8, work_load_score: 7, rework_prob: 0, required_workers: 2, required_tools: '机械式压入工具', station: 'ST03' },
    { step_id: 'S103', task_name: '固定2级转子盘', op_type: 'T', predecessors: 'S102', std_duration: 20, time_variance: 3, work_load_score: 6, rework_prob: 0, required_workers: 2, required_tools: '叶片安装夹具', station: 'ST03' },
    { step_id: 'S104', task_name: '安装2级叶片', op_type: 'A', predecessors: 'S103', std_duration: 45, time_variance: 8, work_load_score: 7, rework_prob: 0, required_workers: 2, required_tools: '机械式压入工具', station: 'ST03' },
    { step_id: 'S105', task_name: '固定3级转子盘', op_type: 'T', predecessors: 'S104', std_duration: 20, time_variance: 3, work_load_score: 6, rework_prob: 0, required_workers: 2, required_tools: '叶片安装夹具', station: 'ST03' },
    { step_id: 'S106', task_name: '安装3级叶片', op_type: 'A', predecessors: 'S105', std_duration: 45, time_variance: 8, work_load_score: 7, rework_prob: 0, required_workers: 2, required_tools: '机械式压入工具', station: 'ST03' },
    
    // ========== 阶段2: 第一级转子组件装配与平衡 - 压气机模块装配区 ==========
    { step_id: 'S201', task_name: '安装挡圈', op_type: 'A', predecessors: 'S106', std_duration: 15, time_variance: 3, work_load_score: 5, rework_prob: 0, required_workers: 1, required_tools: '', station: 'ST03' },
    { step_id: 'S202', task_name: '铆接固定', op_type: 'A', predecessors: 'S201', std_duration: 25, time_variance: 4, work_load_score: 6, rework_prob: 0, required_workers: 2, required_tools: '铆钉枪', station: 'ST03' },
    { step_id: 'S203', task_name: '安装联轴器', op_type: 'A', predecessors: 'S202', std_duration: 20, time_variance: 4, work_load_score: 5, rework_prob: 0, required_workers: 1, required_tools: '', station: 'ST03' },
    { step_id: 'S204', task_name: '安装销钉螺母', op_type: 'A', predecessors: 'S203', std_duration: 18, time_variance: 3, work_load_score: 5, rework_prob: 0, required_workers: 1, required_tools: '手动工具', station: 'ST03' },
    { step_id: 'S205', task_name: '加热密封件', op_type: 'T', predecessors: 'S204', std_duration: 30, time_variance: 5, work_load_score: 4, rework_prob: 0, required_workers: 1, required_tools: '感应加热器', station: 'ST03' },
    { step_id: 'S206', task_name: '安装密封件', op_type: 'A', predecessors: 'S205', std_duration: 22, time_variance: 4, work_load_score: 6, rework_prob: 0, required_workers: 2, required_tools: '专用套筒', station: 'ST03' },
    { step_id: 'S207', task_name: '安装1号轴承', op_type: 'A', predecessors: 'S206', std_duration: 28, time_variance: 5, work_load_score: 6, rework_prob: 0, required_workers: 2, required_tools: '', station: 'ST03' },
    { step_id: 'S208', task_name: '安装垫片与螺母', op_type: 'A', predecessors: 'S207', std_duration: 15, time_variance: 3, work_load_score: 4, rework_prob: 0, required_workers: 1, required_tools: '专用套筒', station: 'ST03' },
    { step_id: 'S209', task_name: '预紧螺母', op_type: 'T', predecessors: 'S208', std_duration: 20, time_variance: 4, work_load_score: 7, rework_prob: 0, required_workers: 1, required_tools: '液压拉伸器', station: 'ST03' },
    { step_id: 'S210', task_name: '最终拧紧', op_type: 'T', predecessors: 'S209', std_duration: 18, time_variance: 3, work_load_score: 6, rework_prob: 0, required_workers: 1, required_tools: '高精度扭矩扳手', station: 'ST03' },
    { step_id: 'S211', task_name: '锁紧垫片', op_type: 'T', predecessors: 'S210', std_duration: 12, time_variance: 2, work_load_score: 5, rework_prob: 0, required_workers: 1, required_tools: '专用套筒', station: 'ST03' },
    { step_id: 'S212', task_name: '动平衡准备', op_type: 'T', predecessors: 'S211', std_duration: 25, time_variance: 4, work_load_score: 5, rework_prob: 0, required_workers: 2, required_tools: '动平衡机', station: 'ST03' },
    { step_id: 'S213', task_name: '执行平衡测试', op_type: 'M', predecessors: 'S212', std_duration: 45, time_variance: 8, work_load_score: 5, rework_prob: 0.08, required_workers: 2, required_tools: '动平衡机', station: 'ST03' },
    { step_id: 'S214', task_name: '添加配重', op_type: 'A', predecessors: 'S213', std_duration: 20, time_variance: 4, work_load_score: 5, rework_prob: 0, required_workers: 1, required_tools: '手动工具', station: 'ST03' },
    { step_id: 'S215', task_name: '复测平衡', op_type: 'M', predecessors: 'S214', std_duration: 35, time_variance: 6, work_load_score: 5, rework_prob: 0.05, required_workers: 2, required_tools: '动平衡机', station: 'ST03' },
    { step_id: 'S216', task_name: '拆卸组件', op_type: 'T', predecessors: 'S215', std_duration: 15, time_variance: 3, work_load_score: 5, rework_prob: 0, required_workers: 1, required_tools: '', station: 'ST03' },
    
    // ========== 阶段3: 核心机同轴装配 - 总装集成工区 ==========
    { step_id: 'S301', task_name: '固定涡轮轴', op_type: 'A', predecessors: 'S216;P004', std_duration: 30, time_variance: 5, work_load_score: 7, rework_prob: 0, required_workers: 2, required_tools: '直立装配工装', station: 'ST11' },
    { step_id: 'S302', task_name: '安装导向套', op_type: 'A', predecessors: 'S301', std_duration: 22, time_variance: 4, work_load_score: 5, rework_prob: 0, required_workers: 1, required_tools: '', station: 'ST11' },
    { step_id: 'S303', task_name: '安装叶轮', op_type: 'A', predecessors: 'S302', std_duration: 28, time_variance: 5, work_load_score: 6, rework_prob: 0, required_workers: 2, required_tools: '', station: 'ST11' },
    { step_id: 'S304', task_name: '安装调整盘', op_type: 'A', predecessors: 'S303', std_duration: 20, time_variance: 4, work_load_score: 5, rework_prob: 0, required_workers: 1, required_tools: '', station: 'ST11' },
    { step_id: 'S305', task_name: '安装导流机匣', op_type: 'A', predecessors: 'S304', std_duration: 25, time_variance: 4, work_load_score: 6, rework_prob: 0, required_workers: 2, required_tools: '', station: 'ST11' },
    { step_id: 'S306', task_name: '安装三级定子', op_type: 'A', predecessors: 'S305', std_duration: 30, time_variance: 5, work_load_score: 6, rework_prob: 0, required_workers: 2, required_tools: '液压压装器', station: 'ST11' },
    { step_id: 'S307', task_name: '测量叶尖间隙', op_type: 'M', predecessors: 'S306', std_duration: 25, time_variance: 4, work_load_score: 4, rework_prob: 0.06, required_workers: 1, required_tools: '塞尺', station: 'ST11' },
    { step_id: 'S308', task_name: '安装连接螺栓', op_type: 'A', predecessors: 'S307', std_duration: 20, time_variance: 3, work_load_score: 5, rework_prob: 0, required_workers: 1, required_tools: '手动工具', station: 'ST11' },
    { step_id: 'S309', task_name: '拧紧螺栓', op_type: 'T', predecessors: 'S308', std_duration: 18, time_variance: 3, work_load_score: 6, rework_prob: 0, required_workers: 1, required_tools: '智能扭矩扳手', station: 'ST11' },
    { step_id: 'S310', task_name: '安装三级转子', op_type: 'A', predecessors: 'S309', std_duration: 35, time_variance: 6, work_load_score: 7, rework_prob: 0, required_workers: 2, required_tools: '', station: 'ST11' },
    { step_id: 'S311', task_name: '测量轴向间隙', op_type: 'M', predecessors: 'S310', std_duration: 22, time_variance: 4, work_load_score: 4, rework_prob: 0.05, required_workers: 1, required_tools: '塞尺', station: 'ST11' },
    { step_id: 'S312', task_name: '测量叶尖间隙2', op_type: 'M', predecessors: 'S311', std_duration: 22, time_variance: 4, work_load_score: 4, rework_prob: 0.05, required_workers: 1, required_tools: '塞尺', station: 'ST11' },
    { step_id: 'S313', task_name: '安装二级定子', op_type: 'A', predecessors: 'S312', std_duration: 28, time_variance: 5, work_load_score: 6, rework_prob: 0, required_workers: 2, required_tools: '', station: 'ST11' },
    { step_id: 'S314', task_name: '安装二级转子', op_type: 'A', predecessors: 'S313', std_duration: 32, time_variance: 5, work_load_score: 7, rework_prob: 0, required_workers: 2, required_tools: '', station: 'ST11' },
    { step_id: 'S315', task_name: '测量叶尖间隙3', op_type: 'M', predecessors: 'S314', std_duration: 22, time_variance: 4, work_load_score: 4, rework_prob: 0.05, required_workers: 1, required_tools: '塞尺', station: 'ST11' },
    { step_id: 'S316', task_name: '测量轴向间隙2', op_type: 'M', predecessors: 'S315', std_duration: 20, time_variance: 4, work_load_score: 4, rework_prob: 0.05, required_workers: 1, required_tools: '塞尺', station: 'ST11' },
    { step_id: 'S317', task_name: '安装一级定子', op_type: 'A', predecessors: 'S316', std_duration: 25, time_variance: 4, work_load_score: 6, rework_prob: 0, required_workers: 2, required_tools: '', station: 'ST11' },
    { step_id: 'S318', task_name: '安装连接螺母', op_type: 'A', predecessors: 'S317', std_duration: 18, time_variance: 3, work_load_score: 5, rework_prob: 0, required_workers: 1, required_tools: '手动工具', station: 'ST11' },
    { step_id: 'S319', task_name: '拧紧螺母', op_type: 'T', predecessors: 'S318', std_duration: 16, time_variance: 3, work_load_score: 6, rework_prob: 0, required_workers: 1, required_tools: '智能扭矩扳手', station: 'ST11' },
    { step_id: 'S320', task_name: '安装一级转子组件', op_type: 'A', predecessors: 'S319', std_duration: 40, time_variance: 7, work_load_score: 7, rework_prob: 0, required_workers: 2, required_tools: '', station: 'ST11' },
    { step_id: 'S321', task_name: '测量叶尖间隙4', op_type: 'M', predecessors: 'S320', std_duration: 22, time_variance: 4, work_load_score: 4, rework_prob: 0.05, required_workers: 1, required_tools: '塞尺', station: 'ST11' },
    { step_id: 'S322', task_name: '测量轴向间隙3', op_type: 'M', predecessors: 'S321', std_duration: 20, time_variance: 4, work_load_score: 4, rework_prob: 0.05, required_workers: 1, required_tools: '塞尺', station: 'ST11' },
    { step_id: 'S323', task_name: '插入连接杆', op_type: 'A', predecessors: 'S322', std_duration: 18, time_variance: 3, work_load_score: 5, rework_prob: 0, required_workers: 1, required_tools: '', station: 'ST11' },
    { step_id: 'S324', task_name: '移除导向套', op_type: 'T', predecessors: 'S323', std_duration: 12, time_variance: 2, work_load_score: 4, rework_prob: 0, required_workers: 1, required_tools: '', station: 'ST11' },
    { step_id: 'S325', task_name: '安装垫圈螺母', op_type: 'A', predecessors: 'S324', std_duration: 15, time_variance: 3, work_load_score: 5, rework_prob: 0, required_workers: 1, required_tools: '手动工具', station: 'ST11' },
    { step_id: 'S326', task_name: '预紧连接杆', op_type: 'T', predecessors: 'S325', std_duration: 20, time_variance: 4, work_load_score: 7, rework_prob: 0, required_workers: 1, required_tools: '液压拉伸器', station: 'ST11' },
    { step_id: 'S327', task_name: '最终拧紧2', op_type: 'T', predecessors: 'S326', std_duration: 18, time_variance: 3, work_load_score: 6, rework_prob: 0, required_workers: 1, required_tools: '高精度扭矩扳手', station: 'ST11' },
    
    // ========== 阶段4: 整体动平衡调试 - 整机测试工区 ==========
    { step_id: 'S401', task_name: '测量总跳动', op_type: 'M', predecessors: 'S327', std_duration: 35, time_variance: 6, work_load_score: 5, rework_prob: 0.06, required_workers: 2, required_tools: '百分表;磁力表座', station: 'ST12' },
    { step_id: 'S402', task_name: '翻转组件', op_type: 'T', predecessors: 'S401', std_duration: 25, time_variance: 4, work_load_score: 8, rework_prob: 0, required_workers: 3, required_tools: '起重设备', station: 'ST12' },
    { step_id: 'S403', task_name: '加热密封件2', op_type: 'T', predecessors: 'S402', std_duration: 28, time_variance: 5, work_load_score: 4, rework_prob: 0, required_workers: 1, required_tools: '感应加热器', station: 'ST12' },
    { step_id: 'S404', task_name: '安装密封件2', op_type: 'A', predecessors: 'S403', std_duration: 22, time_variance: 4, work_load_score: 6, rework_prob: 0, required_workers: 2, required_tools: '专用套筒', station: 'ST12' },
    { step_id: 'S405', task_name: '安装2号轴承', op_type: 'A', predecessors: 'S404', std_duration: 30, time_variance: 5, work_load_score: 6, rework_prob: 0, required_workers: 2, required_tools: '', station: 'ST12' },
    { step_id: 'S406', task_name: '动平衡准备2', op_type: 'T', predecessors: 'S405', std_duration: 30, time_variance: 5, work_load_score: 6, rework_prob: 0, required_workers: 2, required_tools: '动平衡机', station: 'ST12' },
    { step_id: 'S407', task_name: '执行平衡测试2', op_type: 'M', predecessors: 'S406', std_duration: 50, time_variance: 10, work_load_score: 5, rework_prob: 0.10, required_workers: 2, required_tools: '动平衡机', station: 'ST12' },
    { step_id: 'S408', task_name: '添加配重2', op_type: 'A', predecessors: 'S407', std_duration: 25, time_variance: 5, work_load_score: 5, rework_prob: 0, required_workers: 1, required_tools: '手动工具', station: 'ST12' },
    { step_id: 'S409', task_name: '复测平衡2', op_type: 'M', predecessors: 'S408', std_duration: 40, time_variance: 8, work_load_score: 5, rework_prob: 0.06, required_workers: 2, required_tools: '动平衡机', station: 'ST12' },
    { step_id: 'S410', task_name: '拆卸总成', op_type: 'T', predecessors: 'S409', std_duration: 20, time_variance: 4, work_load_score: 6, rework_prob: 0, required_workers: 2, required_tools: '', station: 'ST12' },
    
    // ========== 阶段5: 包装发运 - 包装发运区 ==========
    { step_id: 'S411', task_name: '清洁包装', op_type: 'T', predecessors: 'S410', std_duration: 30, time_variance: 5, work_load_score: 4, rework_prob: 0, required_workers: 2, required_tools: '', station: 'ST13' },
    { step_id: 'S412', task_name: '扫码发货', op_type: 'D', predecessors: 'S411', std_duration: 10, time_variance: 2, work_load_score: 3, rework_prob: 0, required_workers: 1, required_tools: '扫码枪;AGV', station: 'ST13' }
];
