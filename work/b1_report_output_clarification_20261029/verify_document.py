"""Read-only document checks; never imports or runs research code."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent
TARGET = ROOT / '04_汇报与调研资料' / '课题一B1至B3算法阶段研究报告_20261029.md'
old = (WORK / 'before.md').read_text(encoding='utf-8-sig')
new = TARGET.read_text(encoding='utf-8-sig')
staged = (WORK / 'after.md').read_text(encoding='utf-8-sig')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def tables(text):
    lines = text.splitlines()
    result = []
    k = 0
    while k < len(lines):
        if not lines[k].startswith('|'):
            k += 1
            continue
        start = k
        while k < len(lines) and lines[k].startswith('|'):
            k += 1
        end = k
        while k < len(lines) and not lines[k].strip():
            k += 1
        result.append({'rows': lines[start:end], 'after': lines[k] if k < len(lines) else ''})
    return result

def nums(row):
    return re.findall(r'[-+−]?\d+(?:\.\d+)?(?:[eE][+−-]?\d+)?', row.replace('−', '-'))

def is_subsequence(a, b):
    it = iter(b)
    return all(any(x == y for y in it) for x in a)

old_tables, new_tables = tables(old), tables(new)
checks = {'target_matches_reviewed_staging': new == staged}
details = {}
for n in range(1, 5):
    a = next(t for t in old_tables if t['after'].startswith(f'表{n} '))
    b = next(t for t in new_tables if t['after'].startswith(f'表{n} '))
    av = [nums(r) for r in a['rows'][2:]]
    bv = [nums(r) for r in b['rows'][2:]]
    checks[f'table_{n}_data_exact'] = av == bv
    details[f'table_{n}'] = {'old': av, 'new': bv}

for label, key in [('five_states', '立即全程'), ('choice_models', '0.201520'), ('dynamic_metrics', '0.442535'), ('appendix', '401.82')]:
    a = next(t for t in old_tables if any(key in r for r in t['rows']))
    b = next(t for t in new_tables if any(key in r for r in t['rows']))
    av = [nums(r) for r in a['rows'][2:]]
    bv = [nums(r) for r in b['rows'][2:]]
    checks[f'{label}_data_preserved'] = len(av) == len(bv) and all(is_subsequence(x, y) for x, y in zip(av, bv))
    details[label] = {'old': av, 'new': bv}

images_old = re.findall(r'!\[[^\]]*\]\(([^)]+)\)', old)
images_new = re.findall(r'!\[[^\]]*\]\(([^)]+)\)', new)
checks['six_image_references_unchanged'] = images_old == images_new and len(images_new) == 6
checks['all_image_targets_exist'] = all((TARGET.parent / p).is_file() for p in images_new)
checks['short_figure_captions_unchanged'] = re.findall(r'^图\d+ .+$', old, re.M) == re.findall(r'^图\d+ .+$', new, re.M)
checks['twelve_equation_blocks'] = new.splitlines().count('$$') == old.splitlines().count('$$') == 24
checks['all_equations_exactly_unchanged'] = re.findall(r'\$\$(.*?)\$\$', old, re.S) == re.findall(r'\$\$(.*?)\$\$', new, re.S)
headings = re.findall(r'^#{2,4} (\d+(?:\.\d+)*)\s', new, re.M)
references = re.findall(r'(?<![\d.])(\d+(?:\.\d+)+)节', new)
checks['numbered_section_references_resolve'] = all(x in headings for x in references)
checks['no_undefined_generic_method_sentence'] = '复杂候选' not in new and '原方法' not in new
checks['table_columns_consistent'] = all(len({r.count('|') for r in t['rows']}) == 1 for t in new_tables)

receipt = {
    'date': '2026-10-29',
    'scope': 'Markdown report content and structure only; no research execution or Word/PDF synchronization',
    'target': str(TARGET),
    'original_sha256': digest(WORK / 'before.md'),
    'revised_sha256': digest(TARGET),
    'original_characters': len(old),
    'revised_characters': len(new),
    'checks': checks,
    'numeric_table_details': details,
    'images': [{'reference': p, 'sha256': digest((TARGET.parent / p).resolve())} for p in images_new],
    'section_references': references,
    'passed': all(checks.values()),
}
(WORK / 'qa_receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'passed': receipt['passed'], 'checks': checks, 'original_characters': len(old), 'revised_characters': len(new)}, ensure_ascii=False, indent=2))
if not receipt['passed']:
    raise SystemExit(1)

