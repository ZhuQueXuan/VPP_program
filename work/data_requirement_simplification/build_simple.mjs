import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

import path from "node:path";
import { fileURLToPath } from "node:url";

const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

const rows = [
  ["P1-01","资源基础信息","资源编号、资源类型、所属运营单位和虚拟电厂、运行状态、控制方式、是否可远程控制、调节方向、接入节点、所在区域等。","静态数据；有变化时更新","光伏、储能、充电桩（站）等资源","2026年8月中旬"],
  ["P1-02","资源额定参数和能力范围","额定功率/容量、最小最大功率、可调方向、爬坡速度、响应时间、持续时间、恢复时间和安全范围；按资源类型补充关键参数。","静态数据；参数变化时更新","资源级","2026年8月中旬"],
  ["P1-03","资源运行功率","资源编号、时间、实际功率、基线功率（如有）、调节量（如有）、运行状态、是否可用、采样间隔和数据质量。","保留原始频率；至少12个月","资源级、聚合单元级","2026年8月中旬"],
  ["P1-04","资源运行状态","光伏的限发/逆变器状态，储能的荷电状态和充放电状态，充电站的在线车辆数、离站时间、可调车辆数和授权状态等。","与运行功率可按时间对应；至少12个月","资源级或站级","2026年8月中旬"],
  ["P1-05","调节任务和控制指令","任务编号、市场或场景、对象、指令和计划时间、调节方向、目标功率/电量、持续时间、允许偏差、提前通知和变更记录。","按事件提供","现货、调频、爬坡、需求响应等场景","2026年8月中旬"],
  ["P1-06","实际响应和执行结果","任务编号、资源编号、目标和实际功率、基线、实际调节量、响应时间、偏差、持续/恢复情况、成功失败及原因。","按事件及曲线提供","资源级、资源组级、虚拟电厂级","2026年8月中旬"],
  ["P1-07","用户授权和参与情况","邀约时间、是否接受、拒绝/退出原因、申报和授权容量、可接受时长、授权有效期和参与渠道；仅需脱敏编号。","按事件提供","充电设施、可调负荷、用户侧储能等","2026年8月中旬"],
  ["P1-08","市场信号和激励考核","市场类型、区域/节点、时间、价格或补偿、调节方向、考核阈值、偏差处罚、调用频次、通知要求和规则版本。","按市场原始频率；至少12个月","山东市场及示范区域","2026年8月中旬"],
  ["P1-09","基线、预测和可用能力申报","基线功率、日前/日内预测、预测版本、预测/实际可调容量、申报容量、可用概率和计算方法。","与市场和运行数据同频；至少12个月","资源级、资源组级、虚拟电厂级","2026年8月中旬"],
  ["P1-10","环境和气象","时间、区域、温湿度、太阳辐照度、云量、风速、降雨、极端天气、实测/预测及资源区域对应关系。","15分钟至1小时；至少12个月","环境敏感资源所在区域","2026年8月中旬"],
  ["P2-01","结算、收益和成本","市场/容量/里程收益、补偿、偏差考核、违约费用、成本、净收益和结算状态。","按事件、日或月；至少12个月","实际参与市场的资源","2026年8月底"],
  ["P2-02","历史履约和可靠性","可用率、接受率、调用和成功次数、响应时延、偏差、持续达标率、退出率和已有履约等级。","按事件及日/月；至少12个月","资源级、资源组级","2026年8月底"],
  ["P2-03","通信、控制和设备可用情况","在线/离线、通信时延、指令接收/执行、告警、保护闭锁、远程/本地、检修、故障和恢复。","按事件或秒/分钟提供","可远程监控/控制的资源","2026年8月底"],
  ["P2-04","业务计划和刚性约束","车辆到离站与最低保障电量、生产班次和可调整时段、楼宇舒适度、储能后续计划等。","计划变化时更新","存在生产、出行或舒适度约束的资源","2026年8月底"],
  ["P2-05","市场品种和规则","市场名称、适用区域、生效日期、申报和报价要求、响应/持续/精度要求、结算和考核规则、准入条件。","规则变化时更新","课题一涉及的市场","2026年8月底"],
  ["P2-06","资源编组和协同控制","资源组和成员、权重、分配指令/功率、聚合目标、约束冲突、重新分配和执行结果。","编组变化或任务发生时","源-荷-储组合、站群、聚合单元","2026年8月底"],
  ["P2-07","绿色价值和环境属性","能源类型、绿电/绿证、交易量和价格、碳排放因子、减排量、绿色偏好等。","按交易、日或月提供","新能源、储能及绿电场景资源","2026年8月底"],
  ["P2-08","用户偏好和调研标签","价格敏感度、风险偏好、绿色偏好、可接受补偿/调用、用能偏好和样本来源；仅需脱敏或分档信息。","静态或按调研批次更新","存在用户决策的资源","2026年8月底或后续补充"],
  ["P3-01","配网接入和运行约束","资源与接入节点对应；如可提供，再补充线路/变压器、容量、电压、潮流和拓扑版本。","变化时更新","示范虚拟电厂接入范围","2026年9月底或协调提供"],
  ["P3-02","检修、故障和异常事件","资源/设备、事件类型、起止时间、影响容量、原因、处置结果、恢复时间和是否影响调节任务。","按事件；至少12个月","资源设备和通信设备","2026年9月底"],
  ["P3-03","日历、政策和特殊事件","工作日/节假日、季节、重大活动、保供、需求响应通知、政策或规则调整、极端天气和影响区域。","按日或事件提供","山东省及示范地市","2026年9月底"]
];
const wb = Workbook.create();
const s = wb.worksheets.add("数据需求清单");
s.showGridLines = false;
s.mergeCells("A1:F1"); s.getRange("A1:F1").values = [["课题一数据需求（简化版）"]]; s.getRange("A1:F1").format = { fill: "#1F4E78", font: { bold: true, color: "#FFFFFF" }, horizontalAlignment: "center" };
s.mergeCells("A2:F2"); s.getRange("A2:F2").values = [["请按部门职责提供数据。字段均用中文表述；系统内如为英文，可保留原字段并附中文对照。用户信息仅需脱敏编号。"]]; s.getRange("A2:F2").format = { fill: "#D9EAF7", wrapText: true };
s.getRange("A4:F4").values = [["编号","数据名称","需要提供什么（通俗说明）","更新/时间范围","适用范围","建议提供时间"]];
s.getRange("A4:F4").format = { fill: "#1F4E78", font: { bold: true, color: "#FFFFFF" }, wrapText: true, horizontalAlignment: "center", borders: { preset: "all", style: "thin", color: "#B7C9D6" } };
s.getRange("A5:F25").values = rows;
s.getRange("A5:F25").format = { borders: { preset: "all", style: "thin", color: "#B7C9D6" }, wrapText: true, verticalAlignment: "center" };
s.getRange("A5:F25").format.rowHeight = 46;
[12,22,55,27,30,20].forEach((w,i)=>s.getRange(`${String.fromCharCode(65+i)}1:${String.fromCharCode(65+i)}25`).format.columnWidth=w);
s.freezePanes.freezeRows(4);
const deptBlocks = [
  ["调度部门填报模板", ["P1-03","P1-05","P1-06","P1-08","P1-09","P1-10","P2-03","P2-06","P3-01","P3-02"], "调度自动化/负荷管理/运行监视系统"],
  ["交易部门填报模板", ["P1-05","P1-08","P1-09","P2-01","P2-05","P2-07","P3-03"], "电力交易/结算/市场规则管理系统"],
  ["运检部门填报模板", ["P1-02","P2-03","P3-01","P3-02"], "设备运检/通信监控/故障管理系统"],
  ["营销部门填报模板", ["P1-01","P1-02","P1-04","P1-07","P2-02","P2-04","P2-08"], "负荷管理/客户服务/虚拟电厂运营系统"]
];
let startRow = 28;
for (const [dept, ids, suggestedSource] of deptBlocks) {
  const endRow = startRow + ids.length + 1;
  s.mergeCells(`A${startRow}:F${startRow}`); s.getRange(`A${startRow}:F${startRow}`).values = [[dept]]; s.getRange(`A${startRow}:F${startRow}`).format = { fill: "#1F4E78", font: { bold: true, color: "#FFFFFF" }, horizontalAlignment: "center" };
  s.getRange(`A${startRow + 1}:F${startRow + 1}`).values = [["数据编号","数据名称","建议查询的系统/资料","是否可提供（填写）","可提供的时间范围或频次（填写）","备注（缺失项、原因、联系人等）"]];
  s.getRange(`A${startRow + 1}:F${startRow + 1}`).format = { fill: "#D9EAF7", font: { bold: true }, wrapText: true, horizontalAlignment: "center", borders: { preset: "all", style: "thin", color: "#B7C9D6" } };
  const deptRows = ids.map(id => { const item = rows.find(row => row[0] === id); return [id, item ? item[1] : "", suggestedSource, "", "", ""]; });
  s.getRange(`A${startRow + 2}:F${endRow}`).values = deptRows;
  s.getRange(`A${startRow + 2}:F${endRow}`).format = { borders: { preset: "all", style: "thin", color: "#B7C9D6" }, wrapText: true, verticalAlignment: "center" };
  s.getRange(`A${startRow + 2}:F${endRow}`).format.rowHeight = 30;
  startRow = endRow + 3;
}
const out = await SpreadsheetFile.exportXlsx(wb); await out.save(path.join(PROJECT_ROOT, "02_数据需求与口径", "数据需求_课题一_简化版.xlsx"));
console.log("SAVED");



