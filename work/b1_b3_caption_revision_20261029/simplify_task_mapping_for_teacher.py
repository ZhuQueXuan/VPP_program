from pathlib import Path
import hashlib
import json

work = Path(__file__).resolve().parent
target = work.parents[1] / '04_汇报与调研资料' / '课题一B1至B3算法阶段研究报告_20261029.md'
sha = lambda data: hashlib.sha256(data).hexdigest()
original = target.read_bytes()
text = original.decode('utf-8')
start = text.index('从任务书的分阶段安排看，')
end = text.index('## 2 B1算法', start)
old = text[start:end]
assert '本报告只汇报B1—B3，未将B4列为已完成成果。' in old
replacement = '''B1行为影响因素与全过程特征分析算法，对应课题一第（1）项“行为影响因素分析与关键调节时序特征提取”，具体涉及驱动因素解耦、非线性特征与关键响应阈值区间及敏感性识别、全周期调节特征提取。

B2单体容量与响应评估算法，对应课题一第（2）项中的单体资源分析，具体涉及价格敏感性、用能偏好与绿色价值因子分析，风险与不确定性下的决策偏好刻画，以及主观意愿与动态响应能力建模。

B3多资源组合协同与连续调用算法，对应课题一第（2）项中的多智能体协同分析，具体涉及源荷储交互、共享约束下的组合调节潜力评估，以及连续调用中的服务与恢复协调。[1]

'''
updated = text[:start] + replacement + text[end:]
assert updated.replace(replacement, old, 1) == text
before = {p.name: sha(p.read_bytes()) for p in target.parent.iterdir() if p.is_file() and not p.name.startswith('~$')}
backup = work / 'before_teacher_task_mapping_simplification.md'
assert not backup.exists(), 'Preserve existing backup'
backup.write_bytes(original)
assert target.read_bytes() == original, 'User changed report; stop'
target.write_text(updated, encoding='utf-8', newline='')
after = {p.name: sha(p.read_bytes()) for p in target.parent.iterdir() if p.is_file() and not p.name.startswith('~$')}
assert set(before) == set(after)
changed = [name for name in before if before[name] != after[name]]
assert changed == [target.name]
receipt = {'status': 'complete', 'target': str(target), 'backup': str(backup),
           'before_sha256': sha(original), 'after_sha256': sha(target.read_bytes()),
           'only_selected_passage_changed': True, 'changed_files_in_04': changed,
           'removed': old, 'replacement': replacement}
(work / 'teacher_task_mapping_simplification_receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
print('Complete: selected passage replaced with three direct algorithm-to-task paragraphs.')
