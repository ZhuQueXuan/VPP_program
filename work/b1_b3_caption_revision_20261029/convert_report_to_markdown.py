from pathlib import Path
from zipfile import ZipFile
from lxml import etree
import hashlib
import json
import re
import sys
import posixpath

sys.stdout.reconfigure(encoding='utf-8')
BASE = Path(__file__).resolve().parent
receipt = json.loads((BASE / 'compensation_effect_wording_receipt.json').read_text(encoding='utf-8'))
original = Path(receipt['target'])
source = Path(receipt['staged'])
target = original.with_suffix('.md')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(original) == receipt['before_sha256'], 'Original changed; rebase needed'
assert sha(source) == receipt['staged_sha256']
if target.exists():
    previous = json.loads((BASE / 'report_markdown_conversion_receipt.json').read_text(encoding='utf-8'))
    assert sha(target) == previous['output_sha256'], 'Markdown changed; do not overwrite'
before = {p.name: sha(p) for p in original.parent.iterdir() if p.is_file() and not p.name.startswith('~$')}
before.pop(target.name, None)
assets = BASE / 'report_markdown_assets'
assets.mkdir(exist_ok=True)
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
      'm': 'http://schemas.openxmlformats.org/officeDocument/2006/math',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
qn = lambda s: '{' + NS[s.split(':')[0]] + '}' + s.split(':')[1]
local = lambda e: etree.QName(e).localname
maths = []
figures = []
paragraphs = []
table_cells = []
headings = []

def tex_text(text):
    mapping = {'τ̂': r'\hat{\tau}', 'μ̂': r'\hat{\mu}', 'p̂': r'\hat{p}', 'f̄': r'\bar{f}',
               'Δ': r'\Delta ', 'τ': r'\tau ', 'μ': r'\mu ', 'π': r'\pi ',
               'η': r'\eta ', 'λ': r'\lambda ', '≥': r'\ge ', '∈': r'\in ',
               '×': r'\times ', '·': r'\cdot ', '∑': r'\sum ', '−': '-'}
    for a, b in mapping.items():
        text = text.replace(a, b)
    text = re.sub(r'[\u3400-\u9fff（）]+', lambda m: r'\text{' + m.group() + '}', text)
    unit_pattern = r'\b(kWh|kW|s/h|s)\b' if re.search(r'\d', text) else r'\b(kWh|kW|s/h)\b'
    text = re.sub(unit_pattern, lambda m: r'\mathrm{' + m.group() + '}', text)
    return text

def math(e):
    tag = local(e)
    child = lambda name: math(e.find('m:' + name, NS))
    if tag.endswith('Pr') or tag in ('lastRenderedPageBreak',):
        return ''
    if tag == 't':
        return tex_text(e.text or '')
    if tag == 'sSub':
        return child('e') + '_{' + child('sub') + '}'
    if tag == 'sSup':
        return child('e') + '^{' + child('sup') + '}'
    if tag == 'f':
        return r'\frac{' + child('num') + '}{' + child('den') + '}'
    if tag == 'nary':
        char = e.find('m:naryPr/m:chr', NS).get(qn('m:val'))
        return tex_text(char) + '_{' + child('sub') + '}' + child('e')
    assert tag in ('oMath', 'r', 'e', 'sub', 'sup', 'num', 'den'), tag
    return ''.join(math(c) for c in e)

def escape(text):
    return re.sub(r'([\\`*_\[\]<>])', r'\\\1', text)

