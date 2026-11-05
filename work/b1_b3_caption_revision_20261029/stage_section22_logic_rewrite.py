from pathlib import Path
import hashlib,json,re,difflib
work=Path(__file__).resolve().parent
r=json.loads((work/'section22_logic_rewrite_source.json').read_text(encoding='utf-8'))
p=Path(r['target']);sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
assert sha(p)==r['before_sha256'],'User changed report; rebase needed'
text=Path(r['backup']).read_text(encoding='utf-8')
a=text.index('### 2.2 ');b=text.index('### 2.3 ',a)
old=text[a:b]
figure=re.search(r'^!\[图3\].+$',old,re.M).group()
caption=re.search(r'^图3 .+$',old,re.M).group()
equation=re.search(r'^\$\$\n.*?\n\$\$$',old,re.M|re.S).group()
table=re.search(r'^\| \*\*场景\*\*.*?(?=\n\n)',old,re.M|re.S).group()
table_caption=re.search(r'^表1 .+$',old,re.M).group()
new=(work/'section22_logic_rewrite_template.md').read_text(encoding='utf-8')
for key,value in [('@@FIGURE@@',figure),('@@CAPTION@@',caption),('@@EQUATION@@',equation),('@@TABLE@@',table),('@@TABLE_CAPTION@@',table_caption)]:
    assert new.count(key)==1
    new=new.replace(key,value)
new=new.rstrip()+'\n\n'
updated=text[:a]+new+text[b:]
assert updated[:a]==text[:a]
assert updated[a+len(new):]==text[b:]
assert [x for x in updated.splitlines() if x.startswith('|')]==[x for x in text.splitlines() if x.startswith('|')]
assert re.findall(r'^\$\$\n.*?\n\$\$$',updated,re.M|re.S)==re.findall(r'^\$\$\n.*?\n\$\$$',text,re.M|re.S)
assert re.findall(r'^!\[.*$',updated,re.M)==re.findall(r'^!\[.*$',text,re.M)
assert re.findall(r'^[图表]\d+ .+$',updated,re.M)==re.findall(r'^[图表]\d+ .+$',text,re.M)
staged=work/'section22_logic_rewrite_staged.md';staged.write_text(updated,encoding='utf-8',newline='')
(work/'section22_logic_rewrite_diff.patch').write_text(''.join(difflib.unified_diff(text.splitlines(True),updated.splitlines(True),fromfile='before.md',tofile='restructured.md')),encoding='utf-8')
r.update(status='staged',staged=str(staged),staged_sha256=sha(staged),only_section22_rewritten=True,all_tables_formulas_figures_and_captions_preserved=True,new_subsections=['2.2.1','2.2.2','2.2.3','2.2.4','2.2.5'],new_design_detail='50% randomized assignment probability verified from frozen generator; no experiments changed')
(work/'section22_logic_rewrite_receipt.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
print('Staged: section 2.2 restructured; all results tables, formulas and figures unchanged.')
