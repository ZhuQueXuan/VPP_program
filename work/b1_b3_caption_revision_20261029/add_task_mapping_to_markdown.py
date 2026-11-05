from pathlib import Path
import hashlib
import json

base = Path(__file__).resolve().parent
source_receipt = json.loads((base / 'task_mapping_addition_source.json').read_text(encoding='utf-8'))
target = Path(source_receipt['target'])
backup = Path(source_receipt['backup'])
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(target) == source_receipt['before_sha256'], 'Latest report changed; rebase needed'
assert sha(backup) == source_receipt['before_sha256']
text = backup.read_text(encoding='utf-8')
heading = '## 1 研究目标与阶段结论\n\n'
assert text.count(heading) == 1
new_heading = heading + '### 1.1 研究目标与现阶段结论\n\n'
old = '任务对应：B1对应行为影响因素和关键时序特征，B2对应融合行为经济及绿色因素的单体能力分析，B3对应多智能体源荷储交互与组合潜力。以下结果均按各自模拟机制、数据划分和任务口径解释。'
assert text.count(old) == 1
addition = '''### 1.2 三个算法与课题一任务书的对应关系

本报告的B1、B2、B3均服务于课题一“虚拟电厂多元异质资源调节行为分析与智能分类方法研究”。任务书中的课题二、课题三、课题四不在本报告的算法研究范围内。B1—B4是本研究的算法编号，任务书第（1）—（3）项是课题一的研究内容编号，两者不按数字逐项对应。[1]

| 算法 | 对应的课题一任务 | 本报告具体开展的工作 |
| --- | --- | --- |
| B1 行为影响因素与全过程特征分析 | 第（1）项：差异化市场环境下的多元资源行为影响因素分析与关键调节时序特征提取。 | 从参考与观测功率曲线提取累计响应时长、最长连续时长和电量特征；在声明的结构假设下，区分补偿影响与用户事前差异；补充比较非线性、阈值区间、图筛选及历史表示。具体方法和结果见2.1—2.3节。 |
| B2 单体容量与响应评估 | 第（2）项中的单体层面：融合行为经济学、绿色价值等因素，分析资源可调容量与响应能力。 | 针对指定充电桩任务，依次计算物理可行性、许可、接受概率和接受后的执行分布；比较风险、参考点及绿色因素候选，输出条件响应轨迹、预计交付和任务满足概率。具体方法和结果见3.1—3.3节。 |
| B3 多资源组合协同与连续调用 | 同属第（2）项，侧重多智能体协同，以及源、荷、储交互和复杂场景下的组合调节潜力。 | 在共享接入、回补及恢复约束下求组合容量与资源功率计划；在受限共同域中消费B2预测结果，并在连续任务中按实际功率传递欠账和储能电量，记录准入、服务、恢复及失效结果。具体方法和结果见4.1—4.3节。 |

从任务书的分阶段安排看，B1主要对应2026年下半年的驱动因素解耦、非线性与关键响应阈值识别、全周期调节特征提取；B2主要对应2027年上半年的价格敏感性、用能偏好与绿色价值因子、前景理论与离散选择、主观意愿及时序响应能力建模；B3直接对应2027年下半年的多智能体源荷储交互分析与组合潜力评估。这里说明研究内容的对应关系，不表示相应阶段已全部验收。[1]

课题一第（3）项要求研究“面向多元市场调节需求的虚拟电厂资源多能力维度自监督智能分级分类方法”。现有算法规划将这一部分及市场适配、匹配校核工作安排给B4；本报告只汇报B1—B3，未将B4列为已完成成果。前三项算法产生的过程特征、单体能力和组合能力结果，可为后续分级分类提供部分输入。

当前已完成的工作主要是指定充电桩任务族和假设源荷储小站中的模拟原型及有限验证。多元资源与差异化市场的覆盖、正式时序表征与深度表示、真实用户偏好和绿色价值、现场响应及组合可靠性仍需补充证据。因此，B1—B3已对课题一前两项任务形成具体方法和阶段结果，尚不能据此认定前两项任务全部完成，也不能代替课题一整体验收。任务书提出的“模型精度不小于90%”仍需按明确的评价对象、真值和误差标准单独验证；模拟中已接任务的达标比例不等于该精度指标。[1]

以上对应关系依据103任务书PDF文件第5、6、12、13页，分别涉及课题一研究内容、预期目标和考核指标、课题一分阶段计划。以下实验结果仍按各自模拟机制、数据划分和任务口径解释。'''
updated = text.replace(heading, new_heading, 1).replace(old, addition, 1)
assert updated.replace(new_heading, heading, 1).replace(addition, old, 1) == text
assert updated.split('## 2 B1算法', 1)[1] == text.split('## 2 B1算法', 1)[1]
assert updated.count('$$') == text.count('$$')
assert updated.count('![') == text.count('![') == 6
staged = base / 'task_mapping_addition_staged.md'
staged.write_text(updated, encoding='utf-8')
before = source_receipt['folder_before']
inventory = lambda: {p.name: sha(p) for p in target.parent.iterdir() if p.is_file() and not p.name.startswith('~$')}
assert inventory() == before, 'Folder changed before write'
target.write_bytes(staged.read_bytes())
after = inventory()
assert set(after) == set(before)
changed = [name for name in before if before[name] != after[name]]
assert changed == [target.name]
result = {**source_receipt, 'status': 'complete', 'after_sha256': sha(target),
          'changed_files': changed, 'only_section1_changed': True,
          'all_other_content_preserved': True, 'figure_and_formula_counts_preserved': True,
          'added_subsections': ['1.1 研究目标与现阶段结论', '1.2 三个算法与课题一任务书的对应关系'],
          'source_pdf_file_pages': [5, 6, 12, 13], 'new_table_rows': 3}
(base / 'task_mapping_addition_receipt.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print('complete: only report Markdown section 1 updated')