with ZipFile(source) as z:
    root = etree.fromstring(z.read('word/document.xml'))
    rels = {r.get('Id'): r.get('Target') for r in etree.fromstring(z.read('word/_rels/document.xml.rels'))}

    def inline(e):
        tag = local(e)
        if tag in ('pPr', 'rPr', 'lastRenderedPageBreak', 'bookmarkStart', 'bookmarkEnd'):
            return ''
        if tag == 't':
            return escape(e.text or '')
        if tag == 'tab':
            return '    '
        if tag in ('br', 'cr'):
            return '<br>'
        if tag == 'oMath':
            result = math(e).strip()
            maths.append(result)
            return '$$\n' + result + '\n$$'
        if tag in ('drawing', 'pict'):
            nodes = e.findall('.//a:blip', NS)
            assert len(nodes) == 1, 'Unexpected picture representation'
            rid = nodes[0].get(qn('r:embed'))
            name = posixpath.normpath('word/' + rels[rid])
            data = z.read(name)
            index = len(figures) + 1
            asset = assets / ('figure-%02d' % index + Path(name).suffix)
            if asset.exists():
                assert asset.read_bytes() == data
            else:
                asset.write_bytes(data)
            link = '../work/' + BASE.name + '/report_markdown_assets/' + asset.name
            figures.append({'source': name, 'path': str(asset), 'sha256': sha(asset), 'link': link})
            return f'![图{index}]({link})'
        children = ''.join(inline(c) for c in e)
        if tag == 'r' and children.strip():
            bold = e.find('w:rPr/w:b', NS)
            if bold is not None and bold.get(qn('w:val'), '1') not in ('0', 'false', 'off'):
                lead = children[:len(children) - len(children.lstrip())]
                tail = children[len(children.rstrip()):]
                return lead + '**' + children.strip() + '**' + tail
        return children

    blocks = []
    table_count = 0
    for e in root.find('w:body', NS):
        tag = local(e)
        if tag == 'sectPr':
            continue
        if tag == 'p':
            text = ''.join(e.xpath('.//w:t/text()', namespaces=NS))
            converted = inline(e).strip()
            if not converted:
                continue
            style = e.find('w:pPr/w:pStyle', NS)
            sid = style.get(qn('w:val')) if style is not None else ''
            levels = {'aa': 1, '1': 2, '21': 3, '31': 4}
            if sid in levels:
                converted = '#' * levels[sid] + ' ' + text
                headings.append(text)
            # Coalesce Word's adjacent bold runs into a single readable span.
            converted = converted.replace('****', '')
            if text:
                paragraphs.append({'source': text, 'markdown': converted})
            blocks.append(converted)
        elif tag == 'tbl':
            table_count += 1
            rows = []
            for row in e.findall('w:tr', NS):
                cells = []
                for cell in row.findall('w:tc', NS):
                    cell_text = ''.join(cell.xpath('.//w:t/text()', namespaces=NS))
                    table_cells.append(cell_text)
                    parts = [inline(p).strip().replace('\n', ' ') for p in cell.findall('w:p', NS)]
                    cells.append('<br>'.join(p for p in parts if p).replace('|', r'\|').replace('****', ''))
                    span = cell.find('w:tcPr/w:gridSpan', NS)
                    if span is not None:
                        cells.extend([''] * (int(span.get(qn('w:val'))) - 1))
                rows.append(cells)
            width = max(map(len, rows))
            rows = [row + [''] * (width - len(row)) for row in rows]
            lines = ['| ' + ' | '.join(rows[0]) + ' |', '| ' + ' | '.join(['---'] * width) + ' |']
            lines.extend('| ' + ' | '.join(row) + ' |' for row in rows[1:])
            blocks.append('\n'.join(lines))
        else:
            raise ValueError('Unexpected body element: ' + tag)

content = '\n\n'.join(blocks) + '\n'
content = re.sub(r'(?m)^(\*\*[^\n*]+\*\*)(?=[\u3400-\u9fff])', r'\1 ', content)
assert len(maths) == len(root.findall('.//m:oMath', NS)) == 12
assert len(figures) == 6
assert content.count('\n$$\n') == 24
assert '补偿影响估计的输入与计算步骤。' in content
assert '这里的“训练”就是用训练数据计算并保存各组均值' in content
# Validate every ordinary source paragraph and table cell is retained verbatim,
# allowing only Markdown escaping and bold markup.
def normalized(text):
    text = text.replace('**', '').replace('<br>', '')
    return re.sub(r'\\([\\`*_\[\]<>|])', r'\1', text).replace(' ', '').replace('\n', '')
flat = normalized(content)
for p in paragraphs:
    assert normalized(p['source']) in flat, 'Missing paragraph: ' + p['source'][:50]
for cell in table_cells:
    assert normalized(cell) in flat, 'Missing cell: ' + cell
staged = BASE / 'report_markdown_staged.md'
staged.write_text(content, encoding='utf-8')
assert sha(original) == receipt['before_sha256']
current = {p.name: sha(p) for p in original.parent.iterdir() if p.is_file() and not p.name.startswith('~$')}
current.pop(target.name, None)
assert current == before
target.write_bytes(staged.read_bytes())
after = {p.name: sha(p) for p in original.parent.iterdir() if p.is_file() and not p.name.startswith('~$')}
assert set(after) - set(before) == {target.name}
assert all(after[name] == value for name, value in before.items())
report = {'status': 'complete', 'output': str(target), 'output_sha256': sha(target),
          'source': str(source), 'source_sha256': sha(source), 'original_word_unchanged': True,
          'only_new_file_in_04': target.name, 'includes_authorized_section22_revision': True,
          'all_ordinary_paragraphs_and_table_cells_preserved': True,
          'paragraph_count': len(paragraphs), 'table_count': table_count, 'formula_count': len(maths),
          'headings': headings, 'formulas': maths, 'figures': figures,
          'asset_folder': str(assets), 'folder_before': before}
(BASE / 'report_markdown_conversion_receipt.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: report[k] for k in ('status', 'output', 'paragraph_count', 'table_count', 'formula_count')}, ensure_ascii=False))
