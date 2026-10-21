import fs from 'node:fs/promises';
import path from 'node:path';
import {Workbook, SpreadsheetFile} from '@oai/artifact-tool';
const dest='C:/xjp/simpy2/data/factory_layout';
const doc=JSON.parse(await fs.readFile(path.join(dest,'default.json'),'utf8'));
const fields=['station_id','label','area','x','z','yaw','model_key','scale','show_model','label_height','animation','auto_dock','dock_x','dock_z','dock_yaw'];
const headers=['工位编号','显示名称','区域','X（米）','Z（米）','水平角度','模型编号','统一缩放','显示设备','标签高度','动画启用','自动停靠','停靠偏移X','停靠偏移Z','停靠朝向'];
const wb=Workbook.create();const sheet=wb.worksheets.add('工位布局');const models=wb.worksheets.add('可选模型');const help=wb.worksheets.add('填写说明');
sheet.getRange('A1:O80').values=[headers,...doc.stations.map(row=>fields.map(f=>typeof row[f]==='boolean'?(row[f]?'是':'否'):row[f]))];
sheet.getRange('A1:O80').format.font={name:'Microsoft YaHei',size:11};sheet.getRange('A1:O80').format.rowHeight=24;sheet.getRange('A1:O80').format.columnWidth=14;
sheet.getRange('B1:B80').format.columnWidth=30;sheet.getRange('G1:G80').format.columnWidth=28;
sheet.getRange('D2:F80').setNumberFormat('0.00');sheet.getRange('H2:H80').setNumberFormat('0.00');sheet.getRange('J2:J80').setNumberFormat('0.00');sheet.getRange('M2:O80').setNumberFormat('0.00');
sheet.getRange('A2:A80').format.fill='#EDF1F5';sheet.getRange('B2:O80').format.font.color='#145A91';sheet.freezePanes.freezeRows(1);sheet.freezePanes.freezeColumns(1);sheet.tables.add('A1:O80',true,'FactoryStations');
models.getRange(`A1:D${doc.models.length+1}`).values=[['模型编号','名称','允许工位','动画'],...doc.models.map(m=>[m.key,m.label,m.allowed_stations.length?m.allowed_stations.join('、'):'全部工位',m.key==='gantry'?'吊装':m.category.includes('压装')?'压装':m.category.includes('旋转')?'旋转':'按原工位兼容动作'])];
models.getRange(`A1:D${doc.models.length+1}`).format.columnWidth=28;models.getRange(`B1:B${doc.models.length+1}`).format.columnWidth=42;models.freezePanes.freezeRows(1);
sheet.getRange('G2:G80').dataValidation={rule:{type:'list',formula1:`'可选模型'!$A$2:$A$${doc.models.length+1}`}};
for(const col of ['I','K','L'])sheet.getRange(`${col}2:${col}80`).dataValidation={rule:{type:'list',values:['是','否']}};
sheet.getRange('H2:H80').dataValidation={rule:{type:'decimal',operator:'between',formula1:.25,formula2:3}};
const notes=[['工厂布局填写说明','版本 factory-1'],['使用顺序','在PC导出当前布局，修改工位布局表，保存后导入预览；确认后应用并同步VR。'],['工位编号','必须保留完整79行，不新增、不删除、不改编号。行顺序可以调整。'],['坐标与朝向','单位米；X/Z为工厂坐标，Y自动落地。0度朝北，即Unity +Z方向。'],['统一缩放','1保持当前工位标准尺寸；允许0.25～3，不单独拉伸某个轴。'],['模型编号','使用可选模型表；龙门架仅支持A001。不能填写FBX路径。'],['显示设备','填否时保留工位编号、状态与地面轮廓，排产仍包含该工序。'],['标签高度','设备顶部到标签的距离，单位米，允许0.1～5。'],['动画启用','只启停兼容的现有动画，不改变工序时间。'],['停靠设置','自动停靠填是时，忽略偏移。填否时，X/Z偏移为工位局部米数，随工位朝向及缩放变化；朝向为相对角度。'],['通道与陈设','厂房、货架、工具柜及物流通道固定；重叠或不可达布局不会发布。'],['暂停与回退','预览和应用后保持暂停。取消恢复原布局；恢复默认和上一版也要先预览再应用。'],['同步条件','PC、VR连接同一SimPy服务。模型资源不兼容时保留旧布局并显示诊断。'],['填写限制','数据区域不使用公式；空白行会忽略。保留表头、其他工作表及文件格式。']];
help.getRange(`A1:B${notes.length}`).values=notes;help.getRange(`A1:A${notes.length}`).format.columnWidth=22;help.getRange(`B1:B${notes.length}`).format.columnWidth=105;help.getRange(`A1:B${notes.length}`).format.rowHeight=42;help.getRange(`A1:B${notes.length}`).format.wrapText=true;
for(const s of [sheet,models,help]){s.showGridLines=false;s.getRange(s===sheet?'A1:O1':s===models?'A1:D1':'A1:B1').format.fill='#19344B';s.getRange(s===sheet?'A1:O1':s===models?'A1:D1':'A1:B1').format.font={name:'Microsoft YaHei',size:11,bold:true,color:'#FFFFFF'};}
console.log((await wb.inspect({kind:'sheet',include:'id,name',maxChars:1000})).ndjson);
await (await SpreadsheetFile.exportXlsx(wb)).save(path.join(dest,'template.xlsx'));
try{const preview=await wb.render({sheetName:'工位布局',range:'A1:G10',scale:1,format:'png'});await fs.writeFile('C:/xjp/simpy2/results/unity_validation/layout_20261015/template_preview.png',new Uint8Array(await preview.arrayBuffer()));}catch(e){console.log('Preview:',e.message);}
